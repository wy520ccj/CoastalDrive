import json
import sys
import types
from dataclasses import asdict
from pathlib import Path
root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'src'))
import tire_drivetrain
folder = root / 'logs/physics/PHYS-PERF-01'
baseline = types.ModuleType('_load_state_original')
sys.modules[baseline.__name__] = baseline
exec(compile((folder / 'load-state-baseline-tire.py').read_text(encoding='utf-8'), 'original-load-state', 'exec'), baseline.__dict__)
original_replace = baseline.replace
counts = {'calls': 0, 'original_frame_rebuilds': 0}
def replaced(*args, **kwargs):
    counts['original_frame_rebuilds'] += 1
    return original_replace(*args, **kwargs)
baseline.replace = replaced
actual_advance = tire_drivetrain.advance_drivetrain
def hex_tree(value):
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {key: hex_tree(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [hex_tree(item) for item in value]
    return value
def audited(*args, **kwargs):
    expected = baseline.advance_drivetrain(*args, **kwargs)
    actual = actual_advance(*args, **kwargs)
    assert hex_tree(asdict(actual)) == hex_tree(asdict(expected)), counts
    counts['calls'] += 1
    return actual
tire_drivetrain.advance_drivetrain = audited
import vehicle_tires
vehicle_tires.advance_drivetrain = audited
import pytest
code = pytest.main(['-q', 'tests/test_tire_drivetrain.py', 'tests/test_tire_shaft.py', 'tests/test_joint_suspension.py', 'tests/test_guardrail_suspension.py', 'tests/test_tcs_probe.py'])
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
report = {'baseline': 'main 98f86e3 plus pending bounded rolling root, original ContactFrame load replacement',
          'pytest_code': int(code), 'all_full_step_hex_equal': code == 0, 'counts': counts}
(folder / 'load-state-audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report))
raise SystemExit(code)
