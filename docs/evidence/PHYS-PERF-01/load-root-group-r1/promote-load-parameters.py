from pathlib import Path
root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-PERF-01'
folder.mkdir(parents=True, exist_ok=True)
path = root / 'src/tire_drivetrain.py'
source = path.read_text(encoding='utf-8')
(folder / 'load-parameters-baseline-tire.py').write_text(source, encoding='utf-8')
(folder / 'load-parameters-baseline-wheel.py').write_bytes((root / 'src/wheel_dynamics.py').read_bytes())
source = source.replace('    configurations = (config, config, rear_config, rear_config)\n', '')
source = source.replace('    wheel_loads = tuple(frame.load for frame in frames)', '''    configurations = (config, config, rear_config, rear_config)
    wheel_loads = tuple(frame.load for frame in frames)

    def load_parameters():
        # 轮荷刷新时重算本构参数，后续力/Jacobian试探共用同一组数值。
        return tuple((tire_grip(load, frame.mu, car), *tire_stiffness(load, car))
                     for load, frame, car in zip(wheel_loads, frames, configurations))

    contact_parameters = load_parameters()''')
source = source.replace('        nonlocal wheel_loads', '        nonlocal wheel_loads, contact_parameters')
source = source.replace('zip(frames, normal_forces, suspension.alignment, suspension.touching))',
                        'zip(frames, normal_forces, suspension.alignment, suspension.touching))\n        contact_parameters = load_parameters()')
source = source.replace('        grip = tire_grip(wheel_loads[index], frame.mu, car)\n        cx, cy = tire_stiffness(wheel_loads[index], car)',
                        '        grip, cx, cy = contact_parameters[index]')
source = source.replace('tire_grip(wheel_loads[i], frame.mu, car)', 'contact_parameters[i][0]')
source = source.replace('*tire_stiffness(wheel_loads[i], car)', '*contact_parameters[i][1:]')
source = source.replace('stiffnesses = tire_stiffness(wheel_loads[i], car)', 'stiffnesses = contact_parameters[i][1:]')
source = source.replace('tire_grip(wheel_loads[i], frames[i].mu, configurations[i])', 'contact_parameters[i][0]')
assert source.count('tire_grip(') == source.count('tire_stiffness(') == 1
path.write_text(source, encoding='utf-8')
