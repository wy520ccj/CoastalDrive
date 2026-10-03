"""四轮共享一个车体末速度；内迭代只求接触力，收敛后才提交冲量和变形。"""

import math
from dataclasses import dataclass, replace

from rotor_dynamics import bearing_torques, cross, dot, solve_transport
from tire_compliance import contact_force, energy_terms
from tire_forces import combined_force, slip_state
from tire_properties import tire_grip, tire_stiffness
from wheel_dynamics import Mobility, advance_wheel


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
    spin_axis: tuple | None = None
    rolling_radius: float | None = None
    moment_x: tuple | None = None


def advance_coupled(velocity, angular, omega, frames, deformations, drives, brakes,
                    config, rear_config, dt, *, inverse_inertia=None,
                    steering_torques=((0.0, 0.0, 0.0),) * 4):
    """块Gauss-Seidel解同一隐式四轮系统，不把中间迭代当真实运动或变形。"""
    configurations = (config, config, rear_config, rear_config)
    forces = [(0.0, 0.0, 0.0)] * 4
    radius, inertia = config.wheel_radius, config.wheel_inertia
    rotor = config.wheel_rotor_transport
    radii = tuple(frame.rolling_radius for frame in frames) if rotor else (radius,) * 4
    axes = tuple(frame.spin_axis for frame in frames) if rotor else tuple(frame.axle for frame in frames)

    def longitudinal_speed(velocity, angular, frame):
        if rotor:
            return dot(velocity, frame.tangent) + dot(angular, frame.moment_x)
        return dot(tuple(velocity[a] + cross(angular, frame.hub)[a] for a in range(3)), frame.tangent)

    rolling_contacts = tuple(
        max(abs(longitudinal_speed(velocity, angular, frame)),
            abs(radii[i] * omega[i])) >= config.static_contact_speed for i, frame in enumerate(frames))

    def body_state(exclude=None, bearing=None):
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
        end_velocity = tuple(velocity[axis] + dt * total_force[axis] / config.mass for axis in range(3))
        if rotor:
            steering = tuple(sum(torque[a] for torque in steering_torques) for a in range(3))
            known = tuple(angular[a] + dt * (total_angular[a] + dot(inverse_inertia[a], steering))
                          for a in range(3))
            if bearing is not None:
                end_angular = tuple(known[a] + dt * dot(inverse_inertia[a], bearing) for a in range(3))
            else:
                speeds = tuple(omega[i] + dt * (drives[i] - forces[i][2] - radii[i] * forces[i][0]) / inertia
                               for i in range(4))
                spin = tuple(-inertia * sum(speeds[i] * axes[i][a] for i in range(4)) for a in range(3))
                end_angular = solve_transport(known, inverse_inertia, spin, dt)
        else:
            end_angular = tuple(angular[axis] + dt * total_angular[axis] for axis in range(3))
        return end_velocity, end_angular

    def completed_steps():
        end_velocity, end_angular = body_state()
        end_omega = tuple(omega[i] + dt * (drives[i] - forces[i][2] - radii[i] * forces[i][0]) / inertia
                          for i in range(4))
        gyro = bearing_torques(axes, end_omega, inertia, end_angular) if rotor else ((0.0, 0.0, 0.0),) * 4
        completed, maximum, maximum_brake = [], 0.0, 0.0
        for i, frame in enumerate(frames):
            wheel_config = configurations[i]
            radius = radii[i]
            fx, fy, used_brake = forces[i]
            wheel_omega = omega[i] + dt * (drives[i] - used_brake - radius * fx) / inertia
            vx = longitudinal_speed(end_velocity, end_angular, frame)
            vy = dot(tuple(end_velocity[a] + cross(end_angular, frame.point)[a] for a in range(3)), frame.axle)
            body_omega = dot(end_angular, axes[i])
            grip = tire_grip(frame.load, frame.mu, wheel_config)
            cx, cy = tire_stiffness(frame.load, wheel_config)
            kappa, alpha = slip_state(vx, vy, wheel_omega, radius, config)
            if config.tire_compliance:
                target, elastic, rate, patch, patch_kappa, patch_alpha, mode = contact_force(
                    (fx, fy), deformations[i], (radius * wheel_omega - vx, -vy),
                    max(abs(vx), config.slip_speed), rolling_contacts[i], grip, cx, cy, dt,
                    config.tire_contact_stiffness, config.tire_contact_damping,
                    config.tire_shape, config.tire_curvature)
                force_error = math.hypot(fx - target[0], fy - target[1])
                energy, material, road, numerical = energy_terms(
                    (fx, fy), deformations[i], elastic, rate, patch, dt,
                    config.tire_contact_stiffness, config.tire_contact_damping)
            else:
                mode = local_steps[i].mode
                if mode == "sticking":
                    force_error = math.hypot((vx - radius * wheel_omega) / (dt * (
                        frame.mobility.xx + radius**2 / inertia)), vy / (dt * frame.mobility.yy))
                else:
                    target = combined_force(kappa, alpha, grip, cx, cy, config.tire_shape, config.tire_curvature)
                    force_error = math.hypot(fx - target[0], fy - target[1])
                elastic = rate = (0.0, 0.0)
                patch_kappa = patch_alpha = None
                energy = material = road = numerical = 0.0
            relative_omega = wheel_omega + body_omega
            correction = relative_omega / (dt * (1 / inertia + frame.mobility.tt))
            brake_target = max(-brakes[i], min(brakes[i], used_brake + correction))
            brake_error = abs(used_brake - brake_target) / radius
            maximum = max(maximum, force_error)
            maximum_brake = max(maximum_brake, brake_error)
            completed.append(replace(local_steps[i], omega=wheel_omega, relative_omega=relative_omega,
                                     vx=vx, vy=vy, body_omega=body_omega, kappa=kappa, alpha=alpha,
                                     residual=max(force_error, brake_error),
                                     mode=mode if frame.load > 0 else "airborne",
                                     deformation_x=elastic[0], deformation_y=elastic[1],
                                     patch_kappa=patch_kappa, patch_alpha=patch_alpha,
                                     elastic_energy=energy, material_dissipation=material,
                                     road_dissipation=road, elastic_numerical_dissipation=numerical,
                                     deformation_rate_x=rate[0], deformation_rate_y=rate[1],
                                     gyro_torque=gyro[i], steering_torque=steering_torques[i]))
        return tuple(completed), maximum, maximum_brake

    local_steps = [None] * 4
    for iteration in range(20):
        bearing = None
        if rotor:
            _velocity, shared_angular = body_state()
            speeds = tuple(omega[i] + dt * (drives[i] - forces[i][2] - radii[i] * forces[i][0]) / inertia
                           for i in range(4))
            torques = bearing_torques(axes, speeds, inertia, shared_angular)
            bearing = tuple(sum(torque[a] for torque in torques) for a in range(3))
        order = range(4) if iteration % 2 == 0 else range(3, -1, -1)
        for i in order:
            frame = frames[i]
            known_velocity, known_angular = body_state(exclude=i, bearing=bearing)
            point_speed = tuple(known_velocity[a] + cross(known_angular, frame.point)[a] for a in range(3))
            step = advance_wheel(omega[i], longitudinal_speed(known_velocity, known_angular, frame),
                                 dot(point_speed, frame.axle), dot(known_angular, axes[i]), drives[i], brakes[i], frame.load,
                                 frame.mu, frame.mobility, dt, configurations[i], deformations[i],
                                 force_tolerance=.0001, rolling_contact=rolling_contacts[i],
                                 force_initial=forces[i][:2], rolling_radius=radii[i])
            forces[i] = (step.fx, step.fy, step.brake_torque)
            local_steps[i] = step
        completed, error, brake_error = completed_steps()
        if error < .001 and brake_error < 1e-9:
            return completed
    raise ArithmeticError(f"四轮共同末速度积分超过20次迭代：接点 {error:.6g} N，制动等效 {brake_error:.6g} N")
