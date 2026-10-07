"""相同短输入的全部Snapshot与实际墙钟保存，供纯性能改动对照。"""
import hashlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'src'))
from driver_assist import GAME_INPUT
from simulation import Simulation
from vehicle_designs import GR86_DESIGN
from vehicle_state import Control

path = Path(sys.argv[1])
sources = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
           for p in (root / 'src').glob('*.py')}
rows = []
for traffic in (0, 8):
    sim = Simulation(17, track='coastal', traffic_count=traffic,
                     config=GR86_DESIGN, input_config=GAME_INPUT)
    try:
        snapshots, clocks = [], []
        for tick in range(48):
            started = time.perf_counter()
            sim.step(Control(throttle=.3, steering=.02 if tick >= 24 else 0.))
            clocks.append(time.perf_counter() - started)
            state = asdict(sim.snapshot())
            state['player']['contact_epoch'] = 0
            for car in state['traffic']:
                car['contact_epoch'] = 0
            snapshots.append(state)
        rows.append({'traffic': traffic, 'tick_count': len(clocks),
                     'seconds': sum(clocks), 'tick_seconds': clocks, 'snapshots': snapshots})
    finally:
        sim.close()
assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
           for name, digest in sources.items())
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({'sources': sources, 'cases': rows}), encoding='utf-8')
print(json.dumps([{'traffic': row['traffic'], 'seconds': row['seconds']} for row in rows]))
