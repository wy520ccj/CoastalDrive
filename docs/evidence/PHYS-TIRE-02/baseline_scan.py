from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent / "baseline-scan"
sys.path.insert(0, str(ROOT / "src"))
from driving_modes import REFERENCE_CAR
from tire_forces import tire_force

FN0 = REFERENCE_CAR.mass * 9.81 / 4
ROADS = (("asphalt", REFERENCE_CAR.road_friction), ("grass", REFERENCE_CAR.grass_friction))
AXLES = (("front", REFERENCE_CAR), ("rear", replace(REFERENCE_CAR, lateral_stiffness=REFERENCE_CAR.rear_lateral_stiffness)))
LOADS = (0, .5, 1, 1.5, 2)
KAPPAS = (-1, -.3, -.15, -.12, -.06, 0, .06, .12, .15, .3, 1)
ALPHAS = (-.3, -.12, 0, .12, .3)
SOURCES = tuple(ROOT / "src" / name for name in ("tire_forces.py", "vehicle_config.py", "driving_modes.py"))
PEAK_N = 40001
EPS = 1e-5


def source_sha():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES}


def peak(config, mu, load, axis):
    if load == 0:
        return {"peak_force_N": 0.0, "peak_slip": 0.0}
    end = 3.0 if axis == "kappa" else 1.55
    best_force, best_slip = -1.0, 0.0
    for i in range(PEAK_N):
        slip = end * i / (PEAK_N - 1)
        fx, fy = tire_force(slip if axis == "kappa" else 0,
                            slip if axis == "alpha" else 0, load, mu, config)
        force = abs(fx if axis == "kappa" else fy)
        if force > best_force:
            best_force, best_slip = force, slip
    return {"peak_force_N": best_force, "peak_slip": best_slip}


def cornering_stiffness(config, mu, load):
    if load == 0:
        return 0.0
    fy_plus = tire_force(0, EPS, load, mu, config)[1]
    fy_minus = tire_force(0, -EPS, load, mu, config)[1]
    return abs((fy_plus - fy_minus) / (2 * EPS))


def short_check():
    ks, alphas, loads = (-.3, 0, .3), (-.12, 0, .12), (0, FN0 / 2, FN0)
    count = 0
    budget_excess = symmetry_error = 0.0
    for _, mu in ROADS:
        for _, config in AXLES:
            for load in loads:
                for k in ks:
                    for a in alphas:
                        fx, fy = tire_force(k, a, load, mu, config)
                        count += 1
                        budget_excess = max(budget_excess, math.hypot(fx, fy) - mu * load)
                        if load:
                            ox, oy = tire_force(-k, -a, load, mu, config)
                            symmetry_error = max(symmetry_error, abs(fx + ox), abs(fy + oy))
    expected = len(ROADS) * len(AXLES) * len(loads) * len(ks) * len(alphas)
    if count != expected or budget_excess > 1e-9 or symmetry_error > 1e-9:
        raise RuntimeError(f"short scan failed: rows={count}/{expected}, budget_excess={budget_excess}, symmetry_error={symmetry_error}")
    return {"rows": count, "expected_rows": expected, "maximum_force_budget_excess_N": max(0, budget_excess),
            "maximum_force_odd_symmetry_error_N": symmetry_error, "result": "passed"}


def grid_csv():
    path = OUT / "tire-force-grid.csv.gz"
    header = ("road_surface", "mu", "axle", "normal_load_N", "load_multiple_Fn0", "kappa", "alpha_rad", "fx_N", "fy_N", "force_magnitude_N", "budget_mu_Fn_N")
    rows = 0
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for road, mu in ROADS:
            for axle, config in AXLES:
                for mult in LOADS:
                    load = mult * FN0
                    for k in KAPPAS:
                        for a in ALPHAS:
                            fx, fy = tire_force(k, a, load, mu, config)
                            writer.writerow((road, mu, axle, load, mult, k, a, fx, fy, math.hypot(fx, fy), mu * load))
                            rows += 1
    expected = len(ROADS) * len(AXLES) * len(LOADS) * len(KAPPAS) * len(ALPHAS)
    if rows != expected:
        raise RuntimeError(f"grid rows {rows}, expected {expected}")
    return {"file": path.name, "rows": rows, "expected_rows": expected, "columns": header}


