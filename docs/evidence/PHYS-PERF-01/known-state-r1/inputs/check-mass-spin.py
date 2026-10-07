import json
import random
import subprocess
import sys
import textwrap
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'src'))
from driveline_inertia import inertia_projections, project_inertia
from mechanical_kernels import dot, mass_response, rotor_spin

source = subprocess.run(['git', 'show', 'e79af19:src/tire_drivetrain.py'], cwd=root,
                        capture_output=True, text=True, encoding='utf-8', check=True).stdout
space = {'dot': dot, 'project_inertia': project_inertia}
for name, next_name in (('base_inverse_mass', '    downstream ='), ('inverse_mass', '    engine_response ='),
                         ('mobility', '    normal_forces ='), ('spin', '    def load_terms(')):
    begin = source.index('    def ' + name + '(')
    end = source.index(next_name, begin)
    exec(textwrap.dedent(source[begin:end]), space)
rng = random.Random(17)
counts = {'mass_response': 0, 'rotor_spin': 0}
for shaft in (False, True):
    n = 9 if shaft else 8
    for rotor in (False, True):
        for downstream in (False, True):
            for scale in (1e-6, 1., 1e6):
                for _ in range(32):
                    axes = tuple(tuple(rng.uniform(-1, 1) for _ in range(3)) for _ in range(4))
                    engine_axis, shaft_axis = (0., 1., 0.), (.01, .999, .02)
                    matrix = tuple(tuple(rng.uniform(-.001, .001) for _ in range(3)) for _ in range(3))
                    gradients = tuple(tuple(rng.uniform(-1, 1) for _ in range(n)) for _ in range(3)) if downstream else ()
                    inertias = (.013, 0., .005) if downstream else ()
                    down_axes = ((0., 1., 0.), (.01, .999, .02), (.02, .995, .03)) if downstream else ()
                    space.update(shaft=shaft, rotor=rotor, downstream=downstream, dimensions=n,
                                 wheel_start=5 if shaft else 4, inverse_inertia=matrix,
                                 engine_inertia=.2, wheel_inertia=1.12, shaft_inertia=.04 if shaft else None,
                                 engine_axis=engine_axis, shaft_axis=shaft_axis, axes=axes,
                                 gradients=gradients, inertias=inertias, downstream_axes=down_axes)
                    projections = inertia_projections(space['base_inverse_mass'], gradients, inertias)
                    space['downstream_projections'] = projections
                    response = space['inverse_mass']((0., 0., 0., 1., *((0.,) * (n-4))))
                    space.update(engine_response=response, drag_factor=.0017)
                    vector = tuple(scale * rng.uniform(-1000, 1000) for _ in range(n))
                    for name, p, d, r in (('base_inverse_mass', (), 0., None),
                                         ('inverse_mass', projections, 0., None),
                                         ('mobility', projections, .0017, response)):
                        actual = mass_response(vector, matrix, .2, .04 if shaft else None, 1.12, p, d, r)
                        assert space[name](vector) == actual, (name, shaft, rotor, downstream, vector)
                        counts['mass_response'] += 1
                    assert space['spin'](vector) == rotor_spin(vector, .2, engine_axis, 1.12, axes, rotor,
                        .04 if shaft else None, shaft_axis, inertias, gradients, down_axes)
                    counts['rotor_spin'] += 1
report = {'passed': True, 'exact_calls': counts, 'reference': 'e79af19'}
Path(__file__).with_name('mass-spin-exact.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
