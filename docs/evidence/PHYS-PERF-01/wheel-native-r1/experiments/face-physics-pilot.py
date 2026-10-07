import importlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
sys.path[:0] = [str(root/'src'), str(folder/'support-lib')]
import _support_probe

for name in ('wheel_envelope', 'triangle_support', 'suspension_kinematics', 'wheel_geometry'):
    module = importlib.import_module(name)
    module.cylinder_support = _support_probe.cylinder_support
import triangle_support

source = (root/'src/triangle_support.py').read_text(encoding='utf-8')
first = source.index('    a, b, c = triangle\n')
last = source.index('    if face_only:\n        return None\n', first) + len('    if face_only:\n        return None\n')
source = source[:first] + '''    finished, hit = _support_probe.triangle_face(start, end, triangle, margin, axis, radius, width, shoulder, crown,
                                                face_only=face_only, ceiling=ceiling)
    if finished:
        return hit
    velocity = subtract(end, start)
''' + source[last:]
triangle_support._support_probe = _support_probe
exec(compile(source, str(root/'src/triangle_support.py'), 'exec'), triangle_support.__dict__)
triangle_support.cylinder_support = _support_probe.cylinder_support

if len(sys.argv) > 1 and sys.argv[1] == 'tests':
    import pytest
    raise SystemExit(pytest.main(['-q','tests/test_cylinder_suspension.py','tests/test_triangle_support.py',
                                 'tests/test_suspension_query_lifetime.py','tests/test_ramp_contact_step.py']))
script = folder/'compare_ticks.py'
sys.argv = [str(script), str(folder/'face-pilot-snapshots.json')]
exec(compile(script.read_text(encoding='utf-8'), str(script), 'exec'), {'__file__':str(script)})
before = json.loads((folder/'candidate-cache-snapshots.json').read_text(encoding='utf-8'))
after = json.loads((folder/'face-pilot-snapshots.json').read_text(encoding='utf-8'))
rows = []
for first, second in zip(before['cases'], after['cases'], strict=True):
    assert first['snapshots'] == second['snapshots']
    rows.append({'traffic':first['traffic'],'snapshots_all_equal':True,
                 'before_s':first['seconds'],'after_s':second['seconds']})
(folder/'face-pilot-comparison.json').write_text(json.dumps({'in_memory_only':True,'cases':rows},indent=2),encoding='utf-8')
print(json.dumps(rows))