def analyses():
    curves, redistributions = {}, {}
    for road, mu in ROADS:
        for axle, config in AXLES:
            key = f"{road}/{axle}"
            curves[key] = {"mu": mu, "longitudinal_stiffness_N_per_slip": config.longitudinal_stiffness,
                           "lateral_stiffness_config_N_per_rad": config.lateral_stiffness, "loads": {}}
            for mult in LOADS:
                load = mult * FN0
                curves[key]["loads"][str(mult)] = {
                    "normal_load_N": load,
                    "pure_longitudinal_peak": peak(config, mu, load, "kappa"),
                    "pure_lateral_peak": peak(config, mu, load, "alpha"),
                    "small_slip_lateral_stiffness_N_per_rad": cornering_stiffness(config, mu, load),
                }
            allocs = []
            for left, right in ((.5, .5), (.3, .7), (.1, .9)):
                ll, rl = 2 * FN0 * left, 2 * FN0 * right
                pfx = peak(config, mu, ll, "kappa")["peak_force_N"] + peak(config, mu, rl, "kappa")["peak_force_N"]
                pfy = peak(config, mu, ll, "alpha")["peak_force_N"] + peak(config, mu, rl, "alpha")["peak_force_N"]
                allocs.append({"left_share": left, "right_share": right, "left_load_N": ll, "right_load_N": rl,
                               "longitudinal_axle_peak_N": pfx, "lateral_axle_peak_N": pfy,
                               "axle_small_slip_lateral_stiffness_N_per_rad": cornering_stiffness(config, mu, ll) + cornering_stiffness(config, mu, rl)})
            fx0, fy0 = allocs[0]["longitudinal_axle_peak_N"], allocs[0]["lateral_axle_peak_N"]
            for item in allocs:
                item["longitudinal_peak_delta_from_50_50_N"] = item["longitudinal_axle_peak_N"] - fx0
                item["lateral_peak_delta_from_50_50_N"] = item["lateral_axle_peak_N"] - fy0
            redistributions[key] = {
                "total_axle_load_N": 2 * FN0, "allocations": allocs,
                "maximum_longitudinal_peak_spread_N": max(x["longitudinal_axle_peak_N"] for x in allocs) - min(x["longitudinal_axle_peak_N"] for x in allocs),
                "maximum_lateral_peak_spread_N": max(x["lateral_axle_peak_N"] for x in allocs) - min(x["lateral_axle_peak_N"] for x in allocs),
                "interpretation": "linear Fn scaling; aggregate peak invariant within sampled numerical error",
            }
    return curves, redistributions


def main():
    if OUT.exists():
        raise FileExistsError(f"output directory already exists: {OUT}")
    OUT.mkdir()
    before = source_sha()
    try:
        check = short_check()
        grid = grid_csv()
        curves, redistribution = analyses()
        after = source_sha()
        summary = {
            "task": "PHYS-TIRE-02 baseline scan", "status": "completed", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source_sha256_before": before, "source_sha256_after": after, "source_unchanged": before == after,
            "evidence_boundary": "production tire_force called read-only with REFERENCE_CAR; no candidate power law and no vehicle runtime claim",
            "units": {"force": "N", "normal_load": "N", "kappa": "dimensionless slip ratio", "alpha": "rad", "stiffness": "N/rad", "mu": "dimensionless"},
            "reference_vehicle": {"mass_kg": REFERENCE_CAR.mass, "Fn0_N": FN0, "longitudinal_stiffness_N_per_slip": REFERENCE_CAR.longitudinal_stiffness,
                                  "front_lateral_stiffness_N_per_rad": REFERENCE_CAR.lateral_stiffness,
                                  "rear_lateral_stiffness_N_per_rad": REFERENCE_CAR.rear_lateral_stiffness,
                                  "tire_shape": REFERENCE_CAR.tire_shape, "tire_curvature": REFERENCE_CAR.tire_curvature},
            "road_surfaces": {name: {"mu": mu, "config_field": "road_friction" if name == "asphalt" else "grass_friction"} for name, mu in ROADS},
            "grid_definition": {"load_multipliers_Fn0": LOADS, "kappa": KAPPAS, "alpha_rad": ALPHAS}, "short_scan_self_check": check,
            "grid_csv": grid,
            "peak_scan": {"samples_per_curve": PEAK_N, "kappa_range": [0, 3], "alpha_range_rad": [0, 1.55],
                          "small_slip_stiffness_epsilon_rad": EPS, "results_by_surface_and_axle": curves},
            "fixed_axle_load_redistribution": redistribution,
            "numerical_error_accounting": {"peak_scan": "finite 40001-point positive-slip scans; allocation spreads are explicitly reported", "stiffness": "central finite difference at stated epsilon",
                                           "budget_and_symmetry": check, "source_sha_match": before == after},
        }
        (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        (OUT / "status.json").write_text(json.dumps({"status": "completed", "grid_rows": grid["rows"], "short_scan_self_check": check}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"status": "completed", "output": str(OUT), "grid_rows": grid["rows"], "Fn0_N": FN0,
                          "short_scan_self_check": check,
                          "load_transfer_peak_spread_N": {k: {"Fx": v["maximum_longitudinal_peak_spread_N"], "Fy": v["maximum_lateral_peak_spread_N"]} for k, v in redistribution.items()},
                          "source_unchanged": before == after}, ensure_ascii=False, indent=2))
    except Exception as error:
        (OUT / "status.json").write_text(json.dumps({"status": "failed", "error_type": type(error).__name__, "error": str(error),
                                                      "source_sha256_before": before, "source_sha256_after": source_sha()}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
