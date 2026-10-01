"""四轮共享一个车体末速度；内迭代只求接触力，收敛后才提交冲量和变形。"""

import math
from dataclasses import dataclass, replace

from tire_compliance import contact_force, energy_terms
from tire_forces import slip_state
from tire_properties import tire_grip, tire_stiffness
from wheel_dynamics import Mobility, advance_wheel


def dot(first, second):
    return sum(first[i] * second[i] for i in range(3))


def cross(first, second):
    return (first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0])


@dataclass(frozen=True)
class ContactFrame:
    steering: float
    supported: bool
    load: float
    mu: float
    tangent: object
    axle: object
    point: object
    hub: object
    mobility: Mobility
    elastic_frame: tuple | None
    response_x: tuple
    response_y: tuple
    response_t: tuple


def advance_coupled(velocity, angular, omega, frames, deformations, drives, brakes,
                    config, rear_config, dt):
    """块Gauss-Seidel解同一隐式四轮系统，不把中间迭代当真实运动或变形。"""
    configurations = (config, config, rear_config, rear_config)
    forces = [(0.0, 0.0, 0.0)] * 4
    radius, inertia = config.wheel_radius, config.wheel_inertia
    rolling_contacts = tuple(
        max(abs(dot(tuple(velocity[a] + cross(angular, frame.hub)[a] for a in range(3)), frame.tangent)),
            abs(radius * omega[i])) >= config.static_contact_speed for i, frame in enumerate(frames))

    def body_state(exclude=None):
        total_force, total_angular = [0.0] * 3, [0.0] * 3
        for j, frame in enumerate(frames):
            if j == exclude:
                continue
            fx, fy, used_brake = forces[j]
            reaction = drives[j] - used_brake
            for axis in range(3):
                total_force[axis] += frame.tangent[axis] * fx + frame.axle[axis] * fy
                total_angular[axis] += (frame.response_x[axis] * fx + frame.response_y[axis] * fy
                                        + frame.response_t[axis] * reaction)
        return (tuple(velocity[axis] + dt * total_force[axis] / config.mass for axis in range(3)),
                tuple(angular[axis] + dt * total_angular[axis] for axis in range(3)))

    def completed_steps():
        end_velocity, end_angular = body_state()
        completed, maximum, maximum_brake = [], 0.0, 0.0
        for i, frame in enumerate(frames):
            wheel_config = configurations[i]
            fx, fy, used_brake = forces[i]
            wheel_omega = omega[i] + dt * (drives[i] - used_brake - radius * fx) / inertia
            vx = dot(tuple(end_velocity[a] + cross(end_angular, frame.hub)[a] for a in range(3)), frame.tangent)
            vy = dot(tuple(end_velocity[a] + cross(end_angular, frame.point)[a] for a in range(3)), frame.axle)
            body_omega = dot(end_angular, frame.axle)
            grip = tire_grip(frame.load, frame.mu, wheel_config)
            cx, cy = tire_stiffness(frame.load, wheel_config)
            target, elastic, rate, patch, patch_kappa, patch_alpha, mode = contact_force(
                (fx, fy), deformations[i], (radius * wheel_omega - vx, -vy),
                max(abs(vx), config.slip_speed), rolling_contacts[i], grip, cx, cy, dt,
                config.tire_contact_stiffness, config.tire_contact_damping,
                config.tire_shape, config.tire_curvature)
            force_error = math.hypot(fx - target[0], fy - target[1])
            relative_omega = wheel_omega + body_omega
            correction = relative_omega / (dt * (1 / inertia + frame.mobility.tt))
            brake_target = max(-brakes[i], min(brakes[i], used_brake + correction))
            brake_error = abs(used_brake - brake_target) / radius
            maximum = max(maximum, force_error)
            maximum_brake = max(maximum_brake, brake_error)
            kappa, alpha = slip_state(vx, vy, wheel_omega, radius, config)
            energy, material, road, numerical = energy_terms(
                (fx, fy), deformations[i], elastic, rate, patch, dt,
                config.tire_contact_stiffness, config.tire_contact_damping)
            completed.append(replace(local_steps[i], omega=wheel_omega, relative_omega=relative_omega,
                                     vx=vx, vy=vy, body_omega=body_omega, kappa=kappa, alpha=alpha,
                                     residual=max(force_error, brake_error),
                                     mode=mode if frame.load > 0 else "airborne",
                                     deformation_x=elastic[0], deformation_y=elastic[1],
                                     patch_kappa=patch_kappa, patch_alpha=patch_alpha,
                                     elastic_energy=energy, material_dissipation=material,
                                     road_dissipation=road, elastic_numerical_dissipation=numerical,
                                     deformation_rate_x=rate[0], deformation_rate_y=rate[1]))
        return tuple(completed), maximum, maximum_brake

    local_steps = [None] * 4
    for iteration in range(20):
        order = range(4) if iteration % 2 == 0 else range(3, -1, -1)
        for i in order:
            frame = frames[i]
            known_velocity, known_angular = body_state(exclude=i)
            hub_speed = tuple(known_velocity[a] + cross(known_angular, frame.hub)[a] for a in range(3))
            point_speed = tuple(known_velocity[a] + cross(known_angular, frame.point)[a] for a in range(3))
            step = advance_wheel(omega[i], dot(hub_speed, frame.tangent), dot(point_speed, frame.axle),
                                 dot(known_angular, frame.axle), drives[i], brakes[i], frame.load,
                                 frame.mu, frame.mobility, dt, configurations[i], deformations[i],
                                 force_tolerance=.0001, rolling_contact=rolling_contacts[i])
            forces[i] = (step.fx, step.fy, step.brake_torque)
            local_steps[i] = step
        completed, error, brake_error = completed_steps()
        if error < .001 and brake_error < 1e-9:
            return completed
    raise ArithmeticError(f"四轮共同末速度积分超过20次迭代：接点 {error:.6g} N，制动等效 {brake_error:.6g} N")
