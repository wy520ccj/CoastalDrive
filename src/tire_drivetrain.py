"""四轮接触、曲轴/输入轴、有限离合与制动的共同末状态。"""

import math
from dataclasses import dataclass
from struct import pack

from mechanical_kernels import (
    dot,
    known_state,
    load_coefficients,
    loaded_wheel_force_solution,
    mass_coefficients,
    mass_response_prepared,
    rotor_coefficients,
    rotor_spin_prepared,
    shared_load_solution,
    shared_map_coefficients,
    suspension_coefficients,
    suspension_forces,
    suspension_projection,
    suspension_residuals,
    wheel_brake_correction,
    wheel_contact_state,
    wheel_free_state,
    wheel_load_prepared,
    wheel_map_coefficients,
    wheel_map_derivatives,
    wheel_map_state,
    wheel_residuals,
)

from differential import (
    differential_branches,
    differential_gradients,
    differential_torques,
    torque_bias_capacities,
    viscous_projection,
)
from driveline_inertia import active_inertias, inertia_projections, rotor_gradients
from rolling_resistance import rolling_torques
from rotor_dynamics import bearing_torques, cross
from shaft_transmission import (
    shaft_brake_plans,
    shaft_gradients,
    synchronizer_brake_plans,
)
from suspension import SuspensionInput, SuspensionStep, _solve, shared_suspension
from suspension_kinematics import finite_contact_system
from tire_compliance import contact_jacobian, energy_terms
from tire_forces import combined_force, slip_state
from tire_properties import tire_grip, tire_stiffness
from transmission_ports import (
    PORT_TOLERANCE,
    clutch_brake_plans,
    clutch_brake_state,
    transmission_state,
)
from wheel_dynamics import WheelStep, _solve_force, _solve_rolling_force


@dataclass(frozen=True)
class DrivetrainInput:
    """当前子步的机械输入；求解不提交车身冲量或修改车辆状态。"""

    values: tuple
    parameters: dict

    def solve(self):
        return advance_drivetrain(*self.values, **self.parameters)


def solve_drivetrain_stages(stages):
    """直接调用仍按原时序读状态、求解、提交；世界推进可在求解处暂停。"""
    try:
        request = next(stages)
    except StopIteration as finished:
        return finished.value
    while True:
        result = request.solve()
        try:
            request = stages.send(result)
        except StopIteration as finished:
            return finished.value


@dataclass(frozen=True)
class DrivetrainStep:
    """单次求解结果；速度供功/残差核对，调用方只向唯一Bullet车身提交冲量。"""

    wheels: tuple
    velocity: tuple
    angular: tuple
    engine_omega: float
    engine_relative_omega: float
    drive_torque: float
    clutch_torque: float
    clutch_slip: float
    gear_loss_torque: float
    gear_input_speed: float
    engine_body_torque: tuple
    engine_work: float
    engine_drag_heat: float
    clutch_heat: float
    gear_heat: float
    sweeps: int
    wheel_drive_torques: tuple
    differential_torques: tuple
    differential_slips: tuple
    differential_heat: tuple
    shaft_omega: float | None = None
    shaft_relative_omega: float | None = None
    gear_reaction: float = 0.
    synchronizer_slip: float = 0.
    synchronizer_heat: float = 0.
    shaft_body_torque: tuple = (0., 0., 0.)
    downstream_omega: tuple = ()
    downstream_body_torque: tuple = (0., 0., 0.)
    downstream_wheel_torques: tuple = (0.,) * 4
    downstream_kinetic_energy: tuple = ()
    downstream_numerical_dissipation: tuple = ()
    suspension: SuspensionStep | None = None
    normal_residual: float = 0.
    suspension_system: SuspensionInput | None = None


