"""Measure the handling targets against the same simulation used by the game."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=root / "logs/h1-review")
    args = parser.parse_args()
    sys.path.insert(0, str(root / "src"))
    from simulation import Control, Simulation
    from test_track import SPAWN, TEST_SPAWN
    from vehicle_config import CAR

    sim = Simulation(17, track="test")
    result = {"config": asdict(CAR), "physics_hz": 120}
    try:
        sim.reset_player(TEST_SPAWN)
        for _ in range(1800):
            sim.step(Control())
        result["idle_15s_position"] = sim.snapshot().player.position
        result["idle_wheel_contacts"] = [
            w.getRaycastInfo().isInContact() for w in sim._vehicle.getWheels()
        ]
        for ticks in range(1, 1441):
            sim.step(Control(throttle=1))
            if sim.snapshot().player.speed >= 100 / 3.6:
                break
        result["zero_to_100_seconds"] = ticks / 120
        start = sim.snapshot().player.position[1]
        for ticks in range(1, 601):
            sim.step(Control(brake=1))
            if abs(sim.snapshot().player.speed) < 0.15:
                break
        result["braking_100_to_stop_metres"] = sim.snapshot().player.position[1] - start
        result["braking_seconds"] = ticks / 120
        sim.reset_player(TEST_SPAWN)
        for _ in range(2640):
            sim.step(Control(throttle=1))
        result["speed_after_22_seconds_kmh"] = sim.snapshot().player.speed * 3.6
        sim.reset_player((SPAWN[0], 670, SPAWN[2]))
        for _ in range(1600):
            sim.step(Control(throttle=1))
        result["after_wall_impact"] = asdict(sim.snapshot().player)
    finally:
        sim.close()
    result["passed"] = (
        all(result["idle_wheel_contacts"])
        and 8 <= result["zero_to_100_seconds"] <= 11
        and 35 <= result["braking_100_to_stop_metres"] <= 50
        and 150 <= result["speed_after_22_seconds_kmh"] <= 161
        and result["after_wall_impact"]["position"][1] < 719
    )
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    (output / "handling.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
