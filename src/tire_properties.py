"""标称轮荷下的峰值与刚度；相同特性供轮胎、静摩擦和电子预测使用。"""


def tire_grip(normal_load, mu, config):
    if normal_load == 0:
        return 0.0
    ratio = normal_load / config.tire_reference_load
    return mu * normal_load * ratio ** (config.tire_peak_load_exponent - 1)


def tire_stiffness(normal_load, config):
    ratio = normal_load / config.tire_reference_load
    return (config.longitudinal_stiffness * ratio ** config.longitudinal_load_exponent,
            config.lateral_stiffness * ratio ** config.lateral_load_exponent)


def tire_camber_stiffness(normal_load, config) -> float:
    """按轮荷缩放外倾刚度，离地时刚度为零。"""
    if normal_load == 0.0 or config.camber_stiffness == 0.0:
        return 0.0
    return config.camber_stiffness * (normal_load / config.tire_reference_load) ** config.camber_load_exponent
