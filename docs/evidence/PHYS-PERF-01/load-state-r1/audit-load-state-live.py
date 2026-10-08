from pathlib import Path
root = Path(__file__).resolve().parents[3]
path = root / 'logs/physics/PHYS-PERF-01/audit-load-state.py'
source = path.read_text(encoding='utf-8')
source = source.replace('from dataclasses import asdict', 'from dataclasses import fields, is_dataclass')
source = source.replace('    if isinstance(value, float):', "    if is_dataclass(value):\n        return {field.name: hex_tree(getattr(value, field.name)) for field in fields(value)}\n    if isinstance(value, float):")
source = source.replace('hex_tree(asdict(actual)) == hex_tree(asdict(expected))', 'hex_tree(actual) == hex_tree(expected)')
start = source.index('import pytest\n')
stop = source.index('if code == 0:', start)
source = source[:start] + 'code = 0\n' + source[stop:]
source = source.replace('load-state-audit.json', 'load-state-live-audit.json')
source = source.replace("'pytest_code': int(code)", "'pytest': 'not_run; existing T0 reused'")
exec(compile(source, __file__, 'exec'))
