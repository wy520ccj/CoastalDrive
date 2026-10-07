import json
import random
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'src'))
from mechanical_kernels import wheel_load_terms

source = subprocess.run(['git', 'show', 'e79af19:src/tire_drivetrain.py'], cwd=root,
                        capture_output=True, text=True, encoding='utf-8', check=True).stdout
begin, end = source.index('    def load_terms('), source.index('    def known(')
space = {}
exec(textwrap.dedent(source[begin:end]), space)
rng = random.Random(23)
count = 0
for dimensions in (8, 9):
    for has_suspension in (False, True):
        for _ in range(64):
            forces = tuple(tuple(rng.uniform(-1e5, 1e5) for _ in range(3)) for _ in range(4))
            responses = tuple(tuple(tuple(rng.uniform(-.2, .2) for _ in range(dimensions)) for _ in range(3)) for _ in range(4))
            tangents, axles = (tuple(tuple(rng.uniform(-1., 1.) for _ in range(3)) for _ in range(4)) for _ in range(2))
            normal_forces = tuple(rng.uniform(0., 1e5) for _ in range(4))
            normal_responses = tuple(tuple(rng.uniform(-.1, .1) for _ in range(dimensions)) for _ in range(4))
            gradients = tuple(tuple(rng.uniform(-1., 1.) for _ in range(6)) for _ in range(4))
            velocity = tuple(rng.uniform(-100., 100.) for _ in range(3))
            frames = tuple(SimpleNamespace(tangent=t, axle=a) for t, a in zip(tangents, axles))
            suspension = SimpleNamespace(gradients=gradients) if has_suspension else None
            space.update(forces=forces, responses=responses, frames=frames, velocity=velocity,
                         normal_forces=normal_forces, normal_responses=normal_responses,
                         suspension=suspension, mass=1287.29514606, dt=1/240, dimensions=dimensions)
            for exclude in (None, 0, 1, 2, 3):
                old = space['load_terms'](exclude)
                new = wheel_load_terms(forces, responses, tangents, axles, velocity, 1/240, 1287.29514606,
                    normal_forces if has_suspension else None, normal_responses, gradients, exclude, dimensions)
                assert old == new, (dimensions, has_suspension, exclude, old, new)
                count += 1
report = {'passed': True, 'exact_calls': count, 'reference': 'e79af19'}
Path(__file__).with_name('load-terms-exact.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