def advance_drivetrain(velocity, angular, omega, engine_omega, frames, deformations,
                       engine_torque, capacity, ratio, brakes, config, rear_config, dt, *,
                       inverse_inertia, engine_inertia, engine_axis, engine_drag, efficiency,
                       steering_torques=((0., 0., 0.),) * 4, force_initial=((0., 0., 0.),) * 4,
                       shaft_omega=None, shaft_inertia=None, shaft_axis=None,
                       synchronizing=False, synchronizer_capacity=0.,
                       downstream_omega=(), downstream_inertias=(), downstream_axes=(),
                       suspension=None, rolling_coefficients=(0.,) * 4):
    """九维q含实体输入轴；未指定输入轴时保留原八维机制供旧/新A/B。"""
    mass, wheel_inertia = config.mass, config.wheel_inertia
    shaft = shaft_omega is not None
    wheel_start, dimensions = (5, 9) if shaft else (4, 8)
    hard_gear = bool(ratio and not synchronizing) if shaft else bool(ratio)
    initial = tuple(angular) + (engine_omega,) + ((shaft_omega,) if shaft else ()) + tuple(omega)
    rolling_active = any(rolling_coefficients)
    road_torques = (0.,) * 4
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

    def mobility(vector):
        return mass_response_prepared(mobility_coefficients, vector)

    configurations = (config, config, rear_config, rear_config)
    tire_hardware = tuple((car.slip_speed, car.tire_contact_stiffness, car.tire_contact_damping,
                           car.tire_shape, car.tire_curvature) for car in configurations)
    wheel_loads = tuple(frame.load for frame in frames)
    wheel_supported = tuple(frame.supported for frame in frames)
    tire_compliance = tuple(car.tire_compliance for car in configurations)

    def load_parameters():
        # 轮荷刷新时重算本构参数，后续力/Jacobian试探共用同一组数值。
        return tuple((tire_grip(load, frame.mu, car), *tire_stiffness(load, car))
                     for load, frame, car in zip(wheel_loads, frames, configurations))

    contact_parameters = load_parameters()
    normal_forces = (0.,) * 4
    normal_responses, normal_mobility = (), ()
    reference_suspension = suspension
    if suspension is not None:
        hardware = suspension.config
        normal_coefficients = suspension_coefficients(suspension.compression, suspension.geometry,
            hardware.suspension_spring_rates, hardware.suspension_compression_damping,
            hardware.suspension_extension_damping, hardware.suspension_antiroll_rates,
            hardware.suspension_stop_rates, hardware.suspension_travel, dt)
    geometry_results = {}
    projection_results = {}

    def contact_system(end_velocity, end_angular):
        # 唯一世界在本advance内冻结；相同末速度的同一几何方程只计算一次。
        key = pack("6d", *end_velocity, *end_angular)
        if key not in geometry_results:
            geometry_results[key] = finite_contact_system(reference_suspension, end_velocity, end_angular, dt)
        return geometry_results[key]

    def normal_projection():
        nonlocal normal_responses, normal_mobility
        key = suspension.gradients
        if key in projection_results:
            normal_responses, normal_mobility = projection_results[key]
            return
        normal_responses, normal_mobility = suspension_projection(mobility_coefficients, suspension.gradients, mass)
        projection_results[key] = normal_responses, normal_mobility

    def normal_load_solution(end_velocity, end_angular, *, mobility=None, forces=(0.,) * 4):
        # 试探阶段只用反力；完整能量账在同一收敛末状态计算一次。
        return suspension_forces(normal_coefficients, suspension.gradients, end_velocity, end_angular,
                                 suspension.touching, mobility, forces)

    if suspension is not None:
        normal_projection()

    def normal_loads():
        nonlocal wheel_loads, contact_parameters
        # 支持几何在本次推进内固定，法向力只刷新四个实际轮荷。
        wheel_loads = tuple(force / alignment if frame.supported and contact and force > 0. else 0.
                       for frame, force, alignment, contact in
                       zip(frames, normal_forces, suspension.alignment, suspension.touching))
        contact_parameters = load_parameters()

    responses = tuple((mobility(longitudinal[i]), mobility(lateral[i]), mobility(brake_gradients[i])) for i in range(4))
    differential = differential_gradients(axes)
    if shaft:
        differential = tuple(g[:4] + (0.,) + g[4:] for g in differential)
    damping, limits = config.differential_damping, config.differential_capacity
    limited = any(c and limit for c, limit in zip(damping, limits))
    torque_bias = any(value > 1. for value in config.axle_torque_bias_ratios)
    active_limits, bias_ports = limits, (0., 0.)
    differential_responses = tuple(mobility(g) for g in differential) if torque_bias else ()
    branches = []
    for branch in differential_branches(differential, damping, limits, mobility, dt):
        projections = branch[0]
        mc = viscous_projection(mobility(clutch_gradient), projections)
        ml = viscous_projection(mobility(gear_gradient), projections)
        dcc, dcl, dll = dot(clutch_gradient, mc), dot(clutch_gradient, ml), dot(gear_gradient, ml)
        wheel_responses = tuple(tuple(viscous_projection(r, projections) for r in wheel) for wheel in responses)
        local_response = tuple(((dcc, dcl, dot(clutch_gradient, wheel_responses[i][2])),
                               (dcl, dll, dot(gear_gradient, wheel_responses[i][2])),
                               (dot(clutch_gradient, wheel_responses[i][2]), dot(gear_gradient, wheel_responses[i][2]),
                                dot(brake_gradients[i], wheel_responses[i][2]))) for i in range(4))
        shaft_data = None
        if shaft:
            mg = viscous_projection(mobility(shaft_gear_gradient), projections)
            port_gradients = (clutch_gradient, shaft_gear_gradient, gear_gradient) if hard_gear else (clutch_gradient, shaft_gear_gradient)
            port_responses = (mc, mg, ml) if hard_gear else (mc, mg)
            local_response = tuple(tuple(tuple(dot(g, r) for r in (*port_responses, wheel_responses[i][2]))
                                         for g in (*port_gradients, brake_gradients[i])) for i in range(4))
            if hard_gear:
                plans = tuple(shaft_brake_plans(local_response[i], capacity, brakes[i], efficiency) for i in range(4))
                shared_plans = shaft_brake_plans(local_response[0], capacity, 0., efficiency)
            else:
                plans = tuple(synchronizer_brake_plans(local_response[i], (capacity, synchronizer_capacity, brakes[i])) for i in range(4))
                shared_plans = synchronizer_brake_plans(local_response[0], (capacity, synchronizer_capacity, 0.))
            shaft_data = mg, shared_plans
        else:
            plans = (tuple(clutch_brake_plans(local_response[i], capacity, brakes[i], efficiency) for i in range(4))
                     if ratio else ((),) * 4)
        branches.append((branch, mc, ml, ((dcc, dcl), (dcl, dll)), wheel_responses, local_response, plans, shaft_data))
    warm_modes = [[None] * 4 for _ in branches]
    warm_branches = [0] * 4
    shared_branch = 0
    shared_port_index = None

    def branch_free(free, branch):
        if not limited:
            return free
        projected = viscous_projection(free, branch[0])
        offset = branch[1]
        if torque_bias:
            offset = (0.,) * dimensions
            for mode, limit, response in zip(branch[2], active_limits, differential_responses):
                if mode:
                    offset = tuple(offset[a] - dt * mode * limit * response[a] for a in range(dimensions))
            offset = viscous_projection(offset, branch[0])
        return tuple(projected[a] + offset[a] for a in range(dimensions))

    def bias_limits(state, gear_reaction, loss):
        # 限滑负载是实际齿轮输出减去实体轴储能反力，不读取路面μ或预设抓地分配。
        axial = tuple(j * (dot(g, state) - old) / dt for j, g, old in
                      zip(inertias, gradients, downstream_omega)) if downstream else (0., 0., 0.)
        output = ratio * (gear_reaction - loss)
        front = config.front_drive_share * output - config.final_drive * (config.front_drive_share * axial[0] + axial[1])
        rear = (1 - config.front_drive_share) * output - config.final_drive * ((1 - config.front_drive_share) * axial[0] + axial[2])
        return (*torque_bias_capacities(limits[:2], config.axle_torque_bias_ratios, (front, rear)), limits[2])

    forces = list(force_initial)
    modes = [None] * 4
    rolling = tuple(max(abs(dot(velocity, frame.tangent) + dot(angular, moments_x[i])),
                        abs(radii[i] * omega[i])) >= config.static_contact_speed for i, frame in enumerate(frames))
    static = tuple((wheel_loads[i] > 0 if suspension is None else suspension.touching[i]) and max(abs(dot(velocity, frame.tangent) + dot(angular, moments_x[i])),
                   abs(dot(velocity, frame.axle) + dot(angular, moments_y[i])), abs(radii[i] * omega[i]))
                   < config.static_contact_speed for i, frame in enumerate(frames))
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
    wheel_coefficients = load_coefficients(responses, tuple(frame.tangent for frame in frames),
                                          tuple(frame.axle for frame in frames), dt, mass, dimensions)

    def spin(state):
        return rotor_spin_prepared(spin_coefficients, state[:dimensions])

    def load_terms(exclude=None):
        # 法向响应会随末姿态刷新；当前力和梯度逐次传入，固定轮端矩阵只读复用。
        return wheel_load_prepared(wheel_coefficients, forces, velocity,
            normal_forces if suspension is not None else None, normal_responses,
            suspension.gradients if suspension is not None else None, exclude)

    def known(gyro, loads):
        return known_state(mobility_coefficients, free_base, gyro, loads, dt,
                           road_torques if rolling_active else None)

    # 固定机械分区只属于本次advance；法向力、当前轮荷与试探状态逐次传入。
    shared_map = (shared_map_coefficients(mobility_coefficients, spin_coefficients, free_base,
        tuple(branches), (clutch_gradient, shaft_gear_gradient, gear_gradient, brake_gradients[0])
        if hard_gear else (clutch_gradient, shaft_gear_gradient, brake_gradients[0]),
        differential, damping, limits, differential_responses, dt, capacity, efficiency,
        synchronizer_capacity, hard_gear, (radii, rolling_coefficients, config.rolling_transition_speed),
        (ratio, config.front_drive_share, config.final_drive, config.axle_torque_bias_ratios,
         inertias, gradients, tuple(downstream_omega))) if shaft else None)

    wheel_map = (wheel_map_coefficients(shared_map, wheel_coefficients, tuple(branches),
                                          brake_gradients, brakes) if shaft else None)

    def shared(guess):
        nonlocal shared_branch, shared_port_index, road_torques, active_limits, bias_ports
        if shaft:
            end, end_velocity, clutch, loss, gear_reaction, shared_branch, shared_port_index, road_torques, active_limits, bias_ports = shared_load_solution(
                wheel_map, guess, forces, velocity, normal_forces if suspension is not None else None,
                normal_responses, suspension.gradients if suspension is not None else None,
                wheel_loads, wheel_supported, shared_branch, bias_ports)
            return end, end_velocity, clutch, loss, gear_reaction
        loads = load_terms()
        def mapped(state):
            nonlocal shared_branch, shared_port_index, road_torques, active_limits
            # 八维旧机械对照保留原两端口机制。
            if torque_bias:
                active_limits = bias_limits(state[:dimensions], *state[dimensions:])
            if rolling_active:
                road_torques = rolling_torques(frames,radii,state[wheel_start:],rolling_coefficients,
                                               config.rolling_transition_speed, loads=wheel_loads)
            free, end_velocity = known(cross(spin(state), state[:3]), loads)
            order = [shared_branch] + [i for i in range(len(branches)) if i != shared_branch]
            for branch_index in order:
                branch, mc, ml, response, _wheels, _local_response, _plans, _shaft_data = branches[branch_index]
                projected = branch_free(free, branch)
                if ratio:
                    (clutch, loss), _speeds = transmission_state(
                        (dot(clutch_gradient, projected), dot(gear_gradient, projected)),
                        response, dt, capacity, efficiency)
                else:
                    clutch = loss = 0.
                end = tuple(projected[a] - dt * (clutch * mc[a] + loss * ml[a] + 0.) for a in range(dimensions))
                if differential_torques(end, branch, differential, damping, active_limits) is not None:
                    shared_branch = branch_index
                    break
            else:
                raise ArithmeticError("限滑/离合共同末状态无可行分区")
            return (end + (0., loss) if torque_bias else end), end_velocity, clutch, loss, 0.

        variables = dimensions + 2 if torque_bias else dimensions

        def residual_size(state, target):
            if not torque_bias:
                return max(abs(a - b) for a, b in zip(state, target))
            # 角速度与端口转矩使用各自原精度；不能用Nm残差接受更差的rad/s试探步。
            return max(abs(state[a] - target[a]) / (max(1e-14, math.ulp(state[a]), math.ulp(target[a]))
                       if a < dimensions else PORT_TOLERANCE) for a in range(variables))

        state = tuple(guess) + bias_ports if torque_bias else guess
        for iteration in range(30):
            end, end_velocity, clutch, loss, gear_reaction = mapped(state)
            residual = tuple(state[a] - end[a] for a in range(variables))
            error = max(abs(value) for value in residual)
            # 逐坐标保留绝对精度；大转速处容纳一次状态舍入的浮点间隔。
            angular_converged = all(abs(residual[a]) <= max(1e-14, math.ulp(state[a]), math.ulp(end[a]))
                                    for a in range(dimensions))
            ports_converged = not torque_bias or all(abs(value) <= PORT_TOLERANCE for value in residual[dimensions:])
            if angular_converged and ports_converged:
                if torque_bias:
                    bias_ports = gear_reaction, loss
                    active_limits = bias_limits(end[:dimensions], gear_reaction, loss)
                    if differential_torques(end[:dimensions], branches[shared_branch][0], differential,
                                            damping, active_limits) is None:
                        state = end
                        continue
                return end[:dimensions], end_velocity, clutch, loss, gear_reaction
            if (rolling_active or torque_bias) and iteration >= 4:
                # 大轮荷低速滚阻与轴系共同求根，固定点初迭代后用带步长搜索的Newton修正。
                # 冻结的旧八维对照机制保留原中心差分。
                columns = []
                for j in range(variables):
                    plus, minus = list(state), list(state)
                    plus[j] += .0001
                    minus[j] -= .0001
                    high, low = mapped(plus)[0], mapped(minus)[0]
                    columns.append(tuple(float(a == j) - (high[a]-low[a])/.0002 for a in range(variables)))
                delta = _solve(tuple(tuple(columns[j][a] for j in range(variables)) for a in range(variables)),
                               tuple(-value for value in residual))
                before = residual_size(state, end)
                for attempt in range(8):
                    candidate = tuple(state[a] + 2.**-attempt * delta[a] for a in range(variables))
                    target = mapped(candidate)[0]
                    if residual_size(candidate, target) < before:
                        state = candidate
                        # 下一次mapped前恢复该候选的负载，避免试探步残留容量。
                        if torque_bias:
                            active_limits = bias_limits(state[:dimensions], *state[dimensions:])
                        break
                else:
                    # 线搜索已无下降步时，半步固定点抑制末位舍入循环；原30轮／精度保持。
                    state = tuple(math.fsum((state[a], end[a])) / 2 for a in range(variables))
            else:
                state = end
        raise ArithmeticError(f"曲轴/四轮转子共同末状态超过30次迭代：{error:g}")

    def velocities(index, state, end_velocity):
        frame = frames[index]
        vx = dot(end_velocity, frame.tangent) + dot(state[:3], moments_x[index])
        vy = dot(end_velocity, frame.axle) + dot(state[:3], moments_y[index])
        return vx, vy, (radii[index] * state[index + wheel_start] - vx, -vy)

    def contact(index, state, end_velocity, fx, fy):
        car = configurations[index]
        if car.tire_compliance:
            frame = frames[index]
            return wheel_contact_state(state, end_velocity, wheel_start, index, frame.tangent, frame.axle,
                moments_x[index], moments_y[index], radii[index], (fx, fy), deformations[index],
                contact_parameters[index], tire_hardware[index], dt, rolling[index], None if shaft else math.hypot)
        vx, vy, _slip = velocities(index, state, end_velocity)
        grip, cx, cy = contact_parameters[index]
        kappa, alpha = slip_state(vx, vy, state[index + wheel_start], radii[index], car)
        return combined_force(kappa, alpha, grip, cx, cy, car.tire_shape, car.tire_curvature), None

    def solve_wheel(i, gyro):
        frame, car = frames[i], configurations[i]
        if shaft and car.tire_compliance:
            fx, fy, brake, _error = loaded_wheel_force_solution(wheel_map, i, forces, velocity,
                normal_forces if suspension is not None else None, normal_responses,
                suspension.gradients if suspension is not None else None, gyro,
                road_torques if rolling_active else None, active_limits, warm_branches, warm_modes,
                moments_x[i], moments_y[i], deformations[i], contact_parameters[i], tire_hardware[i],
                rolling[i], .0001, forces[i][:2],
                suspension is not None and sweep == 0 and rolling[i] and wheel_loads[i] > 0, None)
            return (fx, fy, brake), "magic-formula" if wheel_loads[i] > 0 else "airborne"
        if shaft:
            free_base_wheel, velocity_base = wheel_free_state(wheel_map, forces, velocity,
                normal_forces if suspension is not None else None, normal_responses,
                suspension.gradients if suspension is not None else None, gyro,
                road_torques if rolling_active else None, i)
        else:
            free_base_wheel, velocity_base = known(gyro, load_terms(exclude=i))
        rx, ry, _rb = responses[i]
        scale_x = dt * (1 / mass + dot(longitudinal[i], rx))
        scale_y = dt * (1 / mass + dot(lateral[i], ry))

        def local_state(fx, fy):
            if shaft:
                end, velocity_end, brake, partition = wheel_map_state(
                    wheel_map, i, free_base_wheel, velocity_base, fx, fy, active_limits,
                    warm_branches[i], warm_modes, frame.tangent, frame.axle)
                warm_branches[i] = partition[0]
                return end, velocity_end, brake, partition
            free = tuple(free_base_wheel[a] + dt * (rx[a] * fx + ry[a] * fy) for a in range(dimensions))
            order = [warm_branches[i]] + [j for j in range(len(branches)) if j != warm_branches[i]]
            for branch_index in order:
                branch, mc, ml, _response, wheel_responses, local_response, plans, _shaft_data = branches[branch_index]
                projected = branch_free(free, branch)
                local_rb = wheel_responses[i][2]
                if ratio:
                    value, _speeds, index = clutch_brake_state(
                        (dot(clutch_gradient, projected), dot(gear_gradient, projected), dot(brake_gradients[i], projected)),
                        local_response[i], dt, capacity, brakes[i], efficiency, plans[i], warm_modes[branch_index][i])
                    warm_modes[branch_index][i] = index
                    local_clutch, local_loss, brake = value
                else:
                    local_clutch = local_loss = 0.
                    brake = max(-brakes[i], min(brakes[i], dot(brake_gradients[i], projected)
                                                / (dt * dot(brake_gradients[i], local_rb))))
                    index = None
                end = tuple(projected[a] - dt * (local_clutch * mc[a] + local_loss * ml[a]
                                                + brake * local_rb[a] + 0.) for a in range(dimensions))
                if differential_torques(end, branch, differential, damping, active_limits) is not None:
                    warm_branches[i] = branch_index
                    break
            else:
                raise ArithmeticError("限滑/离合/制动共同末状态无可行分区")
            velocity_end = tuple(velocity_base[a] + dt / mass * (fx * frame.tangent[a] + fy * frame.axle[a]) for a in range(3))
            return end, velocity_end, brake, (branch_index, index)

        def residual(fx, fy):
            end, velocity_end, _brake, _index = local_state(fx, fy)
            target, _details = contact(i, end, velocity_end, fx, fy)
            return fx - target[0], fy - target[1]

        def derivatives(fx, fy):
            end, velocity_end, brake, (branch_index, index) = local_state(fx, fy)
            if shaft:
                return wheel_map_derivatives(wheel_map, i, branch_index, index, end, velocity_end,
                                             moments_x[i], moments_y[i], radii[i], frame.tangent, frame.axle)
            _branch, mc, ml, _response, wheel_responses, _local_response, plans, _shaft_data = branches[branch_index]
            local_rx, local_ry, local_rb = wheel_responses[i]
            vx, vy, slip = velocities(i, end, velocity_end)
            gradients = []
            for response, direction in ((local_rx, frame.tangent), (local_ry, frame.axle)):
                if ratio:
                    active, _sign, columns = plans[i][index]
                    rhs = tuple(dot(g, response) if mode in ("locked", "static") else 0.
                                for g, mode in zip((clutch_gradient, gear_gradient, brake_gradients[i]), active))
                    dc, dl, db = tuple(sum(columns[j][a] * rhs[j] for j in range(3)) for a in range(3))
                else:
                    dc = dl = 0.
                    db = (dot(brake_gradients[i], response) / dot(brake_gradients[i], local_rb)
                          if abs(brake) < brakes[i] else 0.)
                dq = tuple(dt * (response[a] - dc * mc[a] - dl * ml[a] - db * local_rb[a]) for a in range(dimensions))
                dx = dt / mass * dot(direction, frame.tangent) + dot(dq[:3], moments_x[i])
                dy = dt / mass * dot(direction, frame.axle) + dot(dq[:3], moments_y[i])
                gradients.append((radii[i] * dq[i + wheel_start] - dx, -dy, dx))
            return vx, vy, slip, gradients

        def jacobian(fx, fy):
            vx, _vy, slip, gradients = derivatives(fx, fy)
            slip_jacobian = tuple(tuple(gradients[j][a] for j in range(2)) for a in range(2))
            denominator_gradient = (tuple(math.copysign(1., vx) * value[2] for value in gradients)
                                    if abs(vx) > car.slip_speed else (0., 0.))
            target = contact_jacobian((fx, fy), deformations[i], slip, slip_jacobian,
                max(abs(vx), car.slip_speed), denominator_gradient, rolling[i], contact_parameters[i][0],
                *contact_parameters[i][1:], dt, car.tire_contact_stiffness, car.tire_contact_damping,
                car.tire_shape, car.tire_curvature)
            return 1 - target[0][0], -target[0][1], -target[1][0], 1 - target[1][1]

        def sticking_residual(fx, fy):
            end, velocity_end, _brake, _index = local_state(fx, fy)
            _vx, _vy, slip = velocities(i, end, velocity_end)
            return -slip[0] / scale_x, -slip[1] / scale_y

        def sticking_jacobian(fx, fy):
            _vx, _vy, _slip, gradients = derivatives(fx, fy)
            return (-gradients[0][0] / scale_x, -gradients[1][0] / scale_x,
                    -gradients[0][1] / scale_y, -gradients[1][1] / scale_y)

        mode = "magic-formula" if wheel_loads[i] > 0 else "airborne"
        if car.tire_compliance:
            guess = forces[i][:2]
            if suspension is not None and sweep == 0 and rolling[i] and wheel_loads[i] > 0:
                # 姿态/轮荷刷新后，旧力可能位于曲线下降支。用同一隐式方程的零滑移切线预测初值。
                vx, _vy, slip, gradients = derivatives(0., 0.)
                impedance = car.tire_contact_stiffness * dt + car.tire_contact_damping
                stiffnesses = contact_parameters[i][1:]
                slopes = tuple(value / max(abs(vx), car.slip_speed) for value in stiffnesses)
                patch = tuple(slip[a] + car.tire_contact_stiffness * deformations[i][a] / impedance for a in range(2))
                matrix = tuple(tuple(float(a == b) - slopes[a] * (
                    gradients[b][a] - float(a == b) / impedance) for b in range(2)) for a in range(2))
                a, b = matrix[0]
                c, d = matrix[1]
                rhs_x, rhs_y = tuple(slopes[a] * patch[a] for a in range(2))
                determinant = a * d - b * c
                guess = ((d * rhs_x - b * rhs_y) / determinant, (a * rhs_y - c * rhs_x) / determinant)
            if rolling[i]:
                fx, fy, _error = _solve_rolling_force(residual, jacobian, contact_parameters[i][0],
                                                     tolerance=.0001, initial=guess)
            else:
                fx, fy, _error = _solve_force(residual, tolerance=.0001, initial=guess, jacobian=jacobian)
        else:
            sticking = False
            if static[i]:
                fx, fy, _error = _solve_force(sticking_residual, tolerance=.0001,
                                             initial=forces[i][:2], jacobian=sticking_jacobian)
                sticking = math.hypot(fx, fy) <= contact_parameters[i][0]
            if sticking:
                mode = "sticking"
            else:
                fx, fy, _error = _solve_force(residual, tolerance=.0001, initial=forces[i][:2])
        _end, _velocity, brake, _index = local_state(fx, fy)
        return (fx, fy, brake), mode

    def correct_brakes(state):
        forces[:] = wheel_brake_correction(wheel_map, state, forces, shared_branch, shared_port_index)

    def correct_contacts(guess):
        """强耦合时联合修正八个接触力；仍解同一末状态，不改力/制动门槛。"""
        original = tuple(forces)
        values = tuple(value for force in forces for value in force[:2])

        def residual(values):
            for i in range(4):
                forces[i] = values[2 * i], values[2 * i + 1], original[i][2]
            state, end_velocity, _clutch, _loss, _gear = shared(guess)
            correct_brakes(state)
            state, end_velocity, _clutch, _loss, _gear = shared(state)
            errors = []
            for i in range(4):
                fx, fy, _brake = forces[i]
                if modes[i] == "sticking":
                    _vx, _vy, slip = velocities(i, state, end_velocity)
                    errors.extend((-slip[0] / (dt * (1 / mass + dot(longitudinal[i], responses[i][0]))),
                                   -slip[1] / (dt * (1 / mass + dot(lateral[i], responses[i][1])))))
                else:
                    target, _details = contact(i, state, end_velocity, fx, fy)
                    errors.extend((fx - target[0], fy - target[1]))
            return tuple(errors)

        errors = residual(values)
        columns = []
        for j in range(8):
            plus, minus = list(values), list(values)
            plus[j] += .01
            minus[j] -= .01
            high, low = residual(plus), residual(minus)
            columns.append(tuple((high[i] - low[i]) / .02 for i in range(8)))
        rows = [[columns[j][i] for j in range(8)] + [-errors[i]] for i in range(8)]
        # 静摩擦接触可存在相关约束；增量仅解独立行，旧力的零空间分量保持。
        pivots, row = [], 0
        rounding = 32 * math.ulp(max(abs(value) for line in rows for value in line[:8]))
        for column in range(8):
            pivot = max(range(row, 8), key=lambda i: abs(rows[i][column]))
            if abs(rows[pivot][column]) <= rounding:
                continue
            rows[row], rows[pivot] = rows[pivot], rows[row]
            scale = rows[row][column]
            rows[row] = [value / scale for value in rows[row]]
            for i in range(8):
                if i != row:
                    factor = rows[i][column]
                    rows[i] = [rows[i][j] - factor * rows[row][j] for j in range(9)]
            pivots.append((row, column))
            row += 1
            if row == 8:
                break
        delta = [0.] * 8
        for row, column in pivots:
            delta[column] = rows[row][8]
        before = max(math.hypot(*errors[2 * i:2 * i + 2]) for i in range(4))
        for attempt in range(8):
            scale = 2.**-attempt
            candidate = tuple(values[i] + scale * delta[i] for i in range(8))
            if any(modes[i] == "sticking" and math.hypot(*candidate[2 * i:2 * i + 2])
                   > contact_parameters[i][0] for i in range(4)):
                continue
            after = residual(candidate)
            if max(math.hypot(*after[2 * i:2 * i + 2]) for i in range(4)) < before:
                return
        forces[:] = original

    def correct_suspension(guess, velocity_guess):
        """联立修正六维末速度与曲面反力，消除大轮荷时滞后几何的慢收敛。"""
        nonlocal suspension, normal_forces
        original_system, original_forces = suspension, normal_forces
        values = tuple(velocity_guess) + tuple(guess[:3])

        def residual(values):
            nonlocal suspension, normal_forces
            suspension = contact_system(values[:3], values[3:])
            normal_projection()
            normal_forces = normal_load_solution(values[:3], values[3:])
            state, velocity_end, _clutch, _loss, _gear = shared(tuple(values[3:]) + tuple(guess[3:]))
            return tuple(values[a] - end for a, end in enumerate(tuple(velocity_end) + tuple(state[:3])))

        errors = residual(values)
        columns = []
        for j in range(6):
            plus, minus = list(values), list(values)
            plus[j] += .0001
            minus[j] -= .0001
            high, low = residual(plus), residual(minus)
            columns.append(tuple((high[i] - low[i]) / .0002 for i in range(6)))
        delta = _solve(tuple(tuple(columns[j][i] for j in range(6)) for i in range(6)),
                       tuple(-value for value in errors))
        before = max(abs(value) for value in errors)
        for attempt in range(8):
            candidate = tuple(values[i] + 2.**-attempt * delta[i] for i in range(6))
            after = residual(candidate)
            if max(abs(value) for value in after) < before:
                normal_loads()
                return
        suspension, normal_forces = original_system, original_forces
        normal_projection()

    state = initial
    normal_error = 0.
    geometry_error = 0.
    normal_tolerance = 1e-10
    for sweep in range(20):
        state, end_velocity, clutch, loss, gear_reaction = shared(state)
        if suspension is not None:
            suspension = contact_system(end_velocity, state[:3])
            normal_projection()
            normal_forces = normal_load_solution(end_velocity, state[:3],
                                                mobility=normal_mobility, forces=normal_forces)
            normal_loads()
            state, end_velocity, clutch, loss, gear_reaction = shared(state)
        gyro = cross(spin(state), state[:3])
        for i in (range(4) if sweep % 2 == 0 else range(3, -1, -1)):
            forces[i], modes[i] = solve_wheel(i, gyro)


        state, end_velocity, clutch, loss, gear_reaction = shared(state)
        if shaft:
            correct_brakes(state)
            state, end_velocity, clutch, loss, gear_reaction = shared(state)
        if suspension is not None:
            # 接触块之后用实际末速度刷新硬件反力，再同步机械速度。
            # 预条件块的力与直接本构式可能相差一个舍入位，不能把它留作收敛残差。
            normal_forces = normal_load_solution(end_velocity, state[:3])
            normal_loads()
            state, end_velocity, clutch, loss, gear_reaction = shared(state)
        if shaft:
            maximum, brake_error = wheel_residuals(wheel_map, state, end_velocity, forces, modes,
                deformations, contact_parameters, tire_hardware, rolling, moments_x, moments_y,
                tire_compliance, None)
        else:
            maximum, brake_error = 0., 0.
            for i in range(4):
                fx, fy, brake = forces[i]
                if modes[i] == "sticking":
                    _vx, _vy, slip = velocities(i, state, end_velocity)
                    error = math.hypot(slip[0] / (dt * (1 / mass + dot(longitudinal[i], responses[i][0]))),
                                       slip[1] / (dt * (1 / mass + dot(lateral[i], responses[i][1]))))
                else:
                    target, _details = contact(i, state, end_velocity, fx, fy)
                    error = math.hypot(fx - target[0], fy - target[1])
                maximum = max(maximum, error)
                target_brake = max(-brakes[i], min(brakes[i], brake + dot(brake_gradients[i], state)
                                   / (dt * dot(brake_gradients[i], responses[i][2]))))
                brake_error = max(brake_error, abs(brake - target_brake))
        if suspension is not None:
            target_forces = normal_load_solution(end_velocity, state[:3])
            target_system = contact_system(end_velocity, state[:3])
            normal_error, geometry_error = suspension_residuals(normal_forces, target_forces,
                suspension.gradients, target_system.gradients, dt)
        if maximum < .001 and brake_error < 1e-9 and normal_error < normal_tolerance and geometry_error < 1e-12:
            break
        # 接触误差已小于力门槛时，仍会推动末姿态；几何未收敛也需联立细化接触力。
        if shaft and sweep >= 8 and (maximum >= .001 or geometry_error >= 1e-12):
            correct_contacts(state)
        if suspension is not None and sweep >= 8 and maximum < .001 and (normal_error >= normal_tolerance or geometry_error >= 1e-12):
            correct_suspension(state, end_velocity)
    else:
        raise ArithmeticError(f"传动/四轮共同求解超过20轮：{maximum:g}N，制动{brake_error:g}Nm，法向{normal_error:g}N，几何共轭冲量{geometry_error:g}Ns/Nms")

    normal_step = shared_suspension(suspension, end_velocity, state[:3], dt) if suspension is not None else None
    gyro_torques = bearing_torques(axes, state[wheel_start:], wheel_inertia, state[:3]) if rotor else ((0., 0., 0.),) * 4
    wheels = []
    for i, frame in enumerate(frames):
        fx, fy, brake = forces[i]
        vx, vy, _slip = velocities(i, state, end_velocity)
        kappa, alpha = slip_state(vx, vy, state[i + wheel_start], radii[i], configurations[i])
        elastic = rate = (0., 0.)
        patch_kappa = patch_alpha = None
        energy = material = road = numerical = 0.
        mode = modes[i]
        if config.tire_compliance:
            _target, details = contact(i, state, end_velocity, fx, fy)
            elastic, rate, patch, patch_kappa, patch_alpha, mode = details
            energy, material, road, numerical = energy_terms((fx, fy), deformations[i], elastic, rate, patch,
                dt, config.tire_contact_stiffness, config.tire_contact_damping)
            if wheel_loads[i] == 0:
                mode = "airborne"
        wheels.append(WheelStep(state[i + wheel_start], dot(brake_gradients[i], state), vx, vy, dot(state[:3], axes[i]),
            kappa, alpha, fx, fy, brake, maximum, mode, *elastic, patch_kappa, patch_alpha,
            energy, material, road, numerical, *rate, gyro_torques[i], steering_torques[i],
            road_torques[i], dt * road_torques[i] * state[i + wheel_start]))
    engine_speed = dot(engine_gradient, state)
    clutch_slip, gear_speed = dot(clutch_gradient, state), dot(gear_gradient, state)
    engine_gyro = cross(tuple(engine_inertia * state[3] * value for value in engine_axis), state[:3])
    engine_body = tuple((clutch + engine_drag * engine_speed - engine_torque) * engine_axis[a] + engine_gyro[a] for a in range(3))
    differential_slips = tuple(dot(g, state) for g in differential)
    limited_torques = differential_torques(state, branches[shared_branch][0], differential, damping, active_limits)
    shaft_speed = (state[4] - dot(shaft_axis, state[:3])) if shaft else None
    shaft_gyro = cross(tuple(shaft_inertia * state[4] * value for value in shaft_axis), state[:3]) if shaft else (0.,) * 3
    shaft_body = tuple((gear_reaction - clutch) * shaft_axis[a] + shaft_gyro[a] for a in range(3)) if shaft else (0.,) * 3
    drive_torque = ratio * ((gear_reaction if shaft else clutch) - loss)
    downstream_speeds = tuple(dot(g, state) if j else 0. for j, g in zip(inertias, gradients))
    inertia_torques = tuple(j * (new - old) / dt for j, new, old in
                           zip(inertias, downstream_speeds, downstream_omega))
    downstream_wheels = tuple(-sum(torque * g[i + wheel_start] for torque, g in zip(inertia_torques, gradients))
                             for i in range(4))
    downstream_spin = tuple(sum(j * speed * axis[a] for j, speed, axis in
                               zip(inertias, downstream_speeds, downstream_axes)) for a in range(3))
    downstream_gyro = cross(downstream_spin, state[:3])
    downstream_body = tuple(-sum(torque * axis[a] for torque, axis in zip(inertia_torques, downstream_axes))
                            + downstream_gyro[a] for a in range(3))
    wheel_drives = tuple((drive_torque * weight if weight else 0.)
                        - sum(g[i + wheel_start] * torque for g, torque in zip(differential, limited_torques))
                        for i, weight in enumerate(config.drive_weights))
    if downstream:
        wheel_drives = tuple(wheel_drives[i] + downstream_wheels[i] for i in range(4))
    return DrivetrainStep(tuple(wheels), end_velocity, state[:3], state[3], engine_speed, drive_torque,
        clutch, clutch_slip, loss, gear_speed, engine_body, dt * engine_torque * engine_speed,
        dt * engine_drag * engine_speed**2, dt * clutch * clutch_slip, dt * loss * gear_speed, sweep + 1,
        wheel_drives, limited_torques, differential_slips,
        tuple(dt * torque * slip for torque, slip in zip(limited_torques, differential_slips)),
        state[4] if shaft else None, shaft_speed, gear_reaction,
        dot(shaft_gear_gradient, state) if shaft and not hard_gear else 0.,
        dt * gear_reaction * dot(shaft_gear_gradient, state) if shaft and not hard_gear else 0., shaft_body,
        downstream_speeds, downstream_body, downstream_wheels,
        tuple(.5 * j * speed**2 for j, speed in zip(inertias, downstream_speeds)),
        tuple(.5 * j * (new - old)**2 for j, new, old in zip(inertias, downstream_speeds, downstream_omega)),
        normal_step if suspension is not None else None, normal_error, suspension)
