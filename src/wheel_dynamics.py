"""车轮转动与刚体接点速度的隐式联合滑移积分。"""

import math
from dataclasses import dataclass

from tire_compliance import contact_force, contact_jacobian, energy_terms
from tire_forces import combined_force, slip_state
from tire_properties import tire_grip, tire_stiffness
from vehicle_config import CAR


@dataclass(frozen=True)
class Mobility:
    """车体三个广义速度(vx轮心、vy接点、轴向角速)的对称逆质量阵。"""

    xx: float
    xy: float
    xt: float
    yy: float
    yt: float
    tt: float


@dataclass(frozen=True)
class WheelStep:
    omega: float
    relative_omega: float
    vx: float
    vy: float
    body_omega: float
    kappa: float
    alpha: float
    fx: float
    fy: float
    brake_torque: float
    residual: float
    mode: str
    deformation_x: float = 0.0
    deformation_y: float = 0.0
    patch_kappa: float | None = None
    patch_alpha: float | None = None
    elastic_energy: float = 0.0
    material_dissipation: float = 0.0
    road_dissipation: float = 0.0
    elastic_numerical_dissipation: float = 0.0
    deformation_rate_x: float = 0.0
    deformation_rate_y: float = 0.0


def advance_wheel(omega, vx, vy, body_omega, drive, brake, load, mu, mobility, dt,
                  config=CAR, deformation=(0.0, 0.0), force_tolerance=.001, rolling_contact=None,
                  force_initial=(0.0, 0.0)):
    """同时求解接地力、轮速和干式制动反力；车体由调用方施加同一冲量。"""
    radius, inertia = config.wheel_radius, config.wheel_inertia
    m = mobility
    grip = tire_grip(load, mu, config)
    cx, cy = tire_stiffness(load, config)

    def state(fx, fy):
        free_omega = omega + dt * (drive - radius * fx) / inertia
        free_body = body_omega + dt * (m.xt * fx + m.yt * fy + m.tt * drive)
        # 干式制动耗散轮与车体之间的相对转动；容量内静止，容量外滑动。
        demand = (free_omega + free_body) / (dt * (1 / inertia + m.tt))
        used_brake = max(-brake, min(brake, demand))
        reaction = drive - used_brake
        new_omega = omega + dt * (reaction - radius * fx) / inertia
        new_body = body_omega + dt * (m.xt * fx + m.yt * fy + m.tt * reaction)
        new_vx = vx + dt * (m.xx * fx + m.xy * fy + m.xt * reaction)
        new_vy = vy + dt * (m.xy * fx + m.yy * fy + m.yt * reaction)
        kappa, alpha = slip_state(new_vx, new_vy, new_omega, radius, config)
        return new_omega, new_vx, new_vy, new_body, kappa, alpha, used_brake

    def residual(fx, fy):
        values = state(fx, fy)
        if config.tire_compliance:
            target, *_rest = compliant_state(fx, fy, values)
            target_x, target_y = target
        else:
            target_x, target_y = combined_force(values[4], values[5], grip, cx, cy,
                                              config.tire_shape, config.tire_curvature)
        return fx - target_x, fy - target_y

    def compliant_state(fx, fy, values):
        return contact_force((fx, fy), deformation, (radius * values[0] - values[1], -values[2]),
                             max(abs(values[1]), config.slip_speed),
                             (max(abs(vx), abs(radius * omega)) >= config.static_contact_speed
                              if rolling_contact is None else rolling_contact),
                             grip, cx, cy, dt, config.tire_contact_stiffness,
                             config.tire_contact_damping, config.tire_shape, config.tire_curvature)

    def compliant_jacobian(fx, fy):
        values = state(fx, fy)
        brake_gradient = (((m.xt - radius / inertia) / (1 / inertia + m.tt),
                           m.yt / (1 / inertia + m.tt))
                          if abs(values[6]) < brake else (0.0, 0.0))
        bx, by = brake_gradient
        slip_jacobian = (
            (-dt * (radius**2 / inertia + m.xx) + dt * (m.xt - radius / inertia) * bx,
             -dt * m.xy + dt * (m.xt - radius / inertia) * by),
            (-dt * m.xy + dt * m.yt * bx, -dt * m.yy + dt * m.yt * by),
        )
        denominator_gradient = (0.0, 0.0)
        if abs(values[1]) > config.slip_speed:
            direction = math.copysign(1.0, values[1])
            denominator_gradient = (direction * dt * (m.xx - m.xt * bx),
                                    direction * dt * (m.xy - m.xt * by))
        target = contact_jacobian(
            (fx, fy), deformation, (radius * values[0] - values[1], -values[2]),
            slip_jacobian, max(abs(values[1]), config.slip_speed), denominator_gradient,
            (max(abs(vx), abs(radius * omega)) >= config.static_contact_speed
             if rolling_contact is None else rolling_contact),
            grip, cx, cy, dt, config.tire_contact_stiffness, config.tire_contact_damping,
            config.tire_shape, config.tire_curvature)
        return (1 - target[0][0], -target[0][1], -target[1][0], 1 - target[1][1])

    if config.tire_compliance:
        fx, fy, error = _solve_force(residual, tolerance=force_tolerance, initial=force_initial,
                                    jacobian=compliant_jacobian)
        values = state(fx, fy)
        _target, elastic, rate, patch, kappa, alpha, mode = compliant_state(fx, fy, values)
        if load == 0:
            mode = "airborne"
        energy, material, road, numerical = energy_terms(
            (fx, fy), deformation, elastic, rate, patch, dt,
            config.tire_contact_stiffness, config.tire_contact_damping)
        return WheelStep(values[0], values[0] + values[3], values[1], values[2], values[3],
                         values[4], values[5], fx, fy, values[6], error, mode,
                         *elastic, kappa, alpha, energy, material, road, numerical, *rate)

    mode = "magic-formula" if load > 0 else "airborne"
    if load > 0 and max(abs(vx), abs(vy), abs(radius * omega)) < config.static_contact_speed:
        def sticking_residual(fx, fy):
            values = state(fx, fy)
            # 无滑移滚动/静止约束；速度残差按接点有效逆质量换算为N。
            return ((values[1] - radius * values[0]) / (dt * (m.xx + radius**2 / inertia)),
                    values[2] / (dt * m.yy))

        fx, fy, error = _solve_force(sticking_residual)
        # 静摩擦只在摩擦圆内成立；所需力超出预算时进入实际滑动曲线。
        if math.hypot(fx, fy) <= grip:
            values = state(fx, fy)
            return WheelStep(
                values[0], values[0] + values[3], values[1], values[2], values[3],
                values[4], values[5], fx, fy, values[6], error, "sticking",
            )
    fx, fy, error = _solve_force(residual)
    values = state(fx, fy)
    return WheelStep(
        values[0], values[0] + values[3], values[1], values[2], values[3],
        values[4], values[5], fx, fy, values[6], error, mode,
    )


