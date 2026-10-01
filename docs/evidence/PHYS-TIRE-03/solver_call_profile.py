"""冻结四轮求解调用次数基线；仅计数，不从profile时长推断FPS。"""

import argparse
import cProfile
import hashlib
import json
import pstats
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from panda3d.core import Vec3
from physics.esc_probe import FIXED_DT, SETTLE_TICKS, command_at, initial_speed
from physics.reference_ab import _create_vehicle, _source_hashes, _step
from physics.tire_compliance_probe import trial_config

CASES = {"acceleration": "acceleration", "constant-turn": "constant-turn", "100kmh-brake": "asphalt-brake"}
FUNCTIONS = ("advance_coupled", "advance_wheel", "_solve_force", "residual",
             "contact_force", "body_state", "completed_steps")
PROFILE_TICKS = 120


def source_hashes():
    hashes = _source_hashes()
    for path in (Path(__file__), ROOT / "tools/physics/reference_ab.py",
                 ROOT / "tools/physics/esc_probe.py", ROOT / "tools/physics/tire_compliance_probe.py"):
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def profile_trial(case, output):
    scenario = CASES[case]
    config = trial_config(scenario, True, "simulation")
    world, vehicle = _create_vehicle(config)
    try:
        neutral = command_at("coast-disturbance", 0)[1]
        for _ in range(SETTLE_TICKS):
            _step(world, vehicle, neutral)
        speed = initial_speed(scenario)
        vehicle._chassis.setLinearVelocity(Vec3(0, speed, 0))
        vehicle.tires.initialize_rolling(speed)
        initial_state = vehicle.snapshot()
        command = command_at(scenario, 0)[1]
        profiler = cProfile.Profile()
        profiler.enable()
        for _ in range(PROFILE_TICKS):
            _step(world, vehicle, command)
        profiler.disable()
        filename = f"{case}.pstats"
        profiler.dump_stats(str(output / filename))
        statistics = pstats.Stats(profiler)
        denominator = PROFILE_TICKS*config.tire_substeps
        counts = {name: {"ncalls": 0, "primitive_calls": 0,
                         "average_calls_per_car_substep": 0.0, "definitions": []} for name in FUNCTIONS}
        for (path, line, name), (primitive, total, _self_time, _cumulative_time, _callers) in statistics.stats.items():
            if name not in counts or Path(path).parent.resolve() != (ROOT / "src").resolve():
                continue
            entry = counts[name]
            entry["ncalls"] += total
            entry["primitive_calls"] += primitive
            entry["definitions"].append({"file": Path(path).relative_to(ROOT).as_posix(),
                                         "line": line, "ncalls": total, "primitive_calls": primitive})
        for entry in counts.values():
            entry["average_calls_per_car_substep"] = entry["ncalls"]/denominator
        return {"case": case, "config": asdict(config), "command": asdict(command),
                "initial_conditions": {"initial_speed_mps": speed, "initial_state": asdict(initial_state),
                                       "speed_and_rolling_assignment": "once after 240 neutral settle ticks"},
                "final_state": asdict(vehicle.snapshot()), "profile_ticks": PROFILE_TICKS,
                "profile_elapsed_simulation_s": PROFILE_TICKS*FIXED_DT,
                "car_substeps": denominator, "raw_pstats": filename, "call_counts": counts}
    finally:
        vehicle.close()


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    pending = list(CASES)
    report = {"status": "running", "source_before": before, "trials": [], "protocol": {
        "world": "independent horizontal Bullet plane; simulation reference config; compliance/ABS/TCS/ESC true",
        "settle_ticks": SETTLE_TICKS, "body_step_s": FIXED_DT, "profile_ticks": PROFILE_TICKS,
        "substeps": 2, "average_denominator": "120 ticks * actual config tire_substeps per car; not per wheel",
        "inputs": "fixed direct command for 1 simulated second; constant-turn is fixed 3-degree input from settled straight pose, not steady-state circular motion",
        "measurement": "cProfile ncalls and primitive calls; original pstats retained; exclude initialization/settling/snapshot export",
        "scope": "call counts only; concurrent T2 and profiling overhead make timings unsuitable for FPS/performance comparisons; no optimization"}}
    try:
        for case in CASES:
            report["trials"].append(profile_trial(case, output))
            pending.remove(case)
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", failed_trial=pending[0], not_run=pending[1:],
                      error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["source_after"] = source_hashes()
        report["source_unchanged"] = before == report["source_after"]
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
