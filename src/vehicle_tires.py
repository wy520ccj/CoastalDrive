"""四轮独立转动状态、接地坐标和刚体冲量；原生悬架保持独立。"""

import math
from dataclasses import replace

from panda3d.core import Mat3, Quat, Vec3

from tire_forces import slip_state
from vehicle_config import CAR, wheel_hubs
from vehicle_contacts import road_support
from vehicle_state import WheelDynamicsState, WheelState
from wheel_dynamics import Mobility, advance_wheel


class Tires:
    def __init__(self, config=CAR):
        self.config = config
        self.hubs = wheel_hubs(config)
        self.rear_config = replace(config, lateral_stiffness=config.rear_lateral_stiffness)
        self.omega = [0.0] * 4
        self.rotation = [0.0] * 4
        self.states = tuple(WheelDynamicsState() for _ in range(4))

    def initialize_rolling(self, speed):
        """仅用于试验初始条件；运行中轮速始终由转矩方程积分。"""
        self.omega = [speed / self.config.wheel_radius] * 4

    def driven_omega(self, chassis):
        axle = chassis.getTransform().getQuat().getRight()
        return (self.omega[2] + self.omega[3]) / 2 + chassis.getAngularVelocity().dot(axle)

    def advance(self, chassis, contacts, angles, drive, engine_drag, brake, tick, dt,
                external_velocity=(0.0, 0.0, 0.0), external_angular=(0.0, 0.0, 0.0)):
        pose = chassis.getTransform()
        origin = pose.getPos()
        orientation = pose.getQuat()
        inv_inertia = chassis.getInvInertiaTensorWorld()
        config = self.config
        wheel_frames = []
        for index in range(4):
            angle = angles[index] if index < 2 else 0.0
            steering = Quat()
            steering.setHpr(Vec3(-angle, 0, 0))
            heading = orientation.xform(steering.xform(Vec3(0, 1, 0)))
            contact = contacts[index] if contacts else None
            supported = contact is not None and contact.in_contact and road_support(
                contact.contact_normal
            )
            if supported:
                normal = Vec3(*contact.contact_normal)
                tangent = (heading - normal * heading.dot(normal)).normalized()
                axle = tangent.cross(normal)
                point = Vec3(*contact.contact_point) - origin
                load = contact.normal_load
                mu = config.road_friction if contact.surface == "asphalt" else config.grass_friction
            else:
                normal = orientation.getUp()
                tangent = heading
                axle = tangent.cross(normal)
                point = orientation.xform(Vec3(*self.hubs[index])) - normal * config.wheel_radius
                load, mu = 0.0, config.road_friction
            hub = point + normal * config.wheel_radius
            # Fx在接点的力矩减去轮轴的r*Fx反力矩，等效于轮心力与内部驱动反力。
            moment_x = point.cross(tangent) - axle * config.wheel_radius
            moment_y = point.cross(axle)
            response_x = inv_inertia.xform(moment_x)
            response_y = inv_inertia.xform(moment_y)
            response_t = inv_inertia.xform(axle)
            mobility = Mobility(
                1 / config.mass + moment_x.dot(response_x),
                moment_x.dot(response_y), moment_x.dot(response_t),
                1 / config.mass + moment_y.dot(response_y),
                moment_y.dot(response_t), axle.dot(response_t),
            )
            wheel_frames.append((
                angle, supported, load, mu, tangent, axle, point, hub, mobility,
            ))

        sub_dt = dt / config.tire_substeps
        states = [None] * 4
        longitudinal_impulses = [0.0] * 4
        lateral_impulses = [0.0] * 4
        brake_angular_impulses = [0.0] * 4
        for substep in range(config.tire_substeps):
            # 正反次序成对，避免固定左轮先积分产生持续偏航偏置。
            order = range(4) if substep % 2 == 0 else range(3, -1, -1)
            for index in order:
                frame = wheel_frames[index]
                angle, supported, load, mu, tangent, axle, point, hub, mobility = frame
                # 预报Bullet随后推进的已知外力增量；冲量只施加轮胎部分，不重复推进外力。
                velocity = chassis.getLinearVelocity() + Vec3(*external_velocity)
                angular = chassis.getAngularVelocity() + Vec3(*external_angular)
                vx = (velocity + angular.cross(hub)).dot(tangent)
                vy = (velocity + angular.cross(point)).dot(axle)
                requested_drive = drive / 2 if index >= 2 else 0.0
                share = config.front_brake_share if index < 2 else 1 - config.front_brake_share
                capacity = config.brake_torque * brake * share / 2
                if index >= 2:
                    capacity += engine_drag / 2
                step = advance_wheel(
                    self.omega[index], float(vx), float(vy), float(angular.dot(axle)),
                    requested_drive, capacity, load, mu, mobility, sub_dt,
                    config if index < 2 else self.rear_config,
                )
                force = tangent * step.fx + axle * step.fy
                chassis.applyImpulse(force * sub_dt, point)
                reaction = requested_drive - step.brake_torque - config.wheel_radius * step.fx
                chassis.applyTorqueImpulse(axle * (sub_dt * reaction))
                longitudinal_impulses[index] += sub_dt * step.fx
                lateral_impulses[index] += sub_dt * step.fy
                brake_angular_impulses[index] += sub_dt * step.brake_torque
                self.omega[index] = step.omega
                self.rotation[index] += sub_dt * step.relative_omega
                states[index] = WheelDynamicsState(
                    omega=step.omega, rotation=self.rotation[index],
                    relative_omega=step.relative_omega,
                    longitudinal_speed=step.vx, lateral_speed=step.vy,
                    kappa=step.kappa if supported else None,
                    alpha=step.alpha if supported else None,
                    fx=step.fx, fy=step.fy, drive_torque=requested_drive,
                    brake_capacity=capacity, brake_torque=step.brake_torque,
                    normal_load=load, road_support=supported, steering=angle,
                    force_contact_tick=tick, force_residual=step.residual,
                    force_kappa=step.kappa if supported else None,
                    force_alpha=step.alpha if supported else None,
                    force_mode=step.mode,
                    longitudinal_impulse=longitudinal_impulses[index],
                    lateral_impulse=lateral_impulses[index],
                    brake_angular_impulse=brake_angular_impulses[index],
                )
        self.states = tuple(states)

    def observe(self, chassis, contacts, tick):
        """完成Bullet步后采样当前滑移；保留前一施力阶段的力与求解滑移。"""
        pose = chassis.getTransform()
        velocity, angular = chassis.getLinearVelocity(), chassis.getAngularVelocity()
        states = []
        for index, (state, contact) in enumerate(zip(self.states, contacts)):
            steer = Quat()
            steer.setHpr(Vec3(-state.steering, 0, 0))
            heading = pose.getQuat().xform(steer.xform(Vec3(0, 1, 0)))
            supported = contact.in_contact and road_support(contact.contact_normal)
            if supported:
                normal = Vec3(*contact.contact_normal)
                tangent = (heading - normal * heading.dot(normal)).normalized()
                point = Vec3(*contact.contact_point) - pose.getPos()
            else:
                normal = pose.getQuat().getUp()
                tangent = heading
                point = pose.getQuat().xform(Vec3(*self.hubs[index]))
                point -= normal * self.config.wheel_radius
            axle = tangent.cross(normal)
            hub = point + normal * self.config.wheel_radius
            vx = (velocity + angular.cross(hub)).dot(tangent)
            vy = (velocity + angular.cross(point)).dot(axle)
            kappa, alpha = slip_state(vx, vy, self.omega[index],
                                      self.config.wheel_radius, self.config)
            states.append(replace(
                state, relative_omega=self.omega[index] + angular.dot(axle),
                longitudinal_speed=float(vx), lateral_speed=float(vy),
                kappa=kappa if supported else None, alpha=alpha if supported else None,
                sample_support=supported, sample_tick=tick,
            ))
        self.states = tuple(states)

    def wheel_poses(self, chassis, bullet_vehicle):
        """原生矩阵提供悬架位置；转向和滚动来自真实执行器及独立转角。"""
        chassis_orientation = chassis.getTransform().getQuat()
        wheels = []
        for index, wheel in enumerate(bullet_vehicle.getWheels()):
            steer = Quat()
            steer.setHpr(Vec3(-self.states[index].steering, 0, 0))
            roll = Quat()
            roll.setFromAxisAngle(-math.degrees(self.rotation[index]), Vec3(1, 0, 0))
            rows = [chassis_orientation.xform(steer.xform(roll.xform(axis))) for axis in (
                Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1),
            )]
            orientation = Quat()
            orientation.setFromMatrix(Mat3(*(value for row in rows for value in row)))
            wheels.append(WheelState(tuple(wheel.getWorldTransform().getRow3(3)),
                                     tuple(orientation)))
        return tuple(wheels)
