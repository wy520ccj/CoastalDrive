"""四轮接触、曲轴/输入轴、有限离合与制动的共同末状态。"""

import math
from dataclasses import dataclass

from differential import (
    differential_branches,
    differential_gradients,
    differential_torques,
    viscous_projection,
)
from rotor_dynamics import bearing_torques, cross
from shaft_transmission import (
    brake_increment,
    shaft_brake_plans,
    shaft_brake_response,
    shaft_brake_state,
    shaft_gradients,
    synchronizer_brake_plans,
    synchronizer_brake_response,
    synchronizer_brake_state,
)
from tire_compliance import contact_force, contact_jacobian, energy_terms
from tire_forces import combined_force, slip_state
from tire_properties import tire_grip, tire_stiffness
from transmission_ports import clutch_brake_plans, clutch_brake_state, transmission_state
from wheel_dynamics import WheelStep, _solve_force


def dot(first, second):
    """机械账包含空间向量和完整转子速度，不能截掉曲轴/输入轴/轮轴。"""
    return sum(a * b for a, b in zip(first, second))


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


def advance_drivetrain(velocity, angular, omega, engine_omega, frames, deformations,
                       engine_torque, capacity, ratio, brakes, config, rear_config, dt, *,
                       inverse_inertia, engine_inertia, engine_axis, engine_drag, efficiency,
                       steering_torques=((0., 0., 0.),) * 4, force_initial=((0., 0., 0.),) * 4,
                       shaft_omega=None, shaft_inertia=None, shaft_axis=None,
                       synchronizing=False, synchronizer_capacity=0.):
    """九维q含实体输入轴；未指定输入轴时保留原八维机制供旧/新A/B。"""
    mass, wheel_inertia = config.mass, config.wheel_inertia
    shaft = shaft_omega is not None
    wheel_start, dimensions = (5, 9) if shaft else (4, 8)
    hard_gear = bool(ratio and not synchronizing) if shaft else bool(ratio)
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

    def inverse_mass(vector):
        return (tuple(dot(row, vector[:3]) for row in inverse_inertia)
                + (vector[3] / engine_inertia,)
                + ((vector[4] / shaft_inertia,) if shaft else ())
                + tuple(value / wheel_inertia for value in vector[wheel_start:]))

    engine_response = inverse_mass(engine_gradient)
    drag_factor = dt * engine_drag / (1 + dt * engine_drag * dot(engine_gradient, engine_response))

    def mobility(vector):
        base = inverse_mass(vector)
        projection = drag_factor * dot(engine_response, vector)
        return tuple(base[a] - projection * engine_response[a] for a in range(dimensions))

    responses = tuple((mobility(longitudinal[i]), mobility(lateral[i]), mobility(brake_gradients[i])) for i in range(4))
    differential = differential_gradients(axes)
    if shaft:
        differential = tuple(g[:4] + (0.,) + g[4:] for g in differential)
    damping, limits = config.differential_damping, config.differential_capacity
    limited = any(c and limit for c, limit in zip(damping, limits))
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
        return tuple(projected[a] + branch[1][a] for a in range(dimensions))

    forces = list(force_initial)
    modes = [None] * 4
    configurations = (config, config, rear_config, rear_config)
    rolling = tuple(max(abs(dot(velocity, frame.tangent) + dot(angular, moments_x[i])),
                        abs(radii[i] * omega[i])) >= config.static_contact_speed for i, frame in enumerate(frames))
    static = tuple(frame.load > 0 and max(abs(dot(velocity, frame.tangent) + dot(angular, moments_x[i])),
                   abs(dot(velocity, frame.axle) + dot(angular, moments_y[i])), abs(radii[i] * omega[i]))
                   < config.static_contact_speed for i, frame in enumerate(frames))
    steering = tuple(sum(torque[a] for torque in steering_torques) for a in range(3))
    free_base = tuple(initial[a] + dt * engine_torque * engine_response[a]
                      + (dt * dot(inverse_inertia[a], steering) if a < 3 else 0.) for a in range(dimensions))

    projection = drag_factor * dot(engine_gradient, free_base)
    free_base = tuple(free_base[a] - projection * engine_response[a] for a in range(dimensions))

    def spin(state):
        return tuple(engine_inertia * state[3] * engine_axis[a] - (wheel_inertia * sum(
            state[i + wheel_start] * axes[i][a] for i in range(4)) if rotor else 0.)
            + (shaft_inertia * state[4] * shaft_axis[a] if shaft else 0.) for a in range(3))

    def known(gyro, exclude=None):
        gyro_response = mobility(tuple(gyro) + (0.,) * (dimensions - 3))
        free = tuple(free_base[a] + dt * gyro_response[a] + dt * sum(
            forces[i][0] * responses[i][0][a] + forces[i][1] * responses[i][1][a]
            - forces[i][2] * responses[i][2][a] for i in range(4) if i != exclude) for a in range(dimensions))
        end_velocity = tuple(velocity[a] + dt / mass * sum(
            forces[i][0] * frames[i].tangent[a] + forces[i][1] * frames[i].axle[a]
            for i in range(4) if i != exclude) for a in range(3))
        return free, end_velocity

    def shared(guess):
        nonlocal shared_branch, shared_port_index
        state = guess
        for _ in range(30):
            free, end_velocity = known(cross(spin(state), state[:3]))
            order = [shared_branch] + [i for i in range(len(branches)) if i != shared_branch]
            for branch_index in order:
                branch, mc, ml, response, _wheels, local_response, _plans, shaft_data = branches[branch_index]
                projected = branch_free(free, branch)
                gear_reaction = 0.
                if shaft:
                    mg, shared_plans = shaft_data
                    if hard_gear:
                        values, _speeds, _index = shaft_brake_state(
                            tuple(dot(g, projected) for g in (clutch_gradient, shaft_gear_gradient, gear_gradient, brake_gradients[0])),
                            local_response[0], dt, capacity, 0., efficiency, shared_plans)
                        clutch, gear_reaction, loss, _brake = values
                    else:
                        values, _speeds, _index = synchronizer_brake_state(
                            tuple(dot(g, projected) for g in (clutch_gradient, shaft_gear_gradient, brake_gradients[0])),
                            local_response[0], dt, (capacity, synchronizer_capacity, 0.), shared_plans)
                        clutch, gear_reaction, _brake = values
                        loss = 0.
                elif ratio:
                    (clutch, loss), _speeds = transmission_state(
                        (dot(clutch_gradient, projected), dot(gear_gradient, projected)),
                        response, dt, capacity, efficiency)
                else:
                    clutch = loss = 0.
                end = tuple(projected[a] - dt * (clutch * mc[a] + loss * ml[a]
                            + (gear_reaction * mg[a] if shaft else 0.)) for a in range(dimensions))
                if differential_torques(end, branch, differential, damping, limits) is not None:
                    shared_branch = branch_index
                    if shaft:
                        shared_port_index = _index
                    break
            else:
                raise ArithmeticError("限滑/离合共同末状态无可行分区")
            error = max(abs(end[a] - state[a]) for a in range(dimensions))
            state = end
            if error < 1e-12:
                return state, end_velocity, clutch, loss, gear_reaction
        raise ArithmeticError("曲轴/四轮转子共同末状态超过30次迭代")

    def velocities(index, state, end_velocity):
        frame = frames[index]
        vx = dot(end_velocity, frame.tangent) + dot(state[:3], moments_x[index])
        vy = dot(end_velocity, frame.axle) + dot(state[:3], moments_y[index])
        return vx, vy, (radii[index] * state[index + wheel_start] - vx, -vy)

    def contact(index, state, end_velocity, fx, fy):
        frame, car = frames[index], configurations[index]
        vx, vy, slip = velocities(index, state, end_velocity)
        grip = tire_grip(frame.load, frame.mu, car)
        cx, cy = tire_stiffness(frame.load, car)
        if car.tire_compliance:
            target, *details = contact_force((fx, fy), deformations[index], slip, max(abs(vx), car.slip_speed),
                rolling[index], grip, cx, cy, dt, car.tire_contact_stiffness, car.tire_contact_damping,
                car.tire_shape, car.tire_curvature)
            return target, details
        kappa, alpha = slip_state(vx, vy, state[index + wheel_start], radii[index], car)
        return combined_force(kappa, alpha, grip, cx, cy, car.tire_shape, car.tire_curvature), None

    def solve_wheel(i, gyro):
        free_base_wheel, velocity_base = known(gyro, exclude=i)
        frame, car = frames[i], configurations[i]
        rx, ry, _rb = responses[i]
        scale_x = dt * (1 / mass + dot(longitudinal[i], rx))
        scale_y = dt * (1 / mass + dot(lateral[i], ry))

        def local_state(fx, fy):
            free = tuple(free_base_wheel[a] + dt * (rx[a] * fx + ry[a] * fy) for a in range(dimensions))
            order = [warm_branches[i]] + [j for j in range(len(branches)) if j != warm_branches[i]]
            for branch_index in order:
                branch, mc, ml, _response, wheel_responses, local_response, plans, shaft_data = branches[branch_index]
                projected = branch_free(free, branch)
                local_rb = wheel_responses[i][2]
                local_gear = 0.
                if shaft:
                    mg, _shared_plans = shaft_data
                    if hard_gear:
                        value, _speeds, index = shaft_brake_state(
                            tuple(dot(g, projected) for g in (clutch_gradient, shaft_gear_gradient, gear_gradient, brake_gradients[i])),
                            local_response[i], dt, capacity, brakes[i], efficiency, plans[i], warm_modes[branch_index][i])
                        local_clutch, local_gear, local_loss, brake = value
                    else:
                        value, _speeds, index = synchronizer_brake_state(
                            tuple(dot(g, projected) for g in (clutch_gradient, shaft_gear_gradient, brake_gradients[i])),
                            local_response[i], dt, (capacity, synchronizer_capacity, brakes[i]), plans[i], warm_modes[branch_index][i])
                        local_clutch, local_gear, brake = value
                        local_loss = 0.
                    warm_modes[branch_index][i] = index
                elif ratio:
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
                                                + brake * local_rb[a] + (local_gear * mg[a] if shaft else 0.)) for a in range(dimensions))
                if differential_torques(end, branch, differential, damping, limits) is not None:
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
            _branch, mc, ml, _response, wheel_responses, local_response, plans, shaft_data = branches[branch_index]
            local_rx, local_ry, local_rb = wheel_responses[i]
            vx, vy, slip = velocities(i, end, velocity_end)
            gradients = []
            for response, direction in ((local_rx, frame.tangent), (local_ry, frame.axle)):
                dg = 0.
                if shaft:
                    mg, _shared_plans = shaft_data
                    if hard_gear:
                        dc, dg, dl, db = shaft_brake_response(
                            tuple(dot(g, response) for g in (clutch_gradient, shaft_gear_gradient, gear_gradient, brake_gradients[i])),
                            local_response[i], plans[i][index])
                    else:
                        dc, dg, db = synchronizer_brake_response(
                            tuple(dot(g, response) for g in (clutch_gradient, shaft_gear_gradient, brake_gradients[i])),
                            plans[i][index])
                        dl = 0.
                elif ratio:
                    active, _sign, columns = plans[i][index]
                    rhs = tuple(dot(g, response) if mode in ("locked", "static") else 0.
                                for g, mode in zip((clutch_gradient, gear_gradient, brake_gradients[i]), active))
                    dc, dl, db = tuple(sum(columns[j][a] * rhs[j] for j in range(3)) for a in range(3))
                else:
                    dc = dl = 0.
                    db = (dot(brake_gradients[i], response) / dot(brake_gradients[i], local_rb)
                          if abs(brake) < brakes[i] else 0.)
                dq = tuple(dt * (response[a] - dc * mc[a] - dl * ml[a] - db * local_rb[a] - (dg * mg[a] if shaft else 0.)) for a in range(dimensions))
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
                max(abs(vx), car.slip_speed), denominator_gradient, rolling[i], tire_grip(frame.load, frame.mu, car),
                *tire_stiffness(frame.load, car), dt, car.tire_contact_stiffness, car.tire_contact_damping,
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

        mode = "magic-formula" if frame.load > 0 else "airborne"
        if car.tire_compliance:
            fx, fy, _error = _solve_force(residual, tolerance=.0001, initial=forces[i][:2], jacobian=jacobian)
        else:
            sticking = False
            if static[i]:
                fx, fy, _error = _solve_force(sticking_residual, tolerance=.0001,
                                             initial=forces[i][:2], jacobian=sticking_jacobian)
                sticking = math.hypot(fx, fy) <= tire_grip(frame.load, frame.mu, car)
            if sticking:
                mode = "sticking"
            else:
                fx, fy, _error = _solve_force(residual, tolerance=.0001, initial=forces[i][:2])
        _end, _velocity, brake, _index = local_state(fx, fy)
        return (fx, fy, brake), mode

    def correct_brakes(state):
        _branch, mc, ml, _response, wheels, local, _plans, (mg, shared_plans) = branches[shared_branch]
        corrections = []
        for j in range(4):
            rb = wheels[j][2]
            if hard_gear:
                dc, dg, dl, _db = shaft_brake_response(
                    tuple(dot(g, rb) for g in (clutch_gradient, shaft_gear_gradient, gear_gradient, brake_gradients[0])),
                    local[0], shared_plans[shared_port_index])
            else:
                dc, dg, _db = synchronizer_brake_response(
                    tuple(dot(g, rb) for g in (clutch_gradient, shaft_gear_gradient, brake_gradients[0])),
                    shared_plans[shared_port_index])
                dl = 0.
            corrections.append(tuple(rb[a] - dc * mc[a] - dg * mg[a] - dl * ml[a] for a in range(dimensions)))
        matrix = tuple(tuple(dot(g, response) for response in corrections) for g in brake_gradients)
        delta = brake_increment(matrix, tuple(dot(g, state) for g in brake_gradients),
                                tuple(f[2] for f in forces), brakes, dt,
                                tuple(dot(brake_gradients[i], responses[i][2]) for i in range(4)))
        for i, value in enumerate(delta):
            fx, fy, brake = forces[i]
            forces[i] = fx, fy, brake + value

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
                   > tire_grip(frames[i].load, frames[i].mu, configurations[i]) for i in range(4)):
                continue
            after = residual(candidate)
            if max(math.hypot(*after[2 * i:2 * i + 2]) for i in range(4)) < before:
                return
        forces[:] = original

    state = initial
    for sweep in range(20):
        state, end_velocity, clutch, loss, gear_reaction = shared(state)
        gyro = cross(spin(state), state[:3])
        for i in (range(4) if sweep % 2 == 0 else range(3, -1, -1)):
            forces[i], modes[i] = solve_wheel(i, gyro)


        state, end_velocity, clutch, loss, gear_reaction = shared(state)
        if shaft:
            correct_brakes(state)
            state, end_velocity, clutch, loss, gear_reaction = shared(state)
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
        if maximum < .001 and brake_error < 1e-9:
            break
        if shaft and maximum >= .001 and sweep >= 8:
            correct_contacts(state)
    else:
        raise ArithmeticError(f"传动/四轮共同求解超过20轮：{maximum:g}N，制动{brake_error:g}Nm")

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
            if frame.load == 0:
                mode = "airborne"
        wheels.append(WheelStep(state[i + wheel_start], dot(brake_gradients[i], state), vx, vy, dot(state[:3], axes[i]),
            kappa, alpha, fx, fy, brake, maximum, mode, *elastic, patch_kappa, patch_alpha,
            energy, material, road, numerical, *rate, gyro_torques[i], steering_torques[i]))
    engine_speed = dot(engine_gradient, state)
    clutch_slip, gear_speed = dot(clutch_gradient, state), dot(gear_gradient, state)
    engine_gyro = cross(tuple(engine_inertia * state[3] * value for value in engine_axis), state[:3])
    engine_body = tuple((clutch + engine_drag * engine_speed - engine_torque) * engine_axis[a] + engine_gyro[a] for a in range(3))
    differential_slips = tuple(dot(g, state) for g in differential)
    limited_torques = differential_torques(state, branches[shared_branch][0], differential, damping, limits)
    shaft_speed = (state[4] - dot(shaft_axis, state[:3])) if shaft else None
    shaft_gyro = cross(tuple(shaft_inertia * state[4] * value for value in shaft_axis), state[:3]) if shaft else (0.,) * 3
    shaft_body = tuple((gear_reaction - clutch) * shaft_axis[a] + shaft_gyro[a] for a in range(3)) if shaft else (0.,) * 3
    drive_torque = ratio * ((gear_reaction if shaft else clutch) - loss)
    wheel_drives = tuple((drive_torque * weight if weight else 0.)
                        - sum(g[i + wheel_start] * torque for g, torque in zip(differential, limited_torques))
                        for i, weight in enumerate(config.drive_weights))
    return DrivetrainStep(tuple(wheels), end_velocity, state[:3], state[3], engine_speed, drive_torque,
        clutch, clutch_slip, loss, gear_speed, engine_body, dt * engine_torque * engine_speed,
        dt * engine_drag * engine_speed**2, dt * clutch * clutch_slip, dt * loss * gear_speed, sweep + 1,
        wheel_drives, limited_torques, differential_slips,
        tuple(dt * torque * slip for torque, slip in zip(limited_torques, differential_slips)),
        state[4] if shaft else None, shaft_speed, gear_reaction,
        dot(shaft_gear_gradient, state) if shaft and not hard_gear else 0.,
        dt * gear_reaction * dot(shaft_gear_gradient, state) if shaft and not hard_gear else 0., shaft_body)
