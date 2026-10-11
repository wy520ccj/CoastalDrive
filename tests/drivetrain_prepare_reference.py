"""c299620机械准备数值参考；保留旧式约束、投影与运算顺序供独立对照。"""

from mechanical_kernels import dot, mass_coefficients, mass_response_prepared, rotor_coefficients

from driveline_inertia import active_inertias, inertia_projections, rotor_gradients
from rotor_dynamics import cross
from shaft_transmission import shaft_gradients


def reference_prepare(angular, omega, engine_omega, frames, engine_torque, config, ratio,
                      inverse_inertia, dt, engine_axis, engine_inertia, steering_torques, engine_drag,
                      shaft_omega, shaft_inertia, shaft_axis, downstream_omega, downstream_inertias, downstream_axes):
    wheel_inertia = config.wheel_inertia
    shaft = shaft_omega is not None
    wheel_start, dimensions = (5, 9) if shaft else (4, 8)
    initial = tuple(angular) + (engine_omega,) + ((shaft_omega,) if shaft else ()) + tuple(omega)
    rotor = config.wheel_rotor_transport
    axes = tuple(tuple(frame.spin_axis if rotor else frame.axle) for frame in frames)
    radii = tuple(frame.rolling_radius if rotor else config.wheel_radius for frame in frames)
    moments_x = tuple(frame.moment_x if rotor else tuple(
        cross(frame.point, frame.tangent)[a] - radii[i] * axes[i][a] for a in range(3))
        for i, frame in enumerate(frames))
    moments_y = tuple(cross(frame.point, frame.axle) for frame in frames)
    engine_gradient = tuple(-value for value in engine_axis) + (1.,) + (0.,) * (dimensions - 4)
    # 默认后驱保留原运算次序；前轮转向后的真实机械轴也参与壳体反力。
    if config.front_drive_share == 0:
        drive_axis = tuple(ratio / 2 * (axes[2][a] + axes[3][a]) for a in range(3))
    else:
        drive_axis = tuple(ratio * sum(weight * axes[i][a]
                           for i, weight in enumerate(config.drive_weights)) for a in range(3))
    wheel_ratios = tuple(ratio * weight for weight in config.drive_weights)
    clutch_gradient = tuple(-engine_axis[a] - drive_axis[a] for a in range(3)) + (1.,) + tuple(-r for r in wheel_ratios)
    gear_gradient = drive_axis + (0.,) + wheel_ratios
    shaft_gear_gradient = None
    if shaft:
        clutch_gradient, shaft_gear_gradient, gear_gradient = shaft_gradients(
            engine_axis, shaft_axis, axes, config.drive_weights, ratio)
    rotor_zeros = (0.,) * (wheel_start - 3)
    brake_gradients = tuple(axes[i] + rotor_zeros + tuple(float(j == i) for j in range(4)) for i in range(4))
    longitudinal = tuple(moments_x[i] + rotor_zeros + tuple(-radii[i] if j == i else 0. for j in range(4)) for i in range(4))
    lateral = tuple(moment + (0.,) * (dimensions - 3) for moment in moments_y)

    # 逆惯量及硬件在本次共同求解中固定，下一物理子步重新读取并构造。
    base_coefficients = mass_coefficients(inverse_inertia, engine_inertia, shaft_inertia if shaft else None,
                                          wheel_inertia, (), 0., None)

    def base_inverse_mass(vector):
        return mass_response_prepared(base_coefficients, vector)

    downstream = bool(downstream_omega)
    inertias, gradients, downstream_projections = (), (), ()
    if downstream:
        inertias = active_inertias(downstream_inertias, config.front_drive_share)
        gradients = rotor_gradients(downstream_axes, axes, config.front_drive_share, config.final_drive, wheel_start)
        downstream_projections = inertia_projections(base_inverse_mass, gradients, inertias)

    inverse_coefficients = mass_coefficients(inverse_inertia, engine_inertia, shaft_inertia if shaft else None,
                                             wheel_inertia, downstream_projections, 0., None)

    def inverse_mass(vector):
        return mass_response_prepared(inverse_coefficients, vector)

    engine_response = inverse_mass(engine_gradient)
    drag_factor = dt * engine_drag / (1 + dt * engine_drag * dot(engine_gradient, engine_response))

    mobility_coefficients = mass_coefficients(inverse_inertia, engine_inertia, shaft_inertia if shaft else None,
                                              wheel_inertia, downstream_projections, drag_factor, engine_response)

    steering = tuple(sum(torque[a] for torque in steering_torques) for a in range(3))
    free_base = tuple(initial[a] + dt * engine_torque * engine_response[a]
                      + (dt * dot(inverse_inertia[a], steering) if a < 3 else 0.) for a in range(dimensions))
    if downstream:
        # 上一实体轴速来自真实末状态；轴约束变化时不能重算旧速抹掉储能。
        momentum = tuple(sum(j * g[a] * (old - dot(g, initial))
                             for j, g, old in zip(inertias, gradients, downstream_omega)) for a in range(dimensions))
        initial_response = inverse_mass(momentum)
        steering_response = inverse_mass(steering + (0.,) * (dimensions - 3))
        free_base = tuple(initial[a] + initial_response[a] + dt * (engine_torque * engine_response[a]
                          + steering_response[a]) for a in range(dimensions))

    projection = drag_factor * dot(engine_gradient, free_base)
    free_base = tuple(free_base[a] - projection * engine_response[a] for a in range(dimensions))

    spin_coefficients = rotor_coefficients(engine_inertia, engine_axis, wheel_inertia, axes, rotor,
        shaft_inertia if shaft else None, shaft_axis, inertias, gradients, downstream_axes)
    return (initial, axes, radii, moments_x, moments_y, engine_gradient, clutch_gradient,
            gear_gradient, shaft_gear_gradient, brake_gradients, longitudinal, lateral,
            inertias, gradients, mobility_coefficients, spin_coefficients, free_base)
