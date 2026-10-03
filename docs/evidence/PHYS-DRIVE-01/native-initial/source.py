"""有限传动真实Bullet连续轨迹；明确输入、源码与失败，不替代人工驾驶。"""

import argparse
import gzip
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from physics.reference_ab import _create_vehicle, _step

from driving_modes import DrivingMode
from vehicle_state import VehicleCommand


def command(case, seconds):
    if case == "launch":
        return VehicleCommand(throttle=1., direction=1)
    if case == "reverse":
        return VehicleCommand(throttle=1., direction=-1)
    if case == "neutral":
        return VehicleCommand(throttle=1. if seconds < 1.5 else 0., gear=0)
    if case == "release-brake":
        if seconds < 2.:
            return VehicleCommand(throttle=1., direction=1)
        return VehicleCommand(brake=.8 if seconds >= 3. else 0., direction=1)
    if case == "manual-shift":
        gear = 1 if seconds < 1. else 2 if seconds < 2. else 3
        return VehicleCommand(throttle=.5, direction=1, gear=gear, clutch=1.)
    if case == "interrupted-shift":
        gear = 1 if seconds < 1. else 2 if seconds < 1.04 else -1 if seconds < 1.08 else 0
        return VehicleCommand(throttle=.3, gear=gear, clutch=1.)
    raise ValueError(case)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=6.)
    parser.add_argument("--cases", nargs="+", default=["launch", "reverse", "neutral", "release-brake", "manual-shift", "interrupted-shift"])
    parser.add_argument("--modes", nargs="+", default=["game", "simulation"])
    parser.add_argument("--rigid", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                      for folder in ("src", "tests", "tools") for p in sorted((ROOT / folder).rglob("*.py"))}
    before = hashes()
    results = []
    for mode in args.modes:
        selected = DrivingMode(mode)
        config = replace(selected.vehicle_config, finite_drivetrain=True, tire_compliance=not args.rigid)
        for case in args.cases:
            world, vehicle = _create_vehicle(config, selected.input_config)
            records = []
            try:
                for _ in range(240):
                    _step(world, vehicle, VehicleCommand(brake=1.))
                if case in ("manual-shift", "interrupted-shift"):
                    vehicle.reset(vehicle.spawn, speed=15.)
                for tick in range(round(args.seconds * 120)):
                    request = command(case, tick / 120)
                    _step(world, vehicle, request)
                    state = vehicle.snapshot()
                    records.append({"tick": tick, "input": asdict(request), "car": asdict(state)})
                with gzip.open(args.output / f"{mode}-{case}.jsonl.gz", "wt", encoding="utf-8") as stream:
                    for record in records:
                        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
                summary = {"mode": mode, "case": case, "config": asdict(config), "ticks": len(records),
                    "end_speed": state.speed, "rpm_range": [min(r["car"]["rpm"] for r in records), max(r["car"]["rpm"] for r in records)],
                    "end_rpm": state.rpm, "end_gear": state.gear,
                    "gear_changes": [{"tick": r["tick"], "gear": r["car"]["gear"], "clutch_capacity": r["car"]["powertrain_state"]["clutch_capacity"]}
                                     for i, r in enumerate(records) if i and r["car"]["gear"] != records[i - 1]["car"]["gear"]],
                    "max_force_residual": max(w["force_residual"] for r in records for w in r["car"]["wheel_dynamics"]),
                    "clutch_heat": sum(r["car"]["powertrain_state"]["clutch_heat"] for r in records),
                    "gear_heat": sum(r["car"]["powertrain_state"]["gear_heat"] for r in records)}
                assert summary["max_force_residual"] < .001
                assert all(change["clutch_capacity"] == 0. for change in summary["gear_changes"])
                results.append(summary)
                print(f"PASS {mode}/{case} speed={state.speed:.4f} rpm={state.rpm:.1f} gear={state.gear}", flush=True)
            except (ArithmeticError, AssertionError) as error:
                with gzip.open(args.output / f"{mode}-{case}-partial.jsonl.gz", "wt", encoding="utf-8") as stream:
                    for record in records:
                        stream.write(json.dumps(record, allow_nan=False) + "\n")
                (args.output / "failure.json").write_text(json.dumps({"error": repr(error), "mode": mode, "case": case,
                    "completed_ticks": len(records), "config": asdict(config), "source_sha256": before}, indent=2), encoding="utf-8")
                raise
            finally:
                vehicle.close()
    after = hashes()
    assert before == after
    (args.output / "summary.json").write_text(json.dumps({"source_before": before, "source_after": after,
        "source_stable": before == after, "results": results, "claim": "native 120Hz continuous drivetrain cases; not a visible/human gate"}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
