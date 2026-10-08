import gzip
import json
from pathlib import Path
root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-DESIGN-01-wall'
source = (root / 'docs/evidence/PHYS-PERF-01/suspension-energy-r1/physics/measure-suspension-energy.py').read_text(encoding='utf-8')
template = Path('C:/Users/15120/.codex/worktrees/gr86-physics/CoastalDrive/logs/physics/PHYS-PERF-01/tire-constitutive-snapshots.py').read_text(encoding='utf-8')
template = template[:template.index('old=json.loads')]
template = template.replace("folder=root/'logs/physics/PHYS-PERF-01'", "folder=root/'logs/physics/PHYS-DESIGN-01-wall'")
template = template.replace('tire-constitutive-snapshots.json', 'recontact-snapshots.json')
exec(compile(template, __file__, 'exec'))
old = json.loads(gzip.decompress((root / 'docs/evidence/PHYS-PERF-01/suspension-energy-r1/physics/suspension-energy-snapshots.json.gz').read_bytes()))
result = [{'traffic': a['traffic'], 'new_seconds': a['seconds'], 'old_seconds': b['seconds'],
           'all_fields_equal': a['snapshots'] == b['snapshots']} for a,b in zip(report['cases'],old['cases'])]
(folder / 'recontact-snapshot-comparison.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
