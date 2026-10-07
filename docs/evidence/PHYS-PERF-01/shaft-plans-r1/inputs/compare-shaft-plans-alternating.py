import hashlib
import json
import subprocess
import sys
import time
import types
from dataclasses import asdict
from pathlib import Path

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent
sys.path.insert(0, str(root / 'src'))
import vehicle_tires
from driver_assist import GAME_INPUT
from simulation import Simulation
from vehicle_designs import GR86_DESIGN
from vehicle_state import Control

old = types.ModuleType('mechanical_comparison_baseline')
sys.modules[old.__name__] = old
source = subprocess.run(['git', 'show', '16a7c4a:src/shaft_transmission.py'], cwd=root,
                        capture_output=True, text=True, encoding='utf-8', check=True).stdout
exec(compile(source, '16a7c4a:src/shaft_transmission.py', 'exec'), old.__dict__)
import tire_drivetrain
native = tire_drivetrain.shaft_brake_plans
sources = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
           for path in (root / 'src').rglob('*') if path.suffix in ('.py', '.c', '.pyd')}
rows = []
for label, method in (('python', old.shaft_brake_plans), ('native', native),
                       ('native', native), ('python', old.shaft_brake_plans)):
    tire_drivetrain.shaft_brake_plans = method
    sim = Simulation(17, track='coastal', traffic_count=8, config=GR86_DESIGN, input_config=GAME_INPUT)
    try:
        snapshots, wall, cpu = [], [], []
        for tick in range(48):
            started, cpu_start = time.perf_counter(), time.process_time()
            sim.step(Control(throttle=.3, steering=.02 if tick >= 24 else 0.))
            wall.append(time.perf_counter() - started)
            cpu.append(time.process_time() - cpu_start)
            state = asdict(sim.snapshot())
            state['contact_epoch'] = 0
            snapshots.append(state)
        if rows:
            assert rows[0]['snapshots'] == snapshots
        rows.append({'algorithm': label, 'wall_s': sum(wall), 'cpu_s': sum(cpu), 'snapshots': snapshots})
        print(json.dumps({'algorithm': label, 'wall_s': sum(wall), 'cpu_s': sum(cpu),
                          'all_physical_snapshot_fields_equal': True}), flush=True)
    finally:
        sim.close()
tire_drivetrain.shaft_brake_plans = native
assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest for name, digest in sources.items())
(folder / 'shaft-plans-alternating-snapshots.json').write_text(json.dumps({'passed': True, 'sources': sources, 'cases': rows}), encoding='utf-8')

