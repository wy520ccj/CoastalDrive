"""交替原生短测：固定物理输入，只比较当前进程内的矩阵复用。"""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import runpy
import statistics
import sys
import time

EVIDENCE = Path(__file__).resolve().parent
ROOT = EVIDENCE.parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from driving_modes import DrivingMode
from physics.reference_ab import _create_vehicle, _step
import tire_drivetrain
from vehicle_state import VehicleCommand


def main():
    original = tire_drivetrain.clutch_brake_plans
    experiment = EVIDENCE / "cofactor-reuse-audit-r5.py"
    functions = runpy.run_path(str(experiment))

    def reuse(response, capacity, brake_capacity, efficiency):
        return functions["reused_plans"](response, capacity, brake_capacity, efficiency)[0]

    source = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for folder in ("src", "tests", "tools") for path in sorted((ROOT / folder).rglob("*.py"))}
    trials = []
    for mode in ("game", "simulation"):
        for repeat in range(2):
            variants = (("old", original), ("reuse", reuse))
            if repeat % 2:
                variants = tuple(reversed(variants))
            for label, implementation in variants:
                tire_drivetrain.clutch_brake_plans = implementation
                world, vehicle = _create_vehicle(DrivingMode(mode).vehicle_config)
                try:
                    for _ in range(240):
                        _step(world, vehicle, VehicleCommand(brake=1.))
                    command = VehicleCommand(throttle=1., direction=1)
                    wall_start, cpu_start = time.perf_counter(), time.process_time()
                    for _ in range(120):
                        _step(world, vehicle, command)
                    cpu, wall = time.process_time() - cpu_start, time.perf_counter() - wall_start
                    state = json.dumps(asdict(vehicle.snapshot()), ensure_ascii=False, allow_nan=False).encode("utf-8")
                    row = {"mode": mode, "repeat": repeat, "variant": label,
                           "physics_ticks": 120, "cpu_seconds": cpu, "wall_seconds": wall,
                           "end_state_sha256": hashlib.sha256(state).hexdigest()}
                    trials.append(row)
                    print(json.dumps(row), flush=True)
                finally:
                    vehicle.close()
    results = []
    for mode in ("game", "simulation"):
        rows = [row for row in trials if row["mode"] == mode]
        assert len({row["end_state_sha256"] for row in rows}) == 1
        old = statistics.mean(row["cpu_seconds"] for row in rows if row["variant"] == "old")
        new = statistics.mean(row["cpu_seconds"] for row in rows if row["variant"] == "reuse")
        results.append({"mode": mode, "old_mean_cpu_seconds": old, "reuse_mean_cpu_seconds": new,
                        "cpu_time_reduction_fraction": 1 - new / old, "end_states_identical": True})
    source_after = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source}
    assert source == source_after
    target = EVIDENCE / "cofactor-native-timing-r5.json"
    target.write_text(json.dumps({"status": "completed", "scope": "one-car plane, no rendering; 240 settle excluded + 120 launch timed; AB/BA pairs; concurrent full T1; not a visible FPS gate",
                                 "algorithm_script_sha256": hashlib.sha256(experiment.read_bytes()).hexdigest(),
                                 "runner_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                 "source_before": source, "source_after": source_after,
                                 "source_stable": True, "trials": trials, "results": results},
                                ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results), flush=True)


if __name__ == "__main__":
    main()
