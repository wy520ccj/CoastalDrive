"""334857e原电子控制计算，作为冻结数值对照，不参与生产。"""

import math

from panda3d.core import Vec3

from tire_properties import tire_grip
from vehicle_brakes import BrakeState
from vehicle_stability import StabilityState, allocate_brakes, excess
from vehicle_traction import TractionState


class Brakes:

    def __init__(self, config):
        self.config = config
        self.states = tuple(BrakeState() for _ in range(4))

    def advance(self, requests, wheels, radius, dt):
        """上一完整步轮速/轮心速度为反馈；首次使用仿真真值观测。"""
        config = self.config
        states = []
        for requested, wheel, previous in zip(requests, wheels, self.states):
            wheel_radius = radius if wheel.rolling_radius is None else wheel.rolling_radius
            speed = abs(wheel.longitudinal_speed)
            eligible = config.abs_enabled and requested > 0 and wheel.sample_support and (speed >= config.minimum_speed)
            slip = None
            if wheel.sample_support and speed >= config.minimum_speed:
                direction = math.copysign(1.0, wheel.longitudinal_speed)
                slip = (speed - direction * wheel_radius * wheel.omega) / speed
            predicted = slip
            if slip is not None and previous.braking_slip is not None:
                predicted += config.response_time * (slip - previous.braking_slip) / dt
            active = eligible and (previous.abs_active or predicted > config.target_slip + config.slip_hysteresis)
            command, phase = (requested, 'normal')
            if active:
                command = min(previous.commanded, requested)
                error = config.target_slip - predicted
                if error < -config.slip_hysteresis:
                    rate = max(-config.release_rate, config.slip_rate_gain * error)
                    command = max(0.0, command + rate * dt)
                    phase = 'release'
                elif error > config.slip_hysteresis:
                    rate = min(config.apply_rate, config.slip_rate_gain * error)
                    command = min(requested, command + rate * dt)
                    phase = 'apply'
                else:
                    phase = 'hold'
            pressure = command if config.response_time == 0 else previous.pressure + (command - previous.pressure) * (1 - math.exp(-dt / config.response_time))
            states.append(BrakeState(requested, command, pressure, slip, active, phase, wheel.sample_tick, predicted))
        self.states = tuple(states)
        return tuple(state.pressure for state in self.states)


class TractionControl:

    def __init__(self, config, driven_wheels=(2, 3)):
        self.config = config
        self.driven_wheels = driven_wheels
        self.state = TractionState()

    def advance(self, pedal, direction, braking, wheels, radius, dt):
        """反馈取上一完整步真值；离地轮不用于路面滑转调节。"""
        config, previous = (self.config, self.state)
        slips = tuple(direction * ((radius if wheel.rolling_radius is None else wheel.rolling_radius) * wheel.omega - wheel.longitudinal_speed) / max(abs(wheel.longitudinal_speed), config.slip_speed) if wheel.sample_support else None for wheel in wheels)
        requests = [0.0] * 4
        scale, active = (1.0, False)
        eligible = config.tcs_enabled and pedal > 0 and (direction != 0) and (not braking)
        driven = [slips[index] for index in self.driven_wheels if slips[index] is not None]
        if eligible and driven:
            predicted = []
            for index in self.driven_wheels:
                slip = slips[index]
                if slip is None:
                    continue
                trend = 0.0
                if previous.wheel_slips[index] is not None:
                    trend = (slip - previous.wheel_slips[index]) / dt
                predicted.append(slip + config.prediction_time * trend)
                requests[index] = min(config.maximum_brake, config.brake_gain * max(0.0, slip - config.target_slip))
            worst = max(predicted)
            active = previous.active or worst > config.target_slip + config.slip_hysteresis
            if active:
                error = config.target_slip - worst
                rate = max(-config.release_rate, min(config.apply_rate, config.slip_rate_gain * error))
                scale = max(0.0, min(1.0, previous.torque_scale + rate * dt))
                active = scale < 1.0 or any(requests)
            else:
                requests = [0.0] * 4
        self.state = TractionState(pedal, scale, active, slips, tuple(requests), tuple(wheel.sample_tick for wheel in wheels))
        return self.state


