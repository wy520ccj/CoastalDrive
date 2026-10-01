from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import sys
from dataclasses import fields, is_dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
OUT = EVIDENCE / "candidate-scan"
BASELINE = EVIDENCE / "baseline-scan" / "tire-force-grid.csv.gz"
sys.path.insert(0, str(ROOT / "src"))

from driving_modes import REFERENCE_CAR
from tire_forces import tire_force
from tire_properties import tire_grip, tire_stiffness

FN0 = REFERENCE_CAR.mass * 9.81 / 4
LOADS = (0.0, 0.5 * FN0, FN0, 1.5 * FN0, 2.0 * FN0, REFERENCE_CAR.suspension_force_limit)
KAPPAS = (-1.0, -0.3, -0.15, -0.12, -0.06, 0.0, 0.06, 0.12, 0.15, 0.3, 1.0)
ALPHAS = (-0.3, -0.12, 0.0, 0.12, 0.3)
ROADS = (("asphalt", REFERENCE_CAR.road_friction), ("grass", REFERENCE_CAR.grass_friction))
AXLES = (("front", REFERENCE_CAR), ("rear", replace(REFERENCE_CAR, lateral_stiffness=REFERENCE_CAR.rear_lateral_stiffness)))
SOURCES = tuple(sorted((ROOT / "src").rglob("*.py")))
PEAK_N = 40001
KAPPA_MAX = 3.0
ALPHA_MAX = 1.55
EPS = 1e-5


def source_hashes():
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in SOURCES}


