"""标称轮荷下的峰值与刚度；相同特性供轮胎、静摩擦和电子预测使用。"""


def tire_grip(normal_load, mu, config):
    if normal_load == 0:
        return 0.0
    ratio = normal_load / (config.mass * 9.81 / 4)
    return mu * normal_load * ratio ** (config.tire_peak_load_exponent - 1)


def tire_stiffness(normal_load, config):
    ratio = normal_load / (config.mass * 9.81 / 4)
    return (config.longitudinal_stiffness * ratio ** config.longitudinal_load_exponent,
            config.lateral_stiffness * ratio ** config.lateral_load_exponent)
