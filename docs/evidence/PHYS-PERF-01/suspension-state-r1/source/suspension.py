"""射线悬架的真实硬件单位与原生参数边界。"""

from dataclasses import dataclass

from mechanical_kernels import dot, solve_lu, suspension_contact_state

from rotor_dynamics import cross

_solve = solve_lu


def native_coefficients(config, wheel_index, mass):
    """Bullet最终乘实际车身质量；SI硬件在质量变化时保持自身数值。"""
    if config.suspension_si_enabled:
        return (config.suspension_spring_rates[wheel_index] / mass,
                config.suspension_compression_damping[wheel_index] / mass,
                config.suspension_extension_damping[wheel_index] / mass)
    return config.suspension_stiffness, config.suspension_compression, config.suspension_relaxation


def contact_gradient(normal, direction, arm, *, minimum_alignment=.1):
    """实际射线长度的速度雅可比；近掠射线不伪造放大的共轭支撑。"""
    alignment = -dot(normal, direction)
    if alignment <= minimum_alignment:
        return None
    return tuple(n / alignment for n in normal) + tuple(v / alignment for v in cross(arm, normal))


def stiffness_matrix(rates, bars):
    """U=Σk*x²/2+Σkb*(x左−x右)²/2，x为实际悬架压缩量。"""
    matrix = [[rates[i] if i == j else 0. for j in range(4)] for i in range(4)]
    for left, bar in zip((0, 2), bars):
        matrix[left][left] += bar
        matrix[left + 1][left + 1] += bar
        matrix[left][left + 1] -= bar
        matrix[left + 1][left] -= bar
    return matrix


def elastic_terms(compression, rates, bars, stops, travel):
    spring = sum(k * x * x / 2 for k, x in zip(rates, compression))
    bar = tuple(k * (compression[i] - compression[i + 1]) ** 2 / 2
                for i, k in zip((0, 2), bars))
    excess = tuple(x - max(-travel, min(travel, x)) for x in compression)
    stop = sum(k * e * e / 2 for k, e in zip(stops, excess))
    matrix = stiffness_matrix(rates, bars)
    force = tuple(dot(row, compression) + k * e for row, k, e in zip(matrix, stops, excess))
    return spring, bar, stop, force



@dataclass(frozen=True)
class SuspensionStep:
    compression: tuple
    compression_rate: tuple
    axial_force: tuple
    raw_axial_force: tuple
    spring_energy: float
    bar_energy: tuple
    stop_energy: float
    damping_dissipation: float
    elastic_numerical_dissipation: float
    body_numerical_dissipation: float
    contact_offset_work: float
    energy_residual: float
    body_work: float = 0.


@dataclass(frozen=True)
class SuspensionInput:
    """接触切平面/材料初值；kinematics=None明确指定台架的线性雅可比。"""
    compression: tuple
    geometry: tuple
    gradients: tuple
    touching: tuple
    alignment: tuple
    config: object
    kinematics: tuple | None = None
    angular_damping: float = 0.


def shared_suspension(system, velocity, angular, dt, *, mobility=None, forces=(0.,) * 4):
    """由共同末速度求硬件反力；mobility仅用于法向块的隐式预条件。"""
    mobility = ((0.,) * 4,) * 4 if mobility is None else mobility
    speeds = tuple(dot(g, tuple(velocity) + tuple(angular)) - dt * dot(row, forces)
                   for g, row in zip(system.gradients, mobility))
    config = system.config
    return advance_suspension(system.compression, speeds, mobility, system.touching,
        config.suspension_spring_rates, config.suspension_compression_damping,
        config.suspension_extension_damping, config.suspension_antiroll_rates,
        config.suspension_stop_rates, config.suspension_travel, dt, geometry=system.geometry)


@dataclass(frozen=True)
class SuspensionState:
    step: SuspensionStep | None = None
    normal_force: tuple = (0.,) * 4
    contact_dot: tuple = (None,) * 4
    candidate_contact: tuple = (False,) * 4
    sampled_compression: tuple = (0.,) * 4
    geometry_work: float = 0.
    linear_impulse: tuple = (0., 0., 0.)
    angular_impulse: tuple = (0., 0., 0.)
    force_tick: int = 0
    contact_compression: tuple = (0.,) * 4
    initialization_energy: float = 0.
    substeps: tuple = ()
    force_gradients: tuple = ()


def advance_suspension(compression, extension_speed, mobility, touching,
                       rates, compression_damping, extension_damping, bars,
                       stops, travel, dt, *, geometry=None):
    """四轮共用一个车身末速度；离地的无质量轮由弹簧/阻尼平衡释放行程。

    mobility=A M⁻¹ Aᵀ，A将车身速度映射为轴向伸张速率。
    接地轴向力非负，弹簧/止挡反力始终为同一势能的梯度。
    geometry为射线接触约束位置，离地轮的材料状态不会随候选射线重设。
    """
    stiffness = stiffness_matrix(rates, bars)
    geometry = compression if geometry is None else geometry
    end, forces, raw, damping = suspension_contact_state(
        compression, extension_speed, mobility, touching, stiffness,
        compression_damping, extension_damping, stops, travel, dt, geometry)
    delta = tuple(end[i] - compression[i] for i in range(4))
    initial = elastic_terms(compression, rates, bars, stops, travel)
    spring, bar, stop, elastic_force = elastic_terms(end, rates, bars, stops, travel)
    energy_change = spring + sum(bar) + stop - initial[0] - sum(initial[1]) - initial[2]
    damping_loss = sum(c * dx * dx / dt for c, dx in zip(damping, delta))
    elastic_loss = dot(elastic_force, delta) - energy_change
    body_loss = dt * dt * sum(forces[i] * dot(mobility[i], forces) for i in range(4)) / 2
    offset_work = dot(forces, tuple(geometry[i] - compression[i] for i in range(4)))
    kinetic_change = dt * dot(forces, extension_speed) + body_loss
    residual = kinetic_change + energy_change + damping_loss + elastic_loss + body_loss - offset_work
    return SuspensionStep(end, tuple(dx / dt for dx in delta), forces, raw, spring, bar, stop,
                          damping_loss, elastic_loss, body_loss, offset_work, residual,
                          kinetic_change + body_loss)
