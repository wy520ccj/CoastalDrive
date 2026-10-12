"""横摆参考与分轮制动分配；实际力仍由制动器和联合滑移轮胎产生。"""

import math
from dataclasses import dataclass

from panda3d.core import Vec3
from wheel_contact_kernels import stability_advance

from tire_properties import tire_grip


@dataclass(frozen=True)
class StabilityConfig:
    esc_enabled: bool = True
    minimum_speed: float = 1.5
    reference_response: float = .15
    yaw_gain: float = 6.0  # 横摆率误差到期望横摆加速度，s⁻¹。
    sideslip_gain: float = 6.0  # 侧偏角超限到期望横摆加速度，s⁻²。
    yaw_threshold: float = .10
    sideslip_threshold: float = .06
    moment_threshold: float = 150.0
    engine_cut_gain: float = .4  # 按各自误差阈值归一化后的削矩比例，无量纲。
    continuous_reference: bool = True  # 低于介入速度仍跟踪有支撑的参考，false隔离旧控制A/B。


@dataclass(frozen=True)
class StabilityState:
    reference_yaw_rate: float = 0.0
    unlimited_yaw_rate: float = 0.0
    observed_yaw_rate: float = 0.0
    sideslip: float = 0.0
    yaw_error: float = 0.0
    desired_brake_moment: float = 0.0
    baseline_brake_moment: float = 0.0
    allocated_brake_moment: float = 0.0
    residual_moment: float = 0.0
    brake_requests: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    torque_scale: float = 1.0
    active: bool = False
    feedback_tick: int = 0
    reference_sideslip: float = 0.0
    sideslip_error: float = 0.0


def excess(value, threshold):
    return math.copysign(max(0.0, abs(value) - threshold), value)


def allocate_brakes(base, limits, arms, target, prefer_rear):
    """先释放妨碍纠偏的一侧，再增加同向制动；四轮均受实际容量约束。"""
    forces = list(base)
    remaining = target - sum(force * arm for force, arm in zip(forces, arms))
    sign = math.copysign(1.0, remaining)
    for index in range(4):
        if arms[index] * sign < 0:
            release = min(forces[index], abs(remaining / arms[index]))
            forces[index] -= release
            remaining += release * arms[index]
    order = (2, 3, 0, 1) if prefer_rear else (0, 1, 2, 3)
    for index in order:
        if arms[index] * sign > 0:
            apply = min(limits[index] - forces[index], abs(remaining / arms[index]))
            forces[index] += apply
            remaining -= apply * arms[index]
    return tuple(forces)


class StabilityControl:
    def __init__(self, vehicle_config):
        self.vehicle_config = vehicle_config
        self.config = vehicle_config.stability
        self.state = StabilityState()

    def advance(self, chassis, wheels, contacts, requests, steering, dt):
        """上一完成步的车身、轮速、法向支撑和路面μ均为仿真真值。"""
        vehicle, config = self.vehicle_config, self.config
        pose = chassis.getTransform()
        orientation = pose.getQuat()
        local_velocity = orientation.conjugate().xform(chassis.getLinearVelocity())
        speed = float(local_velocity.y)
        yaw = float(orientation.conjugate().xform(chassis.getAngularVelocity()).z)
        beta = math.atan2(local_velocity.x, abs(speed))
        capacities, limits, arms = [], [], []
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
            mu = vehicle.road_friction if contact.surface == "asphalt" else vehicle.grass_friction
            grip = tire_grip(contact.normal_load, mu, vehicle)
            grip_budget += grip
            limits.append(min(capacity, grip))
            angle = math.radians(wheel.steering)
            heading = orientation.xform(Vec3(math.sin(angle), math.cos(angle), 0))
            normal = Vec3(*contact.contact_normal)
            tangent = (heading - normal * heading.dot(normal)).normalized()
            point = Vec3(*contact.contact_point) - pose.getPos()
            arms.append(-math.copysign(1.0, wheel.longitudinal_speed)
                        * point.cross(tangent).dot(orientation.getUp()))
        supported = any(w.sample_support for w in wheels)
        inertia = chassis.getInertia().z if abs(speed) >= config.minimum_speed and supported else 0.
        self.state = stability_advance(config, vehicle, self.state, tuple(requests), speed, yaw, beta,
            inertia, steering, dt, tuple(capacities), tuple(limits), tuple(arms), grip_budget, supported,
            wheels[0].sample_tick)
        return self.state
