"""Deterministic long-run and recovery checks for the finite highway prototype."""

import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from route_driver import RouteDriver

from coastal_map import ROAD_WIDTH, map_length, project
from highway_map import TRAFFIC_EXIT, lane_x
from simulation import Control, Simulation


def highway_run(seed, seconds=900):
    sim = Simulation(seed, track="highway")
    start = time.perf_counter()
    max_lane_error = max_roll = max_pitch = 0.0
    lowest_z = float("inf")
    highest_y = float("-inf")
    try:
        for tick in range(seconds * 120):
            sim.step(Control())
            if tick % 120:
                continue
            for body, (lane, _, _) in zip(sim._traffic_bodies, sim._traffic):
                position = body.getTransform().getPos()
                if body in sim._retired_traffic:
                    continue
                max_lane_error = max(max_lane_error, abs(position.x - lane_x(lane)))
                max_roll = max(max_roll, abs(body.getTransform().getHpr().z))
                max_pitch = max(max_pitch, abs(body.getTransform().getHpr().y))
                lowest_z = min(lowest_z, position.z)
                highest_y = max(highest_y, position.y)
        return {
            "seed": seed,
            "seconds": seconds,
            "traffic_cycles": sim.traffic_cycles,
            "collision_steps": sim.collision_count,
            "max_lane_error_m": round(max_lane_error, 3),
            "max_roll_deg": round(max_roll, 2),
            "max_pitch_deg": round(max_pitch, 2),
            "lowest_traffic_z_m": round(lowest_z, 3),
            "highest_traffic_y_m": round(highest_y, 1),
            "wall_seconds": round(time.perf_counter() - start, 2),
            "passed": (
                sim.traffic_cycles > 0
                and max_lane_error < 0.2
                and max_roll < 5
                and max_pitch < 5
                and lowest_z > 0.5
                and highest_y <= TRAFFIC_EXIT + 0.5
            ),
        }
    finally:
        sim.close()


def coastal_run(seed=23, laps=3):
    sim = Simulation(seed)
    driver = RouteDriver(90)
    progress = previous = 0.0
    max_error = max_roll = max_pitch = 0.0
    resets = airborne = 0
    try:
        for tick in range(240 * 120):
            sim.step(driver.control(sim.snapshot().player))
            state = sim.snapshot()
            car = state.player
            _, error, along = project(*car.position[:2])
            progress += (along - previous + map_length() / 2) % map_length() - map_length() / 2
            previous = along
            max_error = max(max_error, abs(error))
            max_roll = max(max_roll, abs(car.roll))
            max_pitch = max(max_pitch, abs(car.pitch))
            resets += bool(state.events)
            if tick > 120 and not any(
                wheel.getRaycastInfo().isInContact() for wheel in sim._vehicle.getWheels()
            ):
                airborne += 1
            if progress >= laps * map_length():
                break
        return {
            "seed": seed,
            "target_laps": laps,
            "ordered_laps": round(progress / map_length(), 3),
            "max_centerline_error_m": round(max_error, 3),
            "max_roll_deg": round(max_roll, 2),
            "max_pitch_deg": round(max_pitch, 2),
            "resets": resets,
            "airborne_ticks": airborne,
            "passed": (
                progress >= laps * map_length()
                and max_error + 0.84 < ROAD_WIDTH / 2
                and max_roll < 25
                and max_pitch < 25
                and resets == 0
                and airborne == 0
                and math.isfinite(car.speed)
            ),
        }
    finally:
        sim.close()


def reset_run(count=50):
    overlaps = 0
    for seed in range(count):
        sim = Simulation(seed, track="highway")
        try:
            target = sim._traffic_bodies[seed % len(sim._traffic_bodies)].getTransform().getPos()
            sim.reset_player((target.x, target.y, 0.55))
            sim.recover_player()
            player = sim._chassis.getTransform().getPos()
            overlaps += sum(
                (body.getTransform().getPos() - player).length() <= 4.2
                for body in sim._traffic_bodies
                if body not in sim._retired_traffic
            )
        finally:
            sim.close()
    return {"cases": count, "overlaps": overlaps, "passed": overlaps == 0}


def main():
    report = {
        "highway": [highway_run(seed) for seed in (0, 23)],
        "coastal": [coastal_run()],
        "recovery": reset_run(),
    }
    report["passed"] = (
        all(
            item["passed"] for group in report.values() if isinstance(group, list) for item in group
        )
        and report["recovery"]["passed"]
    )
    output = Path(__file__).resolve().parents[1] / "logs/phase5a"
    output.mkdir(parents=True, exist_ok=True)
    (output / "traffic-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
