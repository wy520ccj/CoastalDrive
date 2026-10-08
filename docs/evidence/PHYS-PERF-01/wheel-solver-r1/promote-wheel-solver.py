from pathlib import Path
root=Path(__file__).resolve().parents[3]
folder=root/'logs/physics/PHYS-PERF-01'
path=root/'src/mechanical_kernels.c'
source=path.read_text(encoding='utf-8')
source=source.replace('static PyMethodDef methods[] = {',(folder/'wheel-solver-body.c').read_text(encoding='utf-8')+'\nstatic PyMethodDef methods[] = {\n    {"wheel_force_solution", (PyCFunction)wheel_force_solution, METH_VARARGS, "原九维轮端柔性接触力与解析Jacobian共同求解"},')
path.write_text(source,encoding='utf-8')
path=root/'src/tire_drivetrain.py';source=path.read_text(encoding='utf-8')
source=source.replace('    wheel_load_prepared,','    wheel_force_solution,\n    wheel_load_prepared,')
source=source.replace('    configurations = (config, config, rear_config, rear_config)', '''    configurations = (config, config, rear_config, rear_config)
    tire_hardware = tuple((car.slip_speed, car.tire_contact_stiffness, car.tire_contact_damping,
                           car.tire_shape, car.tire_curvature) for car in configurations)''')
source=source.replace('''            if rolling[i]:
                fx, fy, _error = _solve_rolling_force''','''            if shaft:
                fx, fy, _error = wheel_force_solution(wheel_map, i, free_base_wheel, velocity_base, active_limits,
                    warm_branches, warm_modes, frame.tangent, frame.axle, moments_x[i], moments_y[i], radii[i],
                    deformations[i], contact_parameters[i], tire_hardware[i], rolling[i], .0001, guess, math.hypot)
            elif rolling[i]:
                fx, fy, _error = _solve_rolling_force''')
path.write_text(source,encoding='utf-8')
