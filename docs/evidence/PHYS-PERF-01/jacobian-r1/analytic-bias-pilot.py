"""含负载偏置的完整11维解析Jacobian试验，先对独立差分再跑原生。"""
import json
import sys
from pathlib import Path
from types import ModuleType

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'src'))
source = (root / 'src/tire_drivetrain.py').read_text(encoding='utf-8')
insert = '''    spin_columns = (tuple(spin(tuple(float(i == j) for i in range(dimensions)))
                          for j in range(dimensions)) if shaft else ())

    def analytic_columns(state):
        branch, mc, ml, _response, _wheels, local, _plans, (mg, port_plans) = branches[shared_branch]
        current_spin = spin(state)
        plan = port_plans[shared_port_index]
        port_gradients = ((clutch_gradient, shaft_gear_gradient, gear_gradient, brake_gradients[0])
                          if hard_gear else (clutch_gradient, shaft_gear_gradient, brake_gradients[0]))
        variables = len(state)
        bias_derivatives = ((0.,) * variables,) * 3
        if torque_bias:
            axial = (tuple(j * (dot(g, state[:dimensions]) - old) / dt for j, g, old in
                           zip(inertias, gradients, downstream_omega)) if downstream else (0.,) * 3)
            output = ratio * (state[dimensions] - state[dimensions + 1])
            share = config.front_drive_share
            torques = (share * output - config.final_drive * (share * axial[0] + axial[1]),
                       (1-share) * output - config.final_drive * ((1-share) * axial[0] + axial[2]))
            derivative_rows = []
            for axle, (torque, bias, limit, weight) in enumerate(zip(torques,
                    config.axle_torque_bias_ratios, limits, (share, 1-share))):
                coefficient = (bias-1.) / (2*(bias+1.))
                slope = (math.copysign(coefficient, torque)
                         if bias > 1. and abs(torque) * coefficient < limit else 0.)
                derivative_rows.append(tuple(slope * (weight * ratio * (float(j == dimensions)
                    - float(j == dimensions+1)) - (config.final_drive / dt *
                    (weight * inertias[0] * gradients[0][j] + inertias[axle+1] * gradients[axle+1][j])
                    if downstream and j < dimensions else 0.)) for j in range(variables)))
            bias_derivatives = (*derivative_rows, (0.,) * variables)
        columns = []
        for j in range(variables):
            gyro_column = cross(spin_columns[j], state[:3]) if j < dimensions else (0.,) * 3
            if j < 3:
                second = cross(current_spin, tuple(float(a == j) for a in range(3)))
                gyro_column = tuple(gyro_column[a] + second[a] for a in range(3))
            direction = mobility(gyro_column + (0.,) * (dimensions - 3))
            if rolling_active and wheel_start <= j < dimensions:
                i = j - wheel_start
                slope = (rolling_coefficients[i] * frames[i].load * radii[i]**2
                         / config.rolling_transition_speed
                         if frames[i].supported and abs(radii[i] * state[j]) < config.rolling_transition_speed else 0.)
                rolling_direction = mobility((0.,) * wheel_start
                    + tuple(-slope if a == i else 0. for a in range(4)))
                direction = tuple(direction[a] + rolling_direction[a] for a in range(dimensions))
            if torque_bias:
                for mode, derivative, response in zip(branch[2], bias_derivatives, differential_responses):
                    if mode:
                        direction = tuple(direction[a] - mode * derivative[j] * response[a]
                                          for a in range(dimensions))
            projected = viscous_projection(direction, branch[0])
            port_direction = tuple(dot(g, projected) for g in port_gradients)
            if hard_gear:
                dc, dg, dl, _db = shaft_brake_response(port_direction, local[0], plan)
            else:
                dc, dg, _db = synchronizer_brake_response(port_direction, plan)
                dl = 0.
            end_column = tuple(dt * (projected[a] - dc * mc[a] - dg * mg[a] - dl * ml[a])
                               for a in range(dimensions))
            if torque_bias:
                end_column += dg, dl
            columns.append(tuple(float(a == j) - end_column[a] for a in range(variables)))
        return columns

'''
source = source.replace('    def shared(guess):\n', insert + '    def shared(guess):\n')
old = '''                columns = []
                for j in range(variables):
                    plus, minus = list(state), list(state)
                    plus[j] += .0001
                    minus[j] -= .0001
                    high, low = mapped(plus)[0], mapped(minus)[0]
                    columns.append(tuple(float(a == j) - (high[a]-low[a])/.0002 for a in range(variables)))
'''
new = '''                if shaft:
                    columns = analytic_columns(state)
                    if len(DERIVATIVE_CHECKS) < 64:
                        original_partition = shared_branch, shared_port_index
                        numeric, partitions = [], []
                        for j in range(variables):
                            plus, minus = list(state), list(state)
                            plus[j] += .0001
                            minus[j] -= .0001
                            high = mapped(plus)[0]
                            partitions.append((shared_branch, shared_port_index))
                            low = mapped(minus)[0]
                            partitions.append((shared_branch, shared_port_index))
                            numeric.append(tuple(float(a == j) - (high[a]-low[a])/.0002 for a in range(variables)))
                        mapped(state)
                        if all(partition == original_partition for partition in partitions):
                            error = max(abs(a-b) / max(1.,abs(a),abs(b))
                                        for x,y in zip(columns,numeric) for a,b in zip(x,y))
                            DERIVATIVE_CHECKS.append(error)
                            assert error < 2e-6, error
                else:
                    columns = []
                    for j in range(variables):
                        plus, minus = list(state), list(state)
                        plus[j] += .0001
                        minus[j] -= .0001
                        high, low = mapped(plus)[0], mapped(minus)[0]
                        columns.append(tuple(float(a == j) - (high[a]-low[a])/.0002 for a in range(variables)))
'''
assert source.count(old) == 1
source = source.replace(old, new)
module = ModuleType('tire_drivetrain')
module.DERIVATIVE_CHECKS = []
sys.modules['tire_drivetrain'] = module
exec(compile(source, 'analytic-bias-pilot-tire_drivetrain.py', 'exec'), module.__dict__)
script = root / 'logs/physics/PHYS-PERF-01/compare_ticks.py'
sys.argv = [str(script), str(root / 'logs/physics/PHYS-PERF-01/analytic-bias-pilot-snapshots.json')]
exec(compile(script.read_text(encoding='utf-8'), str(script), 'exec'), {'__file__': str(script)})
result = {'in_memory_only': True, 'checks': len(module.DERIVATIVE_CHECKS),
          'max_jacobian_relative_error': max(module.DERIVATIVE_CHECKS), 'status': 'completed'}
(root / 'logs/physics/PHYS-PERF-01/analytic-bias-pilot.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
