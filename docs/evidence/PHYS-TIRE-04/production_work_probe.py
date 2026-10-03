"""只读记录最终再接触的所有轮胎子步，对照未观测轨迹与原残差功界。"""

import csv
import gzip
import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from physics import esc_probe
from physics.collision_support_probe import source_hashes

import vehicle_tires
from tire_properties import tire_grip


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    plan = [(mode, steps) for mode in esc_probe.MODES for steps in (2, 4, 8, 16)]
    pending = plan.copy()
    report = {"status": "running", "trials": [], "source_before": source_hashes(),
              "protocol": {"gate_n": .001, "rolling_bound": "h epsilon |patch|",
                  "static_bound": "h epsilon (|patch| + D/(Kh+b))", "dt_body": 1/120,
                  "observer": "returns original WheelStep objects; compares every existing CSV cell exactly",
                  "work": "all signed substeps and macro sums; no negative clamp"}}
    original_coupled, original_step = vehicle_tires.advance_coupled, esc_probe._step
    try:
        for mode, steps in plan:
            tick, substep = 0, 0
            count = negatives = violations = macros = 0
            minimum, maximum = math.inf, 0.0
            macro_bounds = []
            macro_road = []
            config = replace(esc_probe.trial_config("airborne-recontact", True, mode), tire_substeps=steps)
            with gzip.open(output / f"{mode}-{steps}-substeps.jsonl.gz", "wt", encoding="utf-8") as stream:
                def observed_coupled(*args):
                    nonlocal substep, count, negatives, violations, minimum, maximum
                    result = original_coupled(*args)
                    substep += 1
                    cfg, rear, h = args[-3:]
                    for index, step in enumerate(result):
                        wheel_cfg = cfg if index < 2 else rear
                        patch = (cfg.wheel_radius*step.omega-step.vx-step.deformation_rate_x,
                                 -step.vy-step.deformation_rate_y)
                        grip = tire_grip(args[3][index].load, args[3][index].mu, wheel_cfg)
                        bound = h*.001*math.hypot(*patch)
                        if step.mode in ("compliant-sticking", "compliant-sliding"):
                            bound += h*.001*grip/(cfg.tire_contact_stiffness*h+cfg.tire_contact_damping)
                        macro_bounds[index] += bound
                        macro_road[index] += step.road_dissipation
                        count += 1
                        negatives += step.road_dissipation < 0
                        violations += step.road_dissipation+bound < 0
                        minimum = min(minimum, step.road_dissipation)
                        maximum = max(maximum, step.residual)
                        stream.write(json.dumps({"tick": tick, "substep": substep, "wheel": index,
                            "dt_s": h, "step": asdict(step), "patch_mps": patch,
                            "gate_bound_j": bound}, allow_nan=False)+"\n")
                    return result

                def observed_step(world, vehicle, command):
                    nonlocal tick, substep, macro_bounds, macro_road, macros
                    tick += 1
                    substep = 0
                    macro_bounds, macro_road = [0.0]*4, [0.0]*4
                    original_step(world, vehicle, command)
                    macros += any(work+bound < 0 for work, bound in zip(macro_road, macro_bounds))

                vehicle_tires.advance_coupled = observed_coupled
                esc_probe._step = observed_step
                _summary, rows = esc_probe.run_trial("airborne-recontact", True, 6, mode, vehicle_config=config)
            path = HERE / "production-recontact-final" / f"{mode}-airborne-recontact-B-{steps}.csv.gz"
            with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
                expected = list(csv.DictReader(stream))
            observed_path = output / f"{mode}-{steps}-esc.csv.gz"
            esc_probe.write_csv(observed_path, rows)
            with gzip.open(observed_path, "rt", encoding="utf-8", newline="") as stream:
                actual = list(csv.DictReader(stream))
            equal = actual == expected
            result = {"mode": mode, "tire_substeps": steps, "wheel_substeps": count,
                      "same_unobserved_trace_every_cell": equal, "negative_work_count": negatives,
                      "minimum_signed_road_j": minimum, "substep_gate_bound_violations": violations,
                      "macro_gate_bound_violations": macros, "maximum_force_residual_n": maximum}
            report["trials"].append(result)
            pending.pop(0)
            save(output / "summary.json", report)
            if not equal or violations or macros or maximum >= .001:
                raise ValueError(f"原门槛或观察器轨迹核对失败：{result}")
            print(f"Completed {mode} {steps} all {count} wheel-substeps", flush=True)
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}", not_run=pending)
        raise
    finally:
        vehicle_tires.advance_coupled, esc_probe._step = original_coupled, original_step
        report["source_after"] = source_hashes()
        report["source_unchanged"] = report["source_before"] == report["source_after"]
        save(output / "summary.json", report)


if __name__ == "__main__":
    run(HERE / "production-recontact-work")
