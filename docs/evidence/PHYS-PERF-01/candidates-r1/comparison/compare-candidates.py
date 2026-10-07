import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-PERF-01'
before = json.loads((folder / 'native-projection-snapshots.json').read_text(encoding='utf-8'))
after = json.loads((folder / 'candidate-cache-snapshots.json').read_text(encoding='utf-8'))
cases = []
for first, second in zip(before['cases'], after['cases'], strict=True):
    assert first['traffic'] == second['traffic']
    assert first['snapshots'] == second['snapshots']
    cases.append({'traffic': first['traffic'], 'snapshot_all_fields_equal': True,
                  'ticks': len(second['snapshots']), 'before_s': first['seconds'], 'after_s': second['seconds'],
                  'reduction_percent': 100 * (1-second['seconds']/first['seconds'])})
report = {'passed': True, 'cases': cases, 'files': {
    str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (root / 'src').iterdir() if path.suffix in ('.py', '.c', '.pyd')}}
(folder / 'candidate-cache-comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(cases))
