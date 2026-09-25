"""Two ordered laps, measured from physics rather than a timer or odometer alone."""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from route_driver import RouteDriver

from coastal_map import ROAD_WIDTH, map_length, project
from simulation import Simulation


def check_route(speed_kmh=90, laps=2):
    simulation = Simulation(23)
    driver = RouteDriver(speed_kmh)
    progress = previous = 0.0
    max_error = max_roll = max_pitch = max_speed = 0.0
    resets = airborne = 0
    try:
        for tick in range(180 * 120):
            simulation.step(driver.control(simulation.snapshot().player))
            state = simulation.snapshot()
            car = state.player
            _, error, along = project(*car.position[:2])
            progress += (along - previous + map_length() / 2) % map_length() - map_length() / 2
            previous = along
            max_error = max(max_error, error)
            max_roll = max(max_roll, abs(car.roll))
            max_pitch = max(max_pitch, abs(car.pitch))
            max_speed = max(max_speed, car.speed * 3.6)
            resets += bool(state.events)
            if tick > 120 and not any(
                w.getRaycastInfo().isInContact() for w in simulation._vehicle.getWheels()
            ):
                airborne += 1
            if progress >= laps * map_length():
                break
        report = {
            "target_speed_kmh": speed_kmh,
            "seconds": round((tick + 1) / 120, 2),
            "ordered_laps": round(progress / map_length(), 3),
            "max_centerline_error_m": round(max_error, 3),
            "max_roll_deg": round(max_roll, 2),
            "max_pitch_deg": round(max_pitch, 2),
            "max_speed_kmh": round(max_speed, 1),
            "resets": resets,
            "airborne_ticks": airborne,
        }
        report["passed"] = (
            progress >= laps * map_length()
            and max_error + 0.84 < ROAD_WIDTH / 2
            and max_roll < 25
            and max_pitch < 25
            and resets == 0
            and airborne == 0
            and math.isfinite(car.speed)
        )
        return report
    finally:
        simulation.close()


def main():
    reports = [check_route(speed) for speed in (60, 90)]
    output = Path(__file__).resolve().parents[1] / "logs/h2-review"
    output.mkdir(parents=True, exist_ok=True)
    (output / "route-check.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(json.dumps(reports, indent=2))
    return 0 if all(report["passed"] for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
