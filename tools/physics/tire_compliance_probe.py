"""轮胎接触区柔性逐tick A/B；仅切换柔性，单列储能与每步耗散账本。"""

import argparse
import hashlib
import json
import math
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from physics.esc_probe import FIXED_DT, MODES, SETTLE_TICKS, write_csv
from physics.esc_probe import run_trial as esc_run_trial
from physics.esc_probe import source_hashes as esc_source_hashes
from physics.esc_probe import trial_config as esc_trial_config
from physics.tire_load_probe import LOAD_CASES

DISSIPATION_FIELDS = ("material_dissipation", "road_dissipation",
                      "elastic_numerical_dissipation", "frame_dissipation")


def trial_config(case, candidate, mode="simulation"):
    config = esc_trial_config(case, True, mode)
    return replace(config, tire_compliance=candidate)


def energy_summary(rows):
    """耗散字段已为单个固定步子步累计；初始行不再计入试验耗散。"""
    wheels = []
    for index in range(4):
        prefix = f"state.wheel_dynamics.{index}."
        samples = rows[1:]
        wheel = {f"{field}_sum_j": sum(row[prefix+field] for row in samples)
                 for field in DISSIPATION_FIELDS}
        wheel.update({
            "initial_elastic_energy_j": rows[0][prefix+"elastic_energy"],
            "final_elastic_energy_j": rows[-1][prefix+"elastic_energy"],
            "peak_elastic_energy_j": max(row[prefix+"elastic_energy"] for row in rows),
            "peak_deformation_m": max(math.hypot(row[prefix+"deformation_x"], row[prefix+"deformation_y"]) for row in rows),
        })
        for field in ("force_patch_kappa", "force_patch_alpha", "force_kappa", "force_alpha", "kappa", "alpha"):
            values = [abs(row[prefix+field]) for row in samples if row[prefix+field] is not None]
            wheel[f"peak_abs_{field}"] = max(values) if values else None
        wheels.append(wheel)
    return {"wheels": wheels, "total_dissipation_j": {
        field: sum(wheel[f"{field}_sum_j"] for wheel in wheels) for field in DISSIPATION_FIELDS}}


def run_trial(case, candidate, duration=6.0, mode="simulation"):
    config = trial_config(case, candidate, mode)
    summary, rows = esc_run_trial(case, True, duration, mode, vehicle_config=config)
    return {**summary, "tire_compliance": candidate, "energy": energy_summary(rows)}, rows


def source_hashes():
    hashes = esc_source_hashes()
    for path in (Path(__file__), ROOT / "tools/physics/tire_load_probe.py"):
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def mode_energy_summary(results):
    aggregate = {}
    for mode in dict.fromkeys(pair["mode"] for pair in results):
        aggregate[mode] = {}
        for label in ("A", "B"):
            entries = [pair[label]["energy"] for pair in results if pair["mode"] == mode]
            wheels = []
            for index in range(4):
                wheel = {f"{field}_sum_j": sum(entry["wheels"][index][f"{field}_sum_j"] for entry in entries)
                         for field in DISSIPATION_FIELDS}
                for field in ("peak_elastic_energy_j", "peak_deformation_m", "peak_abs_force_patch_kappa",
                              "peak_abs_force_patch_alpha", "peak_abs_force_kappa", "peak_abs_force_alpha",
                              "peak_abs_kappa", "peak_abs_alpha"):
                    values = [entry["wheels"][index][field] for entry in entries
                              if entry["wheels"][index][field] is not None]
                    wheel[field] = max(values) if values else None
                wheels.append(wheel)
            aggregate[mode][label] = {"wheels": wheels}
    return aggregate


def run_matrix(output, duration=6.0, cases=LOAD_CASES, modes=MODES):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    source = source_hashes()
    results = []
    pending = [(mode, case, label) for mode in modes for case in cases for label in ("A", "B")]
    try:
        for mode in modes:
            for case in cases:
                pair = {"mode": mode, "case": case}
                results.append(pair)
                for label, candidate in (("A", False), ("B", True)):
                    summary, rows = run_trial(case, candidate, duration, mode)
                    filename = f"{mode}-{case}-{label}.csv.gz"
                    write_csv(output / filename, rows)
                    pair[label] = {**summary, "csv_gz": filename}
                    pending.remove((mode, case, label))
                metrics = ("final_horizontal_speed_mps", "path_distance_m", "peak_abs_unwrapped_heading_deg",
                           "peak_abs_yaw_rate_radps", "abs_sideslip_integral_rad_s", "abs_yaw_error_integral_rad")
                pair["B_minus_A"] = {key: pair["B"][key]-pair["A"][key] for key in metrics}
    except Exception as error:
        failure = {"status": "failed", "failed_trial": pending[0], "not_run": pending[1:],
                   "error": f"{type(error).__name__}: {error}", "cases": results,
                   "source_sha256_before": source, "source_sha256_after": source_hashes()}
        (output / "summary.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        raise
    report = {"status": "completed", "source_sha256_before": source,
              "source_sha256_after": source_hashes(), "cases": results,
              "mode_energy": mode_energy_summary(results), "protocol": {
                  "observer": "simulation truth; mechanism evidence, no real-car validation",
                  "world": "independent horizontal Bullet plane; gravity -9.81; no window",
                  "step_s": FIXED_DT, "sample_stride": 1, "duration_s": duration,
                  "settle_ticks": SETTLE_TICKS, "airborne_settle_ticks": 0,
                  "comparison": "same mode car, initial conditions, controls, load exponents and K/b; A compliance false, B true; ABS/TCS/ESC all true",
                  "initialization": "once-only speed/pure rolling, airborne +2m or coast yaw +.5rad/s; no runtime edits",
                  "energy_phase": "deformation, elastic_energy and force_patch_kappa/alpha are final tire substep at force_contact_tick; force_kappa/alpha same force phase; kappa/alpha are completed Bullet observations at sample_tick; SI force and completed sample share the outer contact tick but occur before/after Bullet respectively",
                  "dissipation": "material/road/elastic_numerical/frame fields are Joules summed over tire substeps within one tick; trial sums exclude initial row; no positivity clamp",
                  "energy_scope": "contact storage/dissipation only; not complete chassis/engine/brake/collision energy balance; maximum energy is not time-summed",
                  "mode_energy": "per-wheel dissipation sums and storage/deformation/force-patch/force-wheel/completed-wheel slip maxima across selected independent trials; not one continuous drive",
                  "outcomes": "retain all raw trajectories and deltas; no enforced acceleration, distance or yaw improvement"}}
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=6)
    parser.add_argument("--cases", nargs="+", choices=LOAD_CASES, default=LOAD_CASES)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=MODES)
    args = parser.parse_args()
    run_matrix(args.output, args.duration, args.cases, args.modes)


if __name__ == "__main__":
    main()
