"""射线悬架的真实硬件单位与原生参数边界。"""

import math
from dataclasses import dataclass

from mechanical_kernels import dot

from rotor_dynamics import cross


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


def _solve(matrix, rhs):
    """小型稠密LU及残差修正，保持大止挡反力下的绝对机械精度。"""
    rows = [list(row) for row in matrix]
    n = len(rows)
    order = list(range(n))
    for col in range(n):
        pivot = max(range(col, n), key=lambda i: abs(rows[i][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        order[col], order[pivot] = order[pivot], order[col]
        for i in range(col + 1, n):
            factor = rows[i][col] / rows[col][col]
            rows[i][col] = factor
            for j in range(col + 1, n):
                rows[i][j] -= factor * rows[col][j]

    def substitute(values):
        result = [values[i] for i in order]
        for i in range(n):
            result[i] = math.fsum([result[i], *(-rows[i][j] * result[j] for j in range(i))])
        for i in range(n - 1, -1, -1):
            result[i] = math.fsum([result[i], *(-rows[i][j] * result[j] for j in range(i + 1, n))]) / rows[i][i]
        return result

    result = substitute(rhs)
    residual = tuple(math.fsum([rhs[i], *(-value * x for value, x in zip(row, result))])
                     for i, row in enumerate(matrix))
    correction = substitute(residual)
    return tuple(x + dx for x, dx in zip(result, correction))


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
    modes = [1 if contact else 0 for contact in touching]  # 0自由，1弹性接触。
    damping = [compression_damping[i] if extension_speed[i] < 0 else extension_damping[i]
               for i in range(4)]
    stop_bounds = [travel if x > travel else -travel if x < -travel else None for x in compression]
    for _iteration in range(64):
        system = [row[:] for row in stiffness]
        rhs = []
        for i in range(4):
            system[i][i] += damping[i] / dt + (stops[i] if stop_bounds[i] is not None else 0.)
            rhs.append(damping[i] * compression[i] / dt
                       + (stops[i] * stop_bounds[i] if stop_bounds[i] is not None else 0.))
        equations, values = [], []
        for i, mode in enumerate(modes):
            if mode == 0:
                equations.append(system[i] + [0.] * 4)
                values.append(rhs[i])
                equations.append([0.] * 4 + [1. if i == j else 0. for j in range(4)])
                values.append(0.)
            else:
                equations.append([1. if i == j else 0. for j in range(4)]
                                 + [dt * dt * value for value in mobility[i]])
                values.append(geometry[i] - dt * extension_speed[i])
                equations.append([-v for v in system[i]]
                                 + [1. if i == j else 0. for j in range(4)])
                values.append(-rhs[i])
        solution = _solve(equations, values)
        end, forces = solution[:4], solution[4:]
        raw = tuple(math.fsum([*(value*x for value,x in zip(stiffness[i],end)),
                              damping[i] * (end[i] - compression[i]) / dt,
                              stops[i] * (end[i] - stop_bounds[i]) if stop_bounds[i] is not None else 0.])
                    for i in range(4))
        next_modes = modes[:]
        for i, mode in enumerate(modes):
            target = geometry[i] - dt * extension_speed[i] - dt * dt * dot(mobility[i], forces)
            if mode == 0 and touching[i] and end[i] < target - 1e-10:
                next_modes[i] = 1
            elif mode == 1 and forces[i] < -1e-7:
                next_modes[i] = 0
        next_damping = [compression_damping[i] if end[i] >= compression[i] else extension_damping[i]
                        for i in range(4)]
        next_stops = [travel if x > travel else -travel if x < -travel else None for x in end]
        if next_modes == modes and next_damping == damping and next_stops == stop_bounds:
            if all(value == 0. for row in mobility for value in row):
                # 末速度直接给定时，在未舍入行程上求本构力；大止挡刚度不放大行程末位量化。
                raw = tuple(math.fsum([*((math.fma(-k*dt, extension_speed[j], k*geometry[j])
                                          if modes[j] else k*end[j]) for j,k in enumerate(stiffness[i])),
                                       math.fma(-damping[i], extension_speed[i],
                                                damping[i] * (geometry[i] - compression[i]) / dt),
                                       math.fma(-stops[i]*dt, extension_speed[i],
                                                stops[i] * (geometry[i] - stop_bounds[i]))
                                           if stop_bounds[i] is not None else 0.])
                            if modes[i] else raw[i] for i in range(4))
                forces = tuple(raw[i] if modes[i] else 0. for i in range(4))
            break
        modes, damping, stop_bounds = next_modes, next_damping, next_stops
    else:
        raise ArithmeticError("悬架接触/阻尼/止挡活动集未收敛")
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