def _solve_force(residual, tolerance=.001, initial=(0.0, 0.0), jacobian=None):
    """双精度牛顿求解Fx/Fy；不收敛明确报错，不切换到另一套隐含物理。"""
    fx, fy = initial
    epsilon = 0.01
    for _ in range(20):
        rx, ry = residual(fx, fy)
        error = math.hypot(rx, ry)
        if error < tolerance:
            return fx, fy, error
        if jacobian is None:
            px, py = residual(fx + epsilon, fy)
            nx, ny = residual(fx - epsilon, fy)
            a, c = (px - nx) / (2 * epsilon), (py - ny) / (2 * epsilon)
            px, py = residual(fx, fy + epsilon)
            nx, ny = residual(fx, fy - epsilon)
            b, d = (px - nx) / (2 * epsilon), (py - ny) / (2 * epsilon)
        else:
            a, b, c, d = jacobian(fx, fy)
        determinant = a * d - b * c
        dx, dy = (d * rx - b * ry) / determinant, (a * ry - c * rx) / determinant
        for exponent in range(12):
            scale = 0.5 ** exponent
            candidate_x, candidate_y = fx - scale * dx, fy - scale * dy
            new_rx, new_ry = residual(candidate_x, candidate_y)
            if math.hypot(new_rx, new_ry) < error:
                fx, fy = candidate_x, candidate_y
                break
        else:
            raise ArithmeticError(f"轮胎隐式积分不收敛：残差 {error:.6g} N")
    raise ArithmeticError(f"轮胎隐式积分超过20次迭代：残差 {error:.6g} N")
