"""精确复现单NPC换道测试，保存实际控制与轮胎阶段读数。"""

import argparse
import csv
import json
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2] / "src")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source.resolve()))

from simulation import Control, Simulation

sim = Simulation(track="endless", traffic_count=1)
try:
    driver = sim.drivers[0]
    driver.lane = driver.target_lane = 1
    sim.npcs[0].reset((0, 150, .55))
    rows = []
    for tick in range(2800):
        if tick == 1000:
            driver.target_lane, driver.phase, driver.elapsed = 2, "signal", 0
            driver.signal = 1
        sim.step(Control())
        car = sim.npcs[0].snapshot()
        control = sim._traffic_controls[0]
        if tick % 6 and tick != 2799:
            continue
        row = {
            "tick": tick + 1, "phase": driver.phase, "recovery": driver.recovery.phase,
            "lane": driver.lane, "target_lane": driver.target_lane,
            "target_lateral": driver.target_lateral, "x": car.position[0],
            "y": car.position[1], "z": car.position[2], "yaw": car.heading,
            "roll": car.roll, "pitch": car.pitch, "speed": car.speed,
            "velocity": json.dumps(tuple(sim.npcs[0]._chassis.getLinearVelocity())),
            "control_steering": control.steering, "control_throttle": control.throttle,
            "control_brake": control.brake, "actual_steering": car.steering,
            "angular_velocity": json.dumps(tuple(sim.npcs[0]._chassis.getAngularVelocity())),
            "lane_changes": driver.lane_changes,
        }
        # 旧基线没有独立轮胎状态；通过明确版本接口选择，不伪造其读数。
        if "wheel_dynamics" in car.__dataclass_fields__:
            row["wheel_dynamics"] = json.dumps([
                [w.normal_load, w.kappa, w.alpha, w.fx, w.fy]
                for w in car.wheel_dynamics], allow_nan=False)
        rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"source": str(args.source), "final": rows[-1],
                      "first_recovery": next((r for r in rows if r["recovery"]), None)},
                     ensure_ascii=False))
finally:
    sim.close()
