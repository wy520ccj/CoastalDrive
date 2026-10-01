"""独立核对冻结CSV的预算、求解误差与A/B输入隔离。"""

import csv
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    matrix = json.loads((ROOT / "vehicle-ab-final/summary.json").read_text(encoding="utf-8"))
    budget_excess = residual = property_error = 0.0
    samples = 0
    input_mismatches = config_mismatches = 0
    for pair in matrix["cases"]:
        configs = [dict(pair[label]["config"]) for label in ("A", "B")]
        for config in configs:
            for field in ("tire_peak_load_exponent", "longitudinal_load_exponent", "lateral_load_exponent"):
                config.pop(field)
        config_mismatches += configs[0] != configs[1]
        traces = [read(ROOT / "vehicle-ab-final" / pair[label]["csv_gz"]) for label in ("A", "B")]
        for old, new in zip(*traces, strict=True):
            input_mismatches += any(old[key] != new[key] for key in old if key.startswith("command."))
        for label, rows in zip(("A", "B"), traces):
            config = pair[label]["config"]
            nominal = config["mass"] * 9.81 / 4
            for row in rows[1:]:
                for index in range(4):
                    prefix = f"state.wheel_dynamics.{index}."
                    load = float(row[prefix + "normal_load"])
                    grip = float(row[prefix + "force_grip"])
                    force = math.hypot(float(row[prefix + "fx"]), float(row[prefix + "fy"]))
                    error = float(row[prefix + "force_residual"])
                    budget_excess = max(budget_excess, force - grip)
                    residual = max(residual, error)
                    # 支撑轮荷来自施力阶段；μ由同阶段接触表surface确定。
                    if load:
                        # 均匀路面可直接核对解析D；split左右表面仍由逐步接点决定。
                        if pair["case"] != "split-mu-brake":
                            expected = config["road_friction"] * load * (load / nominal) ** (config["tire_peak_load_exponent"] - 1)
                            property_error = max(property_error, abs(grip - expected))
                        cx = config["longitudinal_stiffness"] * (load / nominal) ** config["longitudinal_load_exponent"]
                        cy0 = config["lateral_stiffness"] if index < 2 else config["rear_lateral_stiffness"]
                        cy = cy0 * (load / nominal) ** config["lateral_load_exponent"]
                        property_error = max(property_error, abs(cx - float(row[prefix + "force_longitudinal_stiffness"])),
                                             abs(cy - float(row[prefix + "force_lateral_stiffness"])))
                    samples += 1
    steps = json.loads((ROOT / "substeps/summary.json").read_text(encoding="utf-8"))
    max_steps_residual = max(trial[str(step)]["maximum_force_residual_n"] for trial in steps["trials"] for step in (2, 8))
    report = {"wheel_samples": samples, "maximum_force_over_capacity_n": budget_excess,
              "maximum_force_residual_n": residual, "maximum_property_error": property_error,
              "input_mismatches": input_mismatches, "config_mismatches_except_three_exponents": config_mismatches,
              "source_unchanged_matrix": matrix["source_sha256_before"] == matrix["source_sha256_after"],
              "substeps_trials": 2 * len(steps["trials"]), "maximum_substeps_force_residual_n": max_steps_residual,
              "source_unchanged_substeps": steps["source_unchanged"],
              "maximum_2_8_path_difference_m": max(abs(t["eight_minus_two"]["path_distance_m"]) for t in steps["trials"]),
              "maximum_2_8_heading_difference_deg": max(abs(t["eight_minus_two"]["heading_change_deg"]) for t in steps["trials"]),
              "budget_tolerance_n": .001, "tolerance_basis": "existing implicit force solve residual target .001N"}
    report["passed"] = (budget_excess <= .001 and residual < .001 and max_steps_residual < .001
                        and property_error <= 1e-9 and input_mismatches == config_mismatches == 0
                        and report["source_unchanged_matrix"] and steps["source_unchanged"])
    (ROOT / "trial-checks.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