class StabilityControl:

    def __init__(self, vehicle_config):
        self.vehicle_config = vehicle_config
        self.config = vehicle_config.stability
        self.state = StabilityState()

    def advance(self, chassis, wheels, contacts, requests, steering, dt):
        """上一完成步的车身、轮速、法向支撑和路面μ均为仿真真值。"""
        vehicle, config = (self.vehicle_config, self.config)
        pose = chassis.getTransform()
        orientation = pose.getQuat()
        local_velocity = orientation.conjugate().xform(chassis.getLinearVelocity())
        speed = float(local_velocity.y)
        yaw = float(orientation.conjugate().xform(chassis.getAngularVelocity()).z)
        direction = math.copysign(1.0, speed)
        beta = math.atan2(local_velocity.x, abs(speed))
        capacities, limits, arms = ([], [], [])
        grip_budget = 0.0
        for index, wheel in enumerate(wheels):
            share = vehicle.front_brake_share if index < 2 else 1 - vehicle.front_brake_share
            capacity = vehicle.brake_torque * share / (2 * vehicle.wheel_radius)
            capacities.append(capacity)
            if not wheel.sample_support:
                limits.append(0.0)
                arms.append(0.0)
                continue
            contact = contacts[index]
            mu = vehicle.road_friction if contact.surface == 'asphalt' else vehicle.grass_friction
            grip = tire_grip(contact.normal_load, mu, vehicle)
            grip_budget += grip
            limits.append(min(capacity, grip))
            angle = math.radians(wheel.steering)
            heading = orientation.xform(Vec3(math.sin(angle), math.cos(angle), 0))
            normal = Vec3(*contact.contact_normal)
            tangent = (heading - normal * heading.dot(normal)).normalized()
            point = Vec3(*contact.contact_point) - pose.getPos()
            arms.append(-math.copysign(1.0, wheel.longitudinal_speed) * point.cross(tangent).dot(orientation.getUp()))
        base = tuple((min(request * capacity, limit) for request, capacity, limit in zip(requests, capacities, limits)))
        baseline = sum((force * arm for force, arm in zip(base, arms)))
        unlimited = -speed * math.tan(math.radians(steering)) / vehicle.wheelbase
        supported = any(w.sample_support for w in wheels)
        eligible = abs(speed) >= config.minimum_speed and supported
        reference, reference_beta, target = (0.0, 0.0, 0.0)
        if eligible or (config.continuous_reference and supported and (speed != 0)):
            yaw_limit = grip_budget / (vehicle.mass * abs(speed))
            achievable = max(-yaw_limit, min(yaw_limit, unlimited))
            reference = self.state.reference_yaw_rate + (achievable - self.state.reference_yaw_rate) * (1 - math.exp(-dt / config.reference_response))
            rear_distance = vehicle.wheelbase * vehicle.front_weight_share
            rear_stiffness = 2 * vehicle.rear_lateral_stiffness
            rear_slip = vehicle.mass * vehicle.front_weight_share * speed * reference / rear_stiffness
            reference_beta = math.atan(-rear_distance * reference / abs(speed) + rear_slip)
        if eligible:
            target = chassis.getInertia().z * (config.yaw_gain * excess(reference - yaw, config.yaw_threshold) - direction * config.sideslip_gain * excess(beta - reference_beta, config.sideslip_threshold))
        output, scale, allocated = (tuple(requests), 1.0, baseline)
        if config.esc_enabled and eligible and (abs(target - baseline) > config.moment_threshold):
            understeer = abs(yaw) < abs(reference) and yaw * reference >= 0
            forces = allocate_brakes(base, limits, arms, target, understeer)
            output = tuple((request if force == initial else force / capacity for request, force, initial, capacity in zip(requests, forces, base, capacities)))
            allocated = sum((force * arm for force, arm in zip(forces, arms)))
            scale = max(0.0, 1 - config.engine_cut_gain * (abs(excess(reference - yaw, config.yaw_threshold)) / config.yaw_threshold + abs(excess(beta - reference_beta, config.sideslip_threshold)) / config.sideslip_threshold))
        active = output != tuple(requests) or scale < 1.0
        self.state = StabilityState(reference, unlimited, yaw, beta, reference - yaw, target, baseline, allocated, target - allocated, output, scale, active, wheels[0].sample_tick, reference_beta, beta - reference_beta)
        return self.state
