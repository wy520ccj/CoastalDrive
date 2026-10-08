from pathlib import Path
root = Path(__file__).resolve().parents[3]
main = Path('B:/AI agent/暑期计算机程序设计/CoastalDrive')
folder = root / 'logs/physics/PHYS-PERF-01'
for name in ('src/tire_drivetrain.py', 'src/wheel_dynamics.py', 'tests/test_tcs_probe.py'):
    (root / name).write_bytes((main / name).read_bytes())
path = root / 'src/tire_drivetrain.py'
source = path.read_text(encoding='utf-8')
(folder / 'load-state-baseline-tire.py').write_text(source, encoding='utf-8')
source = source.replace('from dataclasses import dataclass, replace', 'from dataclasses import dataclass')
source = source.replace('    normal_forces = (0.,) * 4', '    wheel_loads = tuple(frame.load for frame in frames)\n    normal_forces = (0.,) * 4')
source = source.replace('''        nonlocal frames
        frames = tuple(replace(frame, load=force / alignment if frame.supported and contact and force > 0. else 0.)
                       for frame, force, alignment, contact in''', '''        nonlocal wheel_loads
        # 支持几何在本次推进内固定，法向力只刷新四个实际轮荷。
        wheel_loads = tuple(force / alignment if frame.supported and contact and force > 0. else 0.
                       for frame, force, alignment, contact in''')
source = source.replace('tuple(frame.load for frame in frames),', 'wheel_loads,')
source = source.replace('static = tuple((frame.load > 0', 'static = tuple((wheel_loads[i] > 0')
start = source.index('    def contact(index,')
stop = source.index('    def solve_wheel(', start)
source = source[:start] + source[start:stop].replace('frame.load', 'wheel_loads[index]') + source[stop:]
source = source.replace('frame.load', 'wheel_loads[i]')
# 唯一初始化仍从调用方给出的接点读取轮荷。
source = source.replace('wheel_loads = tuple(wheel_loads[i] for frame in frames)', 'wheel_loads = tuple(frame.load for frame in frames)')
source = source.replace('frames[i].load', 'wheel_loads[i]')
source = source.replace('                                               config.rolling_transition_speed)',
                        '                                               config.rolling_transition_speed, loads=wheel_loads)')
assert 'replace(' not in source
assert source.count('frame.load') == 1
path.write_text(source, encoding='utf-8')
path = root / 'src/rolling_resistance.py'
source = path.read_text(encoding='utf-8')
source = source.replace('transition_speed):', 'transition_speed, *, loads=None):')
source = source.replace('    return tuple(coefficient * frame.load', '    actual_loads = tuple(frame.load for frame in frames) if loads is None else loads\n    return tuple(coefficient * load')
source = source.replace('for frame,radius,spin,coefficient in zip(frames,radii,spins,coefficients)', 'for frame,load,radius,spin,coefficient in zip(frames,actual_loads,radii,spins,coefficients)')
path.write_text(source, encoding='utf-8')
