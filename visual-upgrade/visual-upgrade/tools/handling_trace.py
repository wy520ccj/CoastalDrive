"""Record repeatable driving response curves, without rendering or synthetic keyboard events."""

import csv
import json
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from simulation import FIXED_DT, Control, Simulation
    from vehicle_response import VehicleResponse

    output = root / "logs/handling-v2"
    output.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name in ("tap", "accelerate_coast_brake"):
        sim = Simulation(17, track="test")
        rows = []
        try:
            for _ in range(240):
                sim.step(Control())
            count = 360 if name == "tap" else 2640
            peak_speed = 0
            for tick in range(count):
                time = tick * FIXED_DT
                if name == "tap":
                    control = Control(throttle=1) if tick < 18 else Control()
                elif time < 12:
                    control = Control(throttle=1)
                elif time < 17:
                    control = Control()
                else:
                    control = Control(brake=1)
                sim.step(control)
                car = sim.snapshot().player
                peak_speed = max(peak_speed, abs(car.speed) * 3.6)
                if tick % 6 == 0:
                    rows.append(
                        (
                            (tick + 1) * FIXED_DT,
                            car.speed * 3.6,
                            car.acceleration,
                            control.throttle,
                            car.throttle,
                            car.brake,
                            car.rpm,
                            car.gear,
                        )
                    )
            summary[name] = {"peak_speed_kmh": peak_speed, "final_speed_kmh": car.speed * 3.6}
        finally:
            sim.close()
        with (output / f"{name}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(
                (
                    "time",
                    "speed_kmh",
                    "acceleration",
                    "requested_throttle",
                    "applied_throttle",
                    "brake",
                    "rpm",
                    "gear",
                )
            )
            writer.writerows(rows)

    rows = []
    for speed in (0, 100 / 3.6):
        response = VehicleResponse()
        for tick in range(360):
            control = Control(steering=1 if tick < 12 or 120 <= tick < 240 else 0)
            response.pedals_and_steering(control, speed, FIXED_DT)
            rows.append(((tick + 1) * FIXED_DT, speed * 3.6, control.steering, response.steering))
    with (output / "steering.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("time", "speed_kmh", "request", "road_wheel_degrees"))
        writer.writerows(rows)
    (output / "trace-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
