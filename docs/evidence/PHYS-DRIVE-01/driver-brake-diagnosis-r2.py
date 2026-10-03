"""原玩家制动/倒车门槛完整轨迹，有限齿比执行器另列等待。"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'src')]

from driver_assist import GAME_INPUT
from simulation import Control, Simulation
from vehicle_state import FIXED_DT

OUT = Path(__file__).with_suffix('')
OUT.mkdir(exist_ok=False)
s = Simulation()
rows = []


def record(phase):
    state = s.snapshot().player
    power = state.powertrain_state
    rows.append({'tick': s.snapshot().tick, 'phase': phase, 'speed': state.speed,
                 'throttle_command': state.throttle, 'brake_command': state.brake,
                 'throttle_executed': power.throttle, 'gear': power.gear,
                 'pending_gear': s.player.powertrain.pending_gear,
                 'shift_phase': power.shift_phase, 'clutch_capacity': power.clutch_capacity,
                 'drive_torque': power.drive_torque, 'reverse_wait': s.player.assist.reverse_wait,
                 'wheel_energy': sum(.5*s.config.wheel_inertia*w.omega**2 for w in state.wheel_dynamics),
                 'engine_rpm': state.rpm})


def step(control, phase):
    s.step(control)
    record(phase)


try:
    for _ in range(240):
        step(Control(), 'settle')
    for _ in range(240):
        step(Control(throttle=1), 'accelerate')
    for _ in range(round(1/GAME_INPUT.brake_rise/FIXED_DT)):
        step(Control(throttle=1, brake=1), 'brake-rise')
    for _ in range(1200):
        if abs(s.snapshot().player.speed) < .15:
            break
        step(Control(brake=1), 'brake-to-stop')
    for _ in range(round(GAME_INPUT.reverse_delay/FIXED_DT)):
        step(Control(brake=1), 'reverse-input-wait')
    for _ in range(round(s.config.shift_time/FIXED_DT)):
        if s.snapshot().player.gear == -1:
            break
        step(Control(brake=1), 'gear-actuator-wait')
    for _ in range(60):
        step(Control(brake=1), 'reverse-launch')
    with (OUT / 'trace.csv').open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle, rows[0])
        writer.writeheader()
        writer.writerows(rows)
    report = {'source_manifest': '../validation-T1-r2-source-before.json',
              'rows': len(rows), 'phase_first_last': {phase:[next(r for r in rows if r['phase']==phase),
                next(r for r in reversed(rows) if r['phase']==phase)] for phase in dict.fromkeys(r['phase'] for r in rows)}}
    (OUT / 'summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
finally:
    s.close()
