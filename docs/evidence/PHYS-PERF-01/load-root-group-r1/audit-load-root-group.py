import inspect
import json
import sys
import types
from dataclasses import fields, is_dataclass
from pathlib import Path
root = Path(__file__).resolve().parents[3]
folder = root / 'logs/physics/PHYS-PERF-01'
sys.path[:0] = [str(root / 'src'), str(root / 'tools')]
import tire_drivetrain
import wheel_dynamics
baseline = types.ModuleType('_load_root_group_original')
sys.modules[baseline.__name__] = baseline
exec(compile((folder / 'load-parameters-baseline-tire.py').read_text(encoding='utf-8'), 'cc2b3da-tire', 'exec'), baseline.__dict__)
wheel_source = (folder / 'load-parameters-baseline-wheel.py').read_text(encoding='utf-8')
start = wheel_source.index('def _solve_rolling_force(')
namespace = {'math': wheel_dynamics.math}
exec(compile(wheel_source[start:], 'cc2b3da-wheel-root', 'exec'), namespace)
baseline._solve_rolling_force = namespace['_solve_rolling_force']
counts = {'full_drivetrain_calls': 0, 'native_root_calls': 0}
def hex_tree(value):
    if is_dataclass(value):
        return {field.name: hex_tree(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, (tuple, list)):
        return [hex_tree(item) for item in value]
    return value
advance = tire_drivetrain.advance_drivetrain
native_root = tire_drivetrain._solve_rolling_force
def root_counted(*args, **kwargs):
    counts['native_root_calls'] += 1
    return native_root(*args, **kwargs)
tire_drivetrain._solve_rolling_force = root_counted
def audited(*args, **kwargs):
    expected = baseline.advance_drivetrain(*args, **kwargs)
    actual = advance(*args, **kwargs)
    assert hex_tree(actual) == hex_tree(expected), counts
    counts['full_drivetrain_calls'] += 1
    return actual
tire_drivetrain.advance_drivetrain = audited
import vehicle_tires
vehicle_tires.advance_drivetrain = audited
from physics.tcs_probe import run_trial
for enabled in (False, True):
    summary, rows = run_trial('airborne-recontact', enabled, 2.)
    assert all(row[f'state.wheel_dynamics.{i}.sample_support'] for row in rows[-60:] for i in range(4))
from simulation import Simulation, Control
from vehicle_designs import GR86_DESIGN
from driver_assist import GAME_INPUT
sim = Simulation(17, track='coastal', traffic_count=8, config=GR86_DESIGN, input_config=GAME_INPUT)
try:
    for tick in range(24):
        sim.step(Control(throttle=.3))
finally:
    sim.close()
report = {'baseline': 'cc2b3da wheel loads; independent old Python root control flow',
          'all_full_step_hex_and_references_equal': True, 'counts': counts,
          'scope': '一次功能组对照；无pytest/T1/三种子重复执行。'}
(folder / 'load-root-group-audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False))
