"""无profile、独立子进程的原平面物理步A/B耗时证据。"""
import argparse
import gzip
import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "docs/evidence/PHYS-TIRE-04/mechanical-rigid/baseline-source"
CASES = ("acceleration", "constant-turn", "asphalt-brake")
ORDER = ("A", "B", "B", "A")


def hashes(source):
    return {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("src", "tools") for p in sorted((source / folder).rglob("*.py"))}


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def worker(source, case, output):
    sys.path[:0] = [str(source / "src"), str(source / "tools")]
    from panda3d.core import Vec3
    from physics import esc_probe, reference_ab

    from driving_modes import REFERENCE_CAR
    from vehicle_state import FIXED_DT, VehicleCommand

    before = hashes(source)
    world, car = reference_ab._create_vehicle(REFERENCE_CAR)
    rows, costs = [], []
    try:
        for _ in range(240):
            reference_ab._step(world, car, VehicleCommand())
        speed = esc_probe.initial_speed(case)
        car._chassis.setLinearVelocity(Vec3(0, speed, 0))
        car.tires.initialize_rolling(speed)
        initial = asdict(car.snapshot())
        for tick in range(1, 721):
            phase, command = esc_probe.command_at(case, (tick - 1) * FIXED_DT)
            start = time.perf_counter_ns()
            reference_ab._step(world, car, command)
            costs.append(time.perf_counter_ns() - start)
            state = asdict(car.snapshot())
            rows.append({"tick": tick, "phase": phase, "command": asdict(command),
                         "position": state["position"], "speed": state["speed"],
                         "heading": state["heading"], "rpm": state["rpm"],
                         "wheel_contacts": state["wheel_contacts"],
                         "wheel_dynamics": state["wheel_dynamics"],
                         "brake_states": state["brake_states"],
                         "stability_state": state["stability_state"],
                         "traction_state": state["traction_state"]})
        final = asdict(car.snapshot())
        modules = {name: str(Path(module.__file__).resolve())
                   for name, module in sorted(sys.modules.items())
                   if module is not None and module.__dict__.get("__file__")
                   and Path(module.__file__).resolve().is_relative_to(source)}
        after = hashes(source)
        trajectory = output.with_suffix(".jsonl.gz")
        with gzip.open(trajectory, "wt", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, allow_nan=False) + "\n")
        report = {"status": "completed", "case": case, "source_root": str(source),
                  "module_files": modules, "config": asdict(REFERENCE_CAR),
                  "input_config": asdict(car.input_config), "initial_snapshot": initial,
                  "final_snapshot": final, "source_before": before, "source_after": after,
                  "source_unchanged": before == after, "trajectory": trajectory.name,
                  "step_total_ns": sum(costs), "per_tick_ns": costs,
                  "tick_median_ns": statistics.median(costs), "tick_range_ns": [min(costs), max(costs)]}
        save(output, report)
    finally:
        car.close()


def flatten(value, prefix=""):
    result = {}
    if isinstance(value, dict):
        for key, child in value.items():
            result.update(flatten(child, prefix + "." + key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.update(flatten(child, prefix + "." + str(index)))
    else:
        result[prefix] = value
    return result


def differences(left, right):
    maxima, changed, compared = {}, 0, 0
    with gzip.open(left, "rt", encoding="utf-8") as a, gzip.open(right, "rt", encoding="utf-8") as b:
        for left_line, right_line in zip(a, b, strict=True):
            x, y = flatten(json.loads(left_line)), flatten(json.loads(right_line))
            if x.keys() != y.keys():
                raise ValueError("两轨迹字段集合不同")
            for key in x:
                compared += 1
                if x[key] != y[key]:
                    changed += 1
                if type(x[key]) in (float, int) and type(y[key]) in (float, int):
                    delta = abs(x[key] - y[key])
                    if not math.isfinite(delta):
                        raise ValueError("轨迹出现非有限数值")
                    maxima[key] = max(maxima.get(key, 0.0), delta)
    return {"compared_values": compared, "changed_values": changed,
            "maximum_absolute_delta_by_field": maxima,
            "comparison": "same case and tick; raw deltas only, no relaxed acceptance threshold"}


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    plan = [(case, index, label) for case in CASES for index, label in enumerate(ORDER)]
    source_before = {label: hashes(source) for label, source in (("A", BASELINE), ("B", ROOT))}
    report = {"status": "running", "protocol": {
        "headless": True, "profile": False, "world": "unchanged reference_ab horizontal infinite Bullet plane",
        "order_per_case": list(ORDER), "repetitions_per_variant": 2,
        "settle_neutral_ticks": 240, "trial_ticks": 720, "dt": 1 / 120,
        "initialization": "once-only initial_speed and pure rolling after settle; no runtime edits",
        "timing": "perf_counter_ns around _step only; commands, snapshots, observations, hashing and export excluded",
        "scope": "physics step wall time only; no FPS, visible window or performance gate claim",
        "baseline": "f2c1450 archived src/tools", "cases": list(CASES)},
        "source_before": source_before, "trials": [], "not_run": plan.copy()}
    save(output / "summary.json", report)
    try:
        for case, index, label in plan:
            destination = output / f"{case}-{index}-{label}.json"
            source = BASELINE if label == "A" else ROOT
            completed = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                "--worker", "--source", str(source), "--case", case, "--output", str(destination)],
                capture_output=True, text=True, encoding="utf-8", check=False)
            destination.with_suffix(".log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
            completed.check_returncode()
            trial = json.loads(destination.read_text(encoding="utf-8"))
            report["trials"].append({"case": case, "order_index": index, "label": label,
                "report": destination.name, "step_total_ns": trial["step_total_ns"],
                "source_unchanged": trial["source_unchanged"]})
            report["not_run"].pop(0)
            save(output / "summary.json", report)
        aggregates = []
        for case in CASES:
            group = {"case": case}
            for label in ("A", "B"):
                values = [t["step_total_ns"] / 1e6 for t in report["trials"] if t["case"] == case and t["label"] == label]
                group[label] = {"total_step_ms": values, "median_ms": statistics.median(values),
                                "range_ms": [min(values), max(values)]}
            group["median_change_percent"] = (group["B"]["median_ms"] / group["A"]["median_ms"] - 1) * 100
            group["aligned_physics_differences"] = [differences(output / f"{case}-0-A.jsonl.gz", output / f"{case}-{i}-B.jsonl.gz") for i in (1, 2)]
            aggregates.append(group)
        report["aggregates"] = aggregates
        report["status"] = "completed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = f"{type(error).__name__}: {error}"
        report["failed_trial"] = report["not_run"][0] if report["not_run"] else None
        raise
    finally:
        report["source_after"] = {label: hashes(source) for label, source in (("A", BASELINE), ("B", ROOT))}
        report["source_unchanged"] = report["source_before"] == report["source_after"]
        save(output / "summary.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.worker:
        worker(args.source.resolve(), args.case, args.output)
    else:
        run(args.output)
