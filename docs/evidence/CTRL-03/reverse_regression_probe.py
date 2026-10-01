"""保留原制动转倒车时序，用独立源码根定位电子介入与旧基线行为。"""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--tcs-off", action="store_true")
parser.add_argument("--esc-off", action="store_true")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source.resolve()))
from driver_assist import GAME_INPUT
from simulation import FIXED_DT, Control, Simulation
from vehicle_config import CAR

config = CAR
if args.tcs_off:
    config = replace(config, traction=replace(config.traction, tcs_enabled=False))
if args.esc_off:
    config = replace(config, stability=replace(config.stability, esc_enabled=False))
sim = Simulation(config=config)
try:
    for _ in range(240):
        sim.step(Control())
    for _ in range(240):
        sim.step(Control(throttle=1))
    previous_speed = sim.snapshot().player.speed
    for _ in range(round(1 / GAME_INPUT.brake_rise / FIXED_DT)):
        sim.step(Control(throttle=1, brake=1))
    for _ in range(1200):
        if abs(sim.snapshot().player.speed) < .15:
            break
        sim.step(Control(brake=1))
    stop_tick = sim.snapshot().tick
    rows = []
    for _ in range(100):
        sim.step(Control(brake=1))
        state = sim.snapshot().player
        rows.append({"tick": sim.snapshot().tick, "speed": state.speed, "gear": state.gear,
                     "torque_scale": state.traction_state.torque_scale,
                     "tcs_active": state.traction_state.active,
                     "rear_slips": state.traction_state.wheel_slips[2:],
                     "drive_torque": sim.player.powertrain.drive_torque,
                     "reverse_wait": sim.player.assist.reverse_wait})
    report = {"source": str(args.source), "tcs_off": args.tcs_off, "esc_off": args.esc_off,
              "initial_brake_speed": previous_speed, "stop_tick": stop_tick,
              "final_speed": rows[-1]["speed"], "rows": rows}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print({k: v for k, v in report.items() if k != "rows"})
finally:
    sim.close()
