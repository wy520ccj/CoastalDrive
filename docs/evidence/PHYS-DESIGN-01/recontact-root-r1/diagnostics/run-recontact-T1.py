import hashlib
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'tools'))
from validate import execute_plan, git_value, make_plan
old = json.loads((root / 'logs/validation/PHYS-INTEGRATE-04-wall-T1/summary.json').read_text(encoding='utf-8'))
energy = json.loads((root / 'docs/evidence/PHYS-PERF-01/suspension-energy-r1/validation/T1/summary.json').read_text(encoding='utf-8'))
tests = sorted(set(old['tests'] + energy['tests'] + [
    'tests/test_tcs_probe.py', 'tests/test_tcs_integration.py', 'tests/test_abs_integration.py',
    'tests/test_esc_integration.py', 'tests/test_wheel_dynamics.py', 'tests/test_tire_compliance.py']))
files = sorted(p for area in ('src', 'tests', 'tools') for p in (root / area).rglob('*') if p.suffix in ('.py', '.c', '.pyd', '.json', '.gz'))
files.append(root / 'setup.py')
capture = lambda: {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
before = capture()
output = root / 'logs/validation/PHYS-INTEGRATE-05-recontact-T1'
metadata = {'git_head': git_value('rev-parse', 'HEAD'), 'git_status': git_value('status', '--short'),
            'tests': tests, 'source_sha256_start': before,
            'scope': '整合严格数值性能块与滚动接触力括根。实际隐式方程/1e-4N/120Hz保持；20纵向与每次最多20横向迭代，非原二维Newton轨迹。'}
code = execute_plan(make_plan('T1', [], tests, output), output, 'T1', 1200, metadata)
summary_path = output / 'summary.json'
summary = json.loads(summary_path.read_text(encoding='utf-8'))
summary['source_sha256_end'] = capture()
summary['source_hashes_equal'] = before == summary['source_sha256_end']
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert summary['source_hashes_equal']
raise SystemExit(code)
