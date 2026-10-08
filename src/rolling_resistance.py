"""道路滚动阻力矩；低速连续，耗散按车轮对静态道路的实际转速计算。"""


def rolling_torques(frames, radii, spins, coefficients, transition_speed, *, loads=None):
    """正值表示阻碍正轮速；轮胎的物理正转轴为机械右轴的负向。"""
    actual_loads = tuple(frame.load for frame in frames) if loads is None else loads
    return tuple(coefficient * load * radius**2 * spin
                 / max(abs(radius*spin), transition_speed) if frame.supported else 0.
                 for frame,load,radius,spin,coefficient in zip(frames,actual_loads,radii,spins,coefficients))
