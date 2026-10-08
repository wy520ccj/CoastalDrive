import hashlib
import inspect
import json
import sys
from pathlib import Path
root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-PERF-01'
sys.path[:0] = [str(root / 'src'), str(folder / 'triangle-packet-baseline')]
import _triangle_packet_old
import triangle_support
old_kernel = _triangle_packet_old.triangle_support_entry
new_kernel = triangle_support.triangle_support_entry
counts = {'queries': 0, 'hits': 0}
def hex_tree(value):
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, tuple):
        return tuple(hex_tree(item) for item in value)
    return value
def audited(*args, **kwargs):
    node = inspect.currentframe().f_back.f_locals['self']
    expected = old_kernel(node, *args[1:], **kwargs)
    actual = new_kernel(*args, **kwargs)
    assert hex_tree(actual) == hex_tree(expected), (counts, args[1:], actual, expected)
    counts['queries'] += 1
    counts['hits'] += actual is not None
    return actual
triangle_support.triangle_support_entry = audited
import pytest
code = pytest.main(['-q', 'tests/test_triangle_support.py', 'tests/test_suspension_candidates.py', 'tests/test_suspension_query_lifetime.py'])
if code == 0:
    from simulation import Simulation, Control
    from vehicle_designs import GR86_DESIGN
    from driver_assist import GAME_INPUT
    sim = Simulation(17, track='coastal', traffic_count=8, config=GR86_DESIGN, input_config=GAME_INPUT)
    try:
        for tick in range(24):
            sim.step(Control(throttle=.3))
    finally:
        sim.close()
baseline_dll = next((folder / 'triangle-packet-baseline').glob('*.pyd'))
report = {'baseline': 'ae6f8b1 query body rebuilt as independent old DLL; strict /fp:strict /utf-8',
          'baseline_dll_sha256': hashlib.sha256(baseline_dll.read_bytes()).hexdigest(),
          'pytest_code': int(code), 'all_query_hex_equal': code == 0, 'counts': counts,
          'scope': '本功能组一次相关短检查及真实查询对照；未重跑整套T1/种子/48拍/profile。'}
(folder / 'triangle-packet-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
raise SystemExit(code)
