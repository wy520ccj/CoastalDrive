import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
sys.path[:0] = [str(root/'src'), str(folder/'support-lib')]
import _support_probe
import wheel_envelope

wheel_envelope._cylinder_point_delta = _support_probe.cylinder_point_delta
wheel_envelope._cylinder_edge_distance = _support_probe.cylinder_edge_distance
if len(sys.argv) > 1 and sys.argv[1] == 'tests':
    import pytest
    raise SystemExit(pytest.main(['-q','tests/test_cylinder_suspension.py','tests/test_triangle_support.py',
                                 'tests/test_suspension_query_lifetime.py','tests/test_ramp_contact_step.py']))
script = folder/'compare_ticks.py'
sys.argv = [str(script), str(folder/'edge-pilot-snapshots.json')]
exec(compile(script.read_text(encoding='utf-8'), str(script), 'exec'), {'__file__':str(script)})
before = json.loads((folder/'wheel-production-snapshots.json').read_text(encoding='utf-8'))
after = json.loads((folder/'edge-pilot-snapshots.json').read_text(encoding='utf-8'))
rows = []
for first, second in zip(before['cases'], after['cases'], strict=True):
    assert first['snapshots'] == second['snapshots']
    rows.append({'traffic':first['traffic'],'snapshots_all_equal':True,
                 'before_s':first['seconds'],'after_s':second['seconds']})
(folder/'edge-pilot-comparison.json').write_text(json.dumps({'in_memory_only':True,'cases':rows},indent=2),encoding='utf-8')
print(json.dumps(rows))
