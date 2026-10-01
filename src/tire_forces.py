"""简化 Magic Formula 纵横向联合滑移力。"""

import math

from tire_properties import tire_grip, tire_stiffness
from vehicle_config import CAR


def slip_state(vx, vy, omega, radius, config=CAR):
    denominator = max(abs(vx), config.slip_speed)
    kappa = (radius * omega - vx) / denominator
    alpha = math.atan2(vy, denominator)
    return kappa, alpha


def tire_force(kappa, alpha, normal_load, mu, config=CAR):
    if normal_load == 0:
        return 0.0, 0.0

    grip = tire_grip(normal_load, mu, config)
    cx, cy = tire_stiffness(normal_load, config)
    return combined_force(kappa, alpha, grip, cx, cy, config.tire_shape, config.tire_curvature)


def combined_force(kappa, alpha, grip, cx, cy, shape, curvature):
    """隐式轮积分在一次求解中复用固定轮荷特性，避免每次残差重复计算幂律。"""
    if grip == 0:
        return 0.0, 0.0
    qx = cx * kappa
    qy = -cy * math.tan(alpha)
    qnorm = math.hypot(qx, qy)
    if qnorm == 0:
        return 0.0, 0.0

    n = qnorm / (shape * grip)
    force_magnitude = grip * math.sin(
        shape * math.atan(n - curvature * (n - math.atan(n)))
    )
    return force_magnitude * qx / qnorm, force_magnitude * qy / qnorm
