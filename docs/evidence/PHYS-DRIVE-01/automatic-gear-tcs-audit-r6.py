"""自动方向不请求换挡时，实际已挂挡位与TCS反馈的原生对照。"""

from dataclasses import asdict, replace
import gzip
import hashlib
import json
from pathlib import Path
import sys

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from driving_modes import DrivingMode
from physics.reference_ab import _create_vehicle, _step
from vehicle_state import VehicleCommand


def main():
    frozen = json.loads((EVIDENCE / "matrix-reuse-r6-source-before.json").read_text(encoding="utf-8"))
    results = []
    for mode in ("game", "simulation"):
        config = replace(DrivingMode(mode).vehicle_config, road_friction=.12)
        for gear in (-1, 1):
            for direction in (0, gear):
                world, car = _create_vehicle(config)
                records = []
                try:
                    for _ in range(240):
                        _step(world, car, VehicleCommand(brake=1., gear=gear))
                    assert car.powertrain.gear == gear
                    for tick in range(120):
                        request = VehicleCommand(throttle=1., direction=direction)
                        _step(world, car, request)
                        records.append({"tick": tick, "request": asdict(request), "car": asdict(car.snapshot())})
                    name = f"automatic-tcs-r6-{mode}-gear{gear}-direction{direction}.jsonl.gz"
                    with gzip.open(EVIDENCE / name, "wt", encoding="utf-8") as stream:
                        for record in records:
                            stream.write(json.dumps(record, allow_nan=False) + "\n")
                    row = {"mode": mode, "gear": gear, "direction": direction,
                           "manual_gear_request_during_drive": False, "ticks": len(records),
                           "active_ticks": sum(record["car"]["traction_state"]["active"] for record in records),
                           "max_rear_abs_kappa": max(abs(wheel["kappa"]) for record in records
                                                     for wheel in record["car"]["wheel_dynamics"][2:] if wheel["kappa"] is not None),
                           "max_rear_drive_torque": max(abs(wheel["drive_torque"]) for record in records
                                                         for wheel in record["car"]["wheel_dynamics"][2:]),
                           "end_speed": records[-1]["car"]["speed"], "trace": name}
                    results.append(row)
                    print(json.dumps(row), flush=True)
                finally:
                    car.close()
    source = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in frozen}
    assert source == frozen
    (EVIDENCE / "automatic-gear-tcs-audit-r6.json").write_text(json.dumps(
        {"scope": "native fixed-input boundary audit; not complete T1/T2", "source_before": frozen,
         "source_after": source, "source_stable": True, "results": results}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
