"""四轮接触、曲轴、有限离合与制动的共同末状态；不持有原生世界。"""

import math
from dataclasses import dataclass

from rotor_dynamics import bearing_torques, cross, dot
from tire_compliance import contact_force, contact_jacobian, energy_terms
from tire_forces import combined_force, slip_state
from tire_properties import tire_grip, tire_stiffness
from transmission_ports import clutch_brake_plans, clutch_brake_state, transmission_state
from wheel_dynamics import WheelStep, _solve_force


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


def advance_drivetrain(velocity, angular, omega, engine_omega, frames, deformations,
                       engine_torque, capacity, ratio, brakes, config, rear_config, dt, *,
                       inverse_inertia, engine_inertia, engine_axis, engine_drag, efficiency,
                       steering_torques=((0., 0., 0.),) * 4):
    """q=(车身角速3,曲轴绝对轴速,四轮绝对轴速)，所有约束共用同一隐式末速度。"""
    mass, wheel_inertia = config.mass, config.wheel_inertia
    initial = tuple(angular) + (engine_omega,) + tuple(omega)
    rotor = config.wheel_rotor_transport
    axes = tuple(frame.spin_axis if rotor else frame.axle for frame in frames)
    radii = tuple(frame.rolling_radius if rotor else config.wheel_radius for frame in frames)
    moments_x = tuple(frame.moment_x if rotor else tuple(
        cross(frame.point, frame.tangent)[a] - radii[i] * axes[i][a] for a in range(3))
        for i, frame in enumerate(frames))
    moments_y = tuple(cross(frame.point, frame.axle) for frame in frames)
    engine_gradient = tuple(-value for value in engine_axis) + (1., 0., 0., 0., 0.)
    rear = tuple(ratio / 2 * (axes[2][a] + axes[3][a]) for a in range(3))
    clutch_gradient = tuple(-engine_axis[a] - rear[a] for a in range(3)) + (1., 0., 0., -ratio / 2, -ratio / 2)
    gear_gradient = rear + (0., 0., 0., ratio / 2, ratio / 2)
    brake_gradients = tuple(axes[i] + (0.,) + tuple(float(j == i) for j in range(4)) for i in range(4))
    longitudinal = tuple(moments_x[i] + (0.,) + tuple(-radii[i] if j == i else 0. for j in range(4)) for i in range(4))
    lateral = tuple(moment + (0., 0., 0., 0., 0.) for moment in moments_y)

    def inverse_mass(vector):
        return (tuple(dot(row, vector[:3]) for row in inverse_inertia)
                + (vector[3] / engine_inertia,) + tuple(value / wheel_inertia for value in vector[4:]))

    engine_response = inverse_mass(engine_gradient)
    drag_factor = dt * engine_drag / (1 + dt * engine_drag * dot(engine_gradient, engine_response))

    def mobility(vector):
        base = inverse_mass(vector)
        projection = drag_factor * dot(engine_response, vector)
        return tuple(base[a] - projection * engine_response[a] for a in range(8))

    mc, ml = mobility(clutch_gradient), mobility(gear_gradient)
    dcc, dcl, dll = dot(clutch_gradient, mc), dot(clutch_gradient, ml), dot(gear_gradient, ml)
    responses = tuple((mobility(longitudinal[i]), mobility(lateral[i]), mobility(brake_gradients[i])) for i in range(4))
    local_response = tuple(((dcc, dcl, dot(clutch_gradient, responses[i][2])),
                            (dcl, dll, dot(gear_gradient, responses[i][2])),
                            (dot(clutch_gradient, responses[i][2]), dot(gear_gradient, responses[i][2]),
                             dot(brake_gradients[i], responses[i][2]))) for i in range(4))
    # 空挡没有已建模的输入轴惯量，因而离合无负载，不锁到虚构的静止轴。
    plans = (tuple(clutch_brake_plans(local_response[i], capacity, brakes[i], efficiency) for i in range(4))
             if ratio else ((),) * 4)
    warm_modes = [None] * 4
    forces = [(0., 0., 0.)] * 4
    modes = [None] * 4
    configurations = (config, config, rear_config, rear_config)
    rolling = tuple(max(abs(dot(velocity, frame.tangent) + dot(angular, moments_x[i])),
                        abs(radii[i] * omega[i])) >= config.static_contact_speed for i, frame in enumerate(frames))
    static = tuple(frame.load > 0 and max(abs(dot(velocity, frame.tangent) + dot(angular, moments_x[i])),
                   abs(dot(velocity, frame.axle) + dot(angular, moments_y[i])), abs(radii[i] * omega[i]))
                   < config.static_contact_speed for i, frame in enumerate(frames))
    steering = tuple(sum(torque[a] for torque in steering_torques) for a in range(3))
    free_base = tuple(initial[a] + dt * engine_torque * engine_response[a]
                      + (dt * dot(inverse_inertia[a], steering) if a < 3 else 0.) for a in range(8))

    projection = drag_factor * dot(engine_gradient, free_base)
    free_base = tuple(free_base[a] - projection * engine_response[a] for a in range(8))

    def spin(state):
        return tuple(engine_inertia * state[3] * engine_axis[a] - (wheel_inertia * sum(
            state[i + 4] * axes[i][a] for i in range(4)) if rotor else 0.) for a in range(3))

    def known(gyro, exclude=None):
        gyro_response = mobility(tuple(gyro) + (0., 0., 0., 0., 0.))
        free = tuple(free_base[a] + dt * gyro_response[a] + dt * sum(
            forces[i][0] * responses[i][0][a] + forces[i][1] * responses[i][1][a]
            - forces[i][2] * responses[i][2][a] for i in range(4) if i != exclude) for a in range(8))
        end_velocity = tuple(velocity[a] + dt / mass * sum(
            forces[i][0] * frames[i].tangent[a] + forces[i][1] * frames[i].axle[a]
            for i in range(4) if i != exclude) for a in range(3))
        return free, end_velocity

    def shared(guess):
        state = guess
        for _ in range(30):
            free, end_velocity = known(cross(spin(state), state[:3]))
            if ratio:
                (clutch, loss), _speeds = transmission_state(
                    (dot(clutch_gradient, free), dot(gear_gradient, free)),
                    ((dcc, dcl), (dcl, dll)), dt, capacity, efficiency)
            else:
                clutch = loss = 0.
            end = tuple(free[a] - dt * (clutch * mc[a] + loss * ml[a]) for a in range(8))
            error = max(abs(end[a] - state[a]) for a in range(8))
            state = end
            if error < 1e-12:
                return state, end_velocity, clutch, loss
        raise ArithmeticError("曲轴/四轮转子共同末状态超过30次迭代")

    def velocities(index, state, end_velocity):
        frame = frames[index]
        vx = dot(end_velocity, frame.tangent) + dot(state[:3], moments_x[index])
        vy = dot(end_velocity, frame.axle) + dot(state[:3], moments_y[index])
        return vx, vy, (radii[index] * state[index + 4] - vx, -vy)

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
        kappa, alpha = slip_state(vx, vy, state[index + 4], radii[index], car)
        return combined_force(kappa, alpha, grip, cx, cy, car.tire_shape, car.tire_curvature), None

    def solve_wheel(i, gyro):
        free_base_wheel, velocity_base = known(gyro, exclude=i)
        frame, car = frames[i], configurations[i]
        rx, ry, rb = responses[i]
        scale_x = dt * (1 / mass + dot(longitudinal[i], rx))
        scale_y = dt * (1 / mass + dot(lateral[i], ry))

        def local_state(fx, fy):
            free = tuple(free_base_wheel[a] + dt * (rx[a] * fx + ry[a] * fy) for a in range(8))
            if ratio:
                value, _speeds, index = clutch_brake_state(
                    (dot(clutch_gradient, free), dot(gear_gradient, free), dot(brake_gradients[i], free)),
                    local_response[i], dt, capacity, brakes[i], efficiency, plans[i], warm_modes[i])
                warm_modes[i] = index
                local_clutch, local_loss, brake = value
            else:
                local_clutch = local_loss = 0.
                brake = max(-brakes[i], min(brakes[i], dot(brake_gradients[i], free)
                                            / (dt * dot(brake_gradients[i], rb))))
                index = None
            end = tuple(free[a] - dt * (local_clutch * mc[a] + local_loss * ml[a] + brake * rb[a]) for a in range(8))
            velocity_end = tuple(velocity_base[a] + dt / mass * (fx * frame.tangent[a] + fy * frame.axle[a]) for a in range(3))
            return end, velocity_end, brake, index

        def residual(fx, fy):
            end, velocity_end, _brake, _index = local_state(fx, fy)
            target, _details = contact(i, end, velocity_end, fx, fy)
            return fx - target[0], fy - target[1]

        def derivatives(fx, fy):
            end, velocity_end, brake, index = local_state(fx, fy)
            vx, vy, slip = velocities(i, end, velocity_end)
            gradients = []
            for response, direction in ((rx, frame.tangent), (ry, frame.axle)):
                if ratio:
                    active, _sign, columns = plans[i][index]
                    rhs = tuple(dot(g, response) if mode in ("locked", "static") else 0.
                                for g, mode in zip((clutch_gradient, gear_gradient, brake_gradients[i]), active))
                    dc, dl, db = tuple(sum(columns[j][a] * rhs[j] for j in range(3)) for a in range(3))
                else:
                    dc = dl = 0.
                    db = (dot(brake_gradients[i], response) / dot(brake_gradients[i], rb)
                          if abs(brake) < brakes[i] else 0.)
                dq = tuple(dt * (response[a] - dc * mc[a] - dl * ml[a] - db * rb[a]) for a in range(8))
                dx = dt / mass * dot(direction, frame.tangent) + dot(dq[:3], moments_x[i])
                dy = dt / mass * dot(direction, frame.axle) + dot(dq[:3], moments_y[i])
                gradients.append((radii[i] * dq[i + 4] - dx, -dy, dx))
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

    state = initial
    for sweep in range(20):
        state, end_velocity, clutch, loss = shared(state)
        gyro = cross(spin(state), state[:3])
        for i in (range(4) if sweep % 2 == 0 else range(3, -1, -1)):
            forces[i], modes[i] = solve_wheel(i, gyro)

        state, end_velocity, clutch, loss = shared(state)
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
    else:
        raise ArithmeticError(f"传动/四轮共同求解超过20轮：{maximum:g}N，制动{brake_error:g}Nm")

    gyro_torques = bearing_torques(axes, state[4:], wheel_inertia, state[:3]) if rotor else ((0., 0., 0.),) * 4
    wheels = []
    for i, frame in enumerate(frames):
        fx, fy, brake = forces[i]
        vx, vy, _slip = velocities(i, state, end_velocity)
        kappa, alpha = slip_state(vx, vy, state[i + 4], radii[i], configurations[i])
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
        wheels.append(WheelStep(state[i + 4], dot(brake_gradients[i], state), vx, vy, dot(state[:3], axes[i]),
            kappa, alpha, fx, fy, brake, maximum, mode, *elastic, patch_kappa, patch_alpha,
            energy, material, road, numerical, *rate, gyro_torques[i], steering_torques[i]))
    engine_speed = dot(engine_gradient, state)
    clutch_slip, gear_speed = dot(clutch_gradient, state), dot(gear_gradient, state)
    engine_gyro = cross(tuple(engine_inertia * state[3] * value for value in engine_axis), state[:3])
    engine_body = tuple((clutch + engine_drag * engine_speed - engine_torque) * engine_axis[a] + engine_gyro[a] for a in range(3))
    return DrivetrainStep(tuple(wheels), end_velocity, state[:3], state[3], engine_speed, ratio * (clutch - loss),
        clutch, clutch_slip, loss, gear_speed, engine_body, dt * engine_torque * engine_speed,
        dt * engine_drag * engine_speed**2, dt * clutch * clutch_slip, dt * loss * gear_speed, sweep + 1)
