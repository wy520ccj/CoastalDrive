"""简化 Magic Formula 纵横向联合滑移力。"""

import math

from mechanical_kernels import tire_combined_force

from tire_properties import tire_camber_stiffness, tire_grip, tire_stiffness
from vehicle_config import CAR


def slip_state(vx, vy, omega, radius, config=CAR):
    denominator = max(abs(vx), config.slip_speed)
    kappa = (radius * omega - vx) / denominator
    alpha = math.atan2(vy, denominator)
    return kappa, alpha


def tire_force(kappa, alpha, normal_load, mu, config=CAR, *, gamma_rad=0.0):
    if normal_load == 0:
        return 0.0, 0.0

    grip = tire_grip(normal_load, mu, config)
    cx, cy = tire_stiffness(normal_load, config)
    if gamma_rad != 0.0 and config.camber_stiffness != 0.0:
        return combined_force(kappa, alpha, grip, cx, cy, config.tire_shape, config.tire_curvature,
                              cgamma=tire_camber_stiffness(normal_load, config), gamma_rad=gamma_rad)
    return combined_force(kappa, alpha, grip, cx, cy, config.tire_shape, config.tire_curvature)


def combined_force(kappa, alpha, grip, cx, cy, shape, curvature, *, cgamma=0.0, gamma_rad=0.0):
    """隐式轮积分在一次求解中复用固定轮荷特性，避免每次残差重复计算幂律。"""
    if cgamma != 0.0 and gamma_rad != 0.0:
        return tire_combined_force(kappa, alpha, grip, cx, cy, shape, curvature, math.hypot,
                                   cgamma * math.sin(gamma_rad))
    return tire_combined_force(kappa, alpha, grip, cx, cy, shape, curvature, math.hypot)
