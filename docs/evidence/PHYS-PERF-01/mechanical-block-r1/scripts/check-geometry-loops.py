import json
import math
import random
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'src'))
from rotor_dynamics import cross, dot
from wheel_contact_kernels import box_interval, rotated_path

space = {'math': math, 'cross': cross, 'dot': dot}
for filename, function, following in (('suspension_geometry.py', 'box_interval', 'box_entry'),
                                       ('suspension_kinematics.py', 'rotated_path', 'finite_contact_system')):
    source = subprocess.run(['git', 'show', '11c7c07:src/' + filename], cwd=root,
                            capture_output=True, text=True, encoding='utf-8', check=True).stdout
    begin = source.index('def ' + function + '(')
    end = source.index('\ndef ' + following + '(', begin)
    exec(source[begin:end], space)
rng = random.Random(23)
counts = {'box': 0, 'rotation': 0}
for scale in (1e-12, 1., 1e6, 1e12):
    for _ in range(128):
        start = tuple(rng.uniform(-2, 2) * scale for _ in range(3))
        end = tuple(rng.uniform(-2, 2) * scale for _ in range(3))
        half = tuple(rng.uniform(.1, 2) * scale for _ in range(3))
        for stop in (start, end):
            assert space['box_interval'](start, stop, half) == box_interval(start, stop, half)
            counts['box'] += 1
        axis = tuple(rng.uniform(-1, 1) for _ in range(3))
        length = math.sqrt(dot(axis, axis))
        axis = tuple(value / length for value in axis)
        for angle in (0., 1e-12, rng.uniform(-3, 3)):
            factor = rng.uniform(.1, 1)
            assert space['rotated_path'](start, axis, angle, factor) == rotated_path(start, axis, angle, factor)
            counts['rotation'] += 1
report = {'passed': True, 'exact_calls': counts, 'reference': '11c7c07'}
Path(__file__).with_name('geometry-loops-exact.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
