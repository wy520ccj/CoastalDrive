"""射线悬架的真实硬件单位与原生参数边界。"""


def native_coefficients(config, wheel_index, mass):
    """Bullet最终乘实际车身质量；SI硬件在质量变化时保持自身数值。"""
    if config.suspension_si_enabled:
        return (config.suspension_spring_rates[wheel_index] / mass,
                config.suspension_compression_damping[wheel_index] / mass,
                config.suspension_extension_damping[wheel_index] / mass)
    return config.suspension_stiffness, config.suspension_compression, config.suspension_relaxation