def json_config(value):
    if is_dataclass(value):
        return {field.name: json_config(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (tuple, list)):
        return [json_config(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_config(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported config value: {type(value).__name__}")


def peak(config, mu, load, axis):
    if load == 0:
        return {"peak_force_N": 0.0, "peak_slip": 0.0}
    upper = KAPPA_MAX if axis == "kappa" else ALPHA_MAX
    max_force, max_slip = -1.0, 0.0
    for index in range(PEAK_N):
        slip = upper * index / (PEAK_N - 1)
        fx, fy = tire_force(slip if axis == "kappa" else 0.0,
                            slip if axis == "alpha" else 0.0, load, mu, config)
        force = abs(fx if axis == "kappa" else fy)
        if force > max_force:
            max_force, max_slip = force, slip
    return {"peak_force_N": max_force, "peak_slip": max_slip}


def small_slip_slopes(config, mu, load):
    if load == 0:
        return {"Cx_N_per_slip": 0.0, "Cy_N_per_rad": 0.0}
    fx_plus = tire_force(EPS, 0.0, load, mu, config)[0]
    fx_minus = tire_force(-EPS, 0.0, load, mu, config)[0]
    fy_plus = tire_force(0.0, EPS, load, mu, config)[1]
    fy_minus = tire_force(0.0, -EPS, load, mu, config)[1]
    return {"Cx_N_per_slip": (fx_plus - fx_minus) / (2 * EPS),
            "Cy_N_per_rad": abs((fy_plus - fy_minus) / (2 * EPS))}


def write_grid():
    path = OUT / "candidate-force-grid.csv.gz"
    columns = ("road_surface", "mu", "axle", "normal_load_N", "load_multiple_Fn0", "normal_load_multiple_suspension_limit",
               "grip_budget_D_N", "Cx_N_per_slip", "Cy_N_per_rad", "kappa", "alpha_rad", "fx_N", "fy_N",
               "force_magnitude_N", "force_budget_ratio")
    count = 0
    with gzip.open(path, "wt", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for road, mu in ROADS:
            for axle, config in AXLES:
                for load in LOADS:
                    grip = tire_grip(load, mu, config)
                    cx, cy = tire_stiffness(load, config)
                    for kappa in KAPPAS:
                        for alpha in ALPHAS:
                            fx, fy = tire_force(kappa, alpha, load, mu, config)
                            magnitude = math.hypot(fx, fy)
                            ratio = magnitude / grip if grip else 0.0
                            writer.writerow((road, mu, axle, load, load / FN0, load / config.suspension_force_limit,
                                             grip, cx, cy, kappa, alpha, fx, fy, magnitude, ratio))
                            count += 1
    expected = len(ROADS) * len(AXLES) * len(LOADS) * len(KAPPAS) * len(ALPHAS)
    if count != expected:
        raise RuntimeError(f"candidate grid row count {count}, expected {expected}")
    return {"file": path.name, "rows": count, "expected_rows": expected, "columns": columns}


def compare_baselines():
    if not BASELINE.is_file():
        raise FileNotFoundError(f"baseline CSV is missing: {BASELINE}")
    linear_configs = {
        axle: replace(config, tire_peak_load_exponent=1.0,
                      longitudinal_load_exponent=1.0, lateral_load_exponent=1.0)
        for axle, config in AXLES
    }
    nominal_mismatches = []
    linear_mismatches = []
    row_count = 0
    with gzip.open(BASELINE, "rt", newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            road, axle = row["road_surface"], row["axle"]
            mu, load = float(row["mu"]), float(row["normal_load_N"])
            kappa, alpha = float(row["kappa"]), float(row["alpha_rad"])
            expected_fx, expected_fy = float(row["fx_N"]), float(row["fy_N"])
            config = dict(AXLES)[axle]
            if load == FN0:
                fx, fy = tire_force(kappa, alpha, load, mu, config)
                if fx != expected_fx or fy != expected_fy:
                    nominal_mismatches.append({"road": road, "axle": axle, "kappa": kappa, "alpha": alpha,
                                               "expected": [expected_fx, expected_fy], "actual": [fx, fy]})
            fx, fy = tire_force(kappa, alpha, load, mu, linear_configs[axle])
            if fx != expected_fx or fy != expected_fy:
                linear_mismatches.append({"road": road, "axle": axle, "load_N": load, "kappa": kappa, "alpha": alpha,
                                          "expected": [expected_fx, expected_fy], "actual": [fx, fy]})
            row_count += 1
    expected_rows = len(ROADS) * len(AXLES) * 5 * len(KAPPAS) * len(ALPHAS)
    if row_count != expected_rows:
        raise RuntimeError(f"baseline row count {row_count}, expected {expected_rows}")
    return {"baseline_rows_read": row_count, "baseline_expected_rows": expected_rows,
            "nominal_point_rows_compared": len(nominal_mismatches) + 4 * len(KAPPAS) * len(ALPHAS) - len(nominal_mismatches),
            "nominal_load_force_mismatch_count": len(nominal_mismatches),
            "nominal_load_forces_strictly_equal": not nominal_mismatches,
            "linear_exponents_force_mismatch_count": len(linear_mismatches),
            "linear_exponents_all_grid_points_strictly_equal": not linear_mismatches,
            "first_nominal_mismatches": nominal_mismatches[:5], "first_linear_mismatches": linear_mismatches[:5]}


def load_transfer_analysis():
    output = {}
    for road, mu in ROADS:
        for axle, config in AXLES:
            group = f"{road}/{axle}"
            distributions = []
            total = 2 * FN0
            for left, right in ((.5, .5), (.3, .7), (.1, .9)):
                loads = (total * left, total * right)
                grip_sum = sum(tire_grip(load, mu, config) for load in loads)
                reference_grip = sum(tire_grip(total * share, mu, config) for share in (.5, .5))
                cx_sum = sum(tire_stiffness(load, config)[0] for load in loads)
                cy_sum = sum(tire_stiffness(load, config)[1] for load in loads)
                reference_cx = sum(tire_stiffness(total * share, config)[0] for share in (.5, .5))
                reference_cy = sum(tire_stiffness(total * share, config)[1] for share in (.5, .5))
                peak_fx = sum(peak(config, mu, load, "kappa")["peak_force_N"] for load in loads)
                peak_fy = sum(peak(config, mu, load, "alpha")["peak_force_N"] for load in loads)
                distributions.append({
                    "left_share": left, "right_share": right, "left_load_N": loads[0], "right_load_N": loads[1],
                    "sum_grip_budget_D_N": grip_sum, "analytic_D_ratio_vs_50_50": grip_sum / reference_grip,
                    "sum_peak_Fx_N": peak_fx, "sum_peak_Fy_N": peak_fy,
                    "scan_Fx_ratio_vs_50_50": peak_fx / distributions[0]["sum_peak_Fx_N"] if distributions else 1.0,
                    "scan_Fy_ratio_vs_50_50": peak_fy / distributions[0]["sum_peak_Fy_N"] if distributions else 1.0,
                    "sum_Cx_N_per_slip": cx_sum, "analytic_Cx_ratio_vs_50_50": cx_sum / reference_cx,
                    "sum_Cy_N_per_rad": cy_sum, "analytic_Cy_ratio_vs_50_50": cy_sum / reference_cy,
                })
            for item in distributions:
                item["capacity_reduction_percent_vs_50_50"] = 100 * (1 - item["analytic_D_ratio_vs_50_50"])
                item["scan_Fx_reduction_percent_vs_50_50"] = 100 * (1 - item["scan_Fx_ratio_vs_50_50"])
                item["scan_Fy_reduction_percent_vs_50_50"] = 100 * (1 - item["scan_Fy_ratio_vs_50_50"])
            output[group] = {
                "total_axle_load_N": total,
                "exponents": {"peak_D": config.tire_peak_load_exponent, "longitudinal_Cx": config.longitudinal_load_exponent,
                              "lateral_Cy": config.lateral_load_exponent},
                "distributions": distributions,
            }
    return output


def characteristics():
    results = {}
    for road, mu in ROADS:
        for axle, config in AXLES:
            key = f"{road}/{axle}"
            loads = {}
            for load in LOADS:
                cx, cy = tire_stiffness(load, config)
                loads[str(load)] = {
                    "normal_load_N": load, "normal_load_multiple_Fn0": load / FN0,
                    "normal_load_multiple_suspension_limit": load / config.suspension_force_limit,
                    "grip_budget_D_N": tire_grip(load, mu, config), "Cx_N_per_slip": cx, "Cy_N_per_rad": cy,
                    "small_slip_measured_slopes": small_slip_slopes(config, mu, load),
                    "pure_longitudinal_peak": peak(config, mu, load, "kappa"),
                    "pure_lateral_peak": peak(config, mu, load, "alpha"),
                }
            results[key] = {"mu": mu, "loads": loads}
    return results


def main():
    if OUT.exists():
        raise FileExistsError(f"output directory must not exist; refusing overwrite: {OUT}")
    OUT.mkdir()
    before = source_hashes()
    try:
        grid = write_grid()
        comparisons = compare_baselines()
        redistribution = load_transfer_analysis()
        properties = characteristics()
        after = source_hashes()
        budget_max = 0.0
        with gzip.open(OUT / grid["file"], "rt", newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                budget_max = max(budget_max, float(row["force_budget_ratio"]) - 1.0)
        summary = {
            "task": "PHYS-TIRE-02 candidate load-property scan", "status": "completed",
            "timestamp_utc": datetime.now(UTC).isoformat(), "source_sha256_before": before,
            "source_sha256_after": after, "source_unchanged": before == after,
            "source_file_count": len(before), "reference_config": json_config(REFERENCE_CAR),
            "reference_config_name": "DrivingMode.SIMULATION.vehicle_config / REFERENCE_CAR",
            "units": {"force": "N", "normal_load": "N", "kappa": "dimensionless slip ratio", "alpha": "rad", "Cx": "N per slip ratio", "Cy": "N/rad", "mu": "dimensionless"},
            "Fn0_N": FN0, "actual_suspension_force_limit_N_per_wheel": REFERENCE_CAR.suspension_force_limit,
            "load_levels_N": LOADS, "load_levels_multiple_Fn0": [load / FN0 for load in LOADS],
            "road_surfaces": {name: {"mu": mu} for name, mu in ROADS},
            "grid": {**grid, "kappa_values": KAPPAS, "alpha_values_rad": ALPHAS,
                     "positive_negative_joint_slip_included": True, "maximum_force_budget_ratio_excess": max(0.0, budget_max)},
            "high_resolution_peak_scan": {"samples_per_positive_slip_curve": PEAK_N, "kappa_range": [0, KAPPA_MAX], "alpha_range_rad": [0, ALPHA_MAX]},
            "small_slip_slope": {"method": "central difference of production tire_force", "epsilon": EPS},
            "properties_and_peaks_by_surface_axle_load": properties,
            "fixed_axle_load_redistribution": redistribution,
            "strict_baseline_comparisons": comparisons,
            "analytic_model": {"D": "mu*Fn*(Fn/Fn0)^(pD-1)", "Cx": "Cx0*(Fn/Fn0)^pX", "Cy": "Cy0*(Fn/Fn0)^pY",
                               "redistribution_ratio_for_exponent_p": "(sum(Fn_i^p))/(sum(Fn_i,50:50^p))"},
            "evidence_boundary": "deterministic characteristic scan using production tire_force, tire_grip and tire_stiffness; no candidate runtime/vehicle handling claim",
        }
        (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        (OUT / "status.json").write_text(json.dumps({"status": "completed", "grid_rows": grid["rows"], "baseline_comparisons": comparisons,
                                                       "source_unchanged": before == after}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "completed", "output": str(OUT), "grid_rows": grid["rows"],
                          "max_budget_ratio_excess": max(0.0, budget_max), "baseline_comparisons": comparisons,
                          "load_capacity_reduction_percent": {key: [round(item["capacity_reduction_percent_vs_50_50"], 6)
                                                                     for item in value["distributions"]]
                                                               for key, value in redistribution.items()},
                          "source_file_count": len(before), "source_unchanged": before == after}, ensure_ascii=False, indent=2))
    except Exception as error:
        (OUT / "status.json").write_text(json.dumps({"status": "failed", "error_type": type(error).__name__,
                                                       "error": str(error), "source_sha256_before": before,
                                                       "source_sha256_after": source_hashes()}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
