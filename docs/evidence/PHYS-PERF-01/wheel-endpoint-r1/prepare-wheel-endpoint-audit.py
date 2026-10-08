from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-PERF-01'
source = (folder / 'audit-wheel-solver.py').read_text(encoding='utf-8')
source = source.replace("counts={'full_calls'", """def legacy_energy_terms(force, previous, deformation, rate, patch, dt, stiffness, damping):
    energy = .5 * stiffness * sum(value * value for value in deformation)
    material = dt * damping * sum(value * value for value in rate)
    road = dt * sum(force[i] * patch[i] for i in range(2))
    numerical = .5 * stiffness * sum((deformation[i] - previous[i]) ** 2 for i in range(2))
    return energy, material, road, numerical

baseline.energy_terms = legacy_energy_terms
counts={'full_calls'""")
source = source.replace("'bench_cases':0}", "'bench_cases':0,'contact_calls':0,'energy_calls':0,'energy_cases':0}")
source = source.replace('advance=tire_drivetrain.advance_drivetrain', '''import random
from tire_compliance import energy_terms
rng = random.Random(17)
for case in range(512):
    pairs = tuple(tuple(rng.uniform(-1., 1.) * scale for _ in range(2))
                  for scale in (10000., .01, .02, 4., 20.))
    arguments = (*pairs, 1 / (120 if case % 2 else 240), 170000. + case, 850. + case)
    assert hex_tree(energy_terms(*arguments)) == hex_tree(legacy_energy_terms(*arguments)), case
    counts['energy_cases'] += 1

contact = tire_drivetrain.wheel_contact_state
energy = tire_drivetrain.energy_terms
def counted_contact(*args):
    counts['contact_calls'] += 1
    return contact(*args)
def counted_energy(*args):
    counts['energy_calls'] += 1
    return energy(*args)
tire_drivetrain.wheel_contact_state = counted_contact
tire_drivetrain.energy_terms = counted_energy
advance=tire_drivetrain.advance_drivetrain''')
source = source.replace("'scope':'一次功能组旧/新对照，不再次pytest/T1/种子/48拍/profile。'", "'scope':'轮端初值/制动反力、末速度本构和胎体能量功能组的一次旧/新对照；不重复T1/种子/48拍/profile。'")
source = source.replace("'wheel-solver-audit.json'", "'wheel-endpoint-audit.json'")
(folder / 'audit-wheel-endpoint.py').write_text(source, encoding='utf-8')
print('独立旧DLL/原Python及旧能量公式对照已准备。')
