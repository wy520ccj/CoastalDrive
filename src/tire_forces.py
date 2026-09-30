"""简化 Magic Formula 纵横向联合滑移力。"""

import math

from vehicle_config import CAR


def slip_state(vx, vy, omega, radius, config=CAR):
    denominator = max(abs(vx), config.slip_speed)
    kappa = (radius * omega - vx) / denominator
    alpha = math.atan2(vy, denominator)
    return kappa, alpha


def tire_force(kappa, alpha, normal_load, mu, config=CAR):
    if normal_load == 0:
        return 0.0, 0.0

    nominal_load = config.mass * 9.81 / 4
    stiffness_scale = normal_load / nominal_load
    qx = config.longitudinal_stiffness * stiffness_scale * kappa
    qy = -config.lateral_stiffness * stiffness_scale * math.tan(alpha)
    qnorm = math.hypot(qx, qy)
    if qnorm == 0:
        return 0.0, 0.0

    budget = mu * normal_load
    n = qnorm / (config.tire_shape * budget)
    force_magnitude = budget * math.sin(
        config.tire_shape
        * math.atan(n - config.tire_curvature * (n - math.atan(n)))
    )
    return force_magnitude * qx / qnorm, force_magnitude * qy / qnorm
