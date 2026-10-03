"""逐轮胎子步核对有符号路面功与原接触残差功界，不改变求解或受力。"""

import argparse
import gzip
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASELINE = HERE / "mechanical-rigid/baseline-source"
CASES = ("acceleration", "constant-turn", "asphalt-brake")


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def worker(output, case, label):
    source = BASELINE if label == "A" else ROOT
    sys.path[:0] = [str(source / "src"), str(source / "tools")]
    from panda3d.core import Vec3
    from physics import esc_probe, reference_ab

    import vehicle_tires
    from driving_modes import REFERENCE_CAR
    from tire_properties import tire_grip
    from vehicle_state import FIXED_DT, VehicleCommand

    def hashes():
        return {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for folder in ("src", "tools") for p in sorted((source / folder).rglob("*.py"))}

    original = vehicle_tires.advance_coupled
    tick, substep = 0, 0
    substeps, sums, states = [], [], []

    def observed(*args):
        nonlocal substep
        result = original(*args)
        if tick == 0:
            return result
        substep += 1
        frames, config, h = args[3], args[-3], args[-1]
        for i, step in enumerate(result):
            denominator = max(abs(step.vx), config.slip_speed)
            patch = (step.patch_kappa*denominator, -math.tan(step.patch_alpha)*denominator)
            speed = math.hypot(*patch)
            grip = tire_grip(frames[i].load, frames[i].mu, config)
            # residual=max(force_error,brake_error)仍是接触力误差的保守上界。
            error = step.residual
            bound = h*error*speed
            if step.mode in ("compliant-sticking", "compliant-sliding"):
                bound += h*error*grip/(config.tire_contact_stiffness*h+config.tire_contact_damping)
            substeps.append({"tick": tick, "substep": substep, "wheel": i, "dt_s": h,
                             "step": asdict(step), "patch_speed_mps": speed, "grip_n": grip,
                             "residual_work_bound_j": bound,
                             "signed_road_above_lower_bound_j": step.road_dissipation+bound})
            sums[i] += bound
        return result

    before = hashes()
    vehicle_tires.advance_coupled = observed
    world, car = reference_ab._create_vehicle(REFERENCE_CAR)
    try:
        for _ in range(240):
            reference_ab._step(world, car, VehicleCommand())
        speed = esc_probe.initial_speed(case)
        car._chassis.setLinearVelocity(Vec3(0, speed, 0))
        car.tires.initialize_rolling(speed)
        initial = asdict(car.snapshot())
        with gzip.open(HERE / "solver-timing" / f"{case}-{0 if label == 'A' else 1}-{label}.jsonl.gz", "rt", encoding="utf-8") as stream:
            expected = [json.loads(line) for line in stream]
        equal = True
        for tick in range(1, 721):
            sums, substep = [0.0]*4, 0
            _phase, command = esc_probe.command_at(case, (tick-1)*FIXED_DT)
            reference_ab._step(world, car, command)
            state = json.loads(json.dumps(asdict(car.snapshot()), allow_nan=False))
            old = expected[tick-1]
            # 观察器不得改变任何已计时轨迹字段。
            equal &= all(state[field] == old[field] for field in (
                "position", "speed", "heading", "rpm", "wheel_contacts", "wheel_dynamics",
                "brake_states", "stability_state", "traction_state"))
            states.append({"tick": tick, "bounds_j": sums.copy(),
                           "road_j": [wheel.road_dissipation for wheel in car.tires.states]})
        for name, rows in (("substeps", substeps), ("ticks", states)):
            with gzip.open(output / f"{name}.jsonl.gz", "wt", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row, allow_nan=False)+"\n")
        negative = [row for row in substeps if row["step"]["road_dissipation"] < 0]
        violations = [row for row in substeps if row["signed_road_above_lower_bound_j"] < 0]
        macro_violations = [row for row in states if any(road+bound < 0 for road, bound in zip(row["road_j"], row["bounds_j"]))]
        save(output / "summary.json", {"status": "completed", "case": case, "label": label,
            "config": asdict(REFERENCE_CAR), "initial": initial, "source_before": before, "source_after": hashes(),
            "source_unchanged": before == hashes(), "same_timed_trace": bool(equal),
            "modules": {name: sys.modules[name].__file__ for name in ("vehicle", "vehicle_tires", "tire_coupling", "wheel_dynamics")},
            "substep_wheel_records": len(substeps), "negative_road_records": len(negative),
            "minimum_signed_road_j": min(row["step"]["road_dissipation"] for row in substeps),
            "negative_bound_violations": len(violations), "macro_bound_violations": len(macro_violations),
            "maximum_force_residual_n": max(row["step"]["residual"] for row in substeps),
            "worst_negative_record": min(negative, key=lambda row: row["step"]["road_dissipation"]) if negative else None})
    finally:
        car.close()


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    plan = [(case, label) for case in CASES for label in ("A", "B")]
    report = {"status": "running", "trials": [], "not_run": plan.copy(), "protocol": {
        "physics": "same unmodified solver-timing source/config/settle/input, observer returns original WheelStep objects",
        "rolling_bound": "h*epsilon*|patch| since exact target dot patch is nonnegative",
        "static_bound": "h*epsilon*(|patch|+D/(Kh+b)); target radial projection A implies target dot (A-target)>=0, patch=(A-F)/(Kh+b)",
        "epsilon": "actual saved max(force_error,brake_error), upper bound on contact force residual; original .001N gate unchanged",
        "macro": "sum each substep's bound and signed road work; no last-substep proxy and no negative clamp"}}
    try:
        for case, label in plan:
            child = output / f"{case}-{label}"
            child.mkdir()
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", "--output", str(child.resolve()),
                                     "--case", case, "--label", label], capture_output=True, text=True, check=False)
            (child / "execution.log").write_text(result.stdout+result.stderr, encoding="utf-8")
            result.check_returncode()
            report["trials"].append(json.loads((child / "summary.json").read_text(encoding="utf-8")))
            report["not_run"].pop(0)
            save(output / "summary.json", report)
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        save(output / "summary.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--case", choices=CASES)
    parser.add_argument("--label", choices=("A", "B"))
    args = parser.parse_args()
    if args.worker:
        worker(args.output, args.case, args.label)
    else:
        run(args.output)
