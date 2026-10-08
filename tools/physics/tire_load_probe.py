"""两模式轮胎载荷敏感性A/B；电子控制同值，仅三个载荷指数不同。"""

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from physics.esc_probe import (
    CASES,
    EXTRA_CASES,
    FIXED_DT,
    MODES,
    SETTLE_TICKS,
    run_trial,
    write_csv,
)
from physics.esc_probe import source_hashes as esc_source_hashes
from physics.esc_probe import trial_config as esc_trial_config

LOAD_CASES = CASES+EXTRA_CASES
EXPONENT_FIELDS = ("tire_peak_load_exponent", "longitudinal_load_exponent", "lateral_load_exponent")


def trial_config(case, candidate, mode="simulation", enabled=True):
    config = esc_trial_config(case, enabled, mode)
    config = replace(config, braking=replace(config.braking, abs_enabled=enabled),
                     traction=replace(config.traction, tcs_enabled=enabled))
    if not candidate:
        config = replace(config, tire_peak_load_exponent=1.0,
                         longitudinal_load_exponent=1.0, lateral_load_exponent=1.0)
    return config


def source_hashes():
    hashes = esc_source_hashes()
    path = Path(__file__)
    hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def run_matrix(output, duration=6.0, cases=LOAD_CASES, modes=MODES, enabled=True):
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
                    config = trial_config(case, candidate, mode, enabled)
                    summary, rows = run_trial(case, enabled, duration, mode, vehicle_config=config)
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
              "protocol": {
                  "observer": "simulation truth; no real sensor/vehicle validation",
                  "world": "independent horizontal Bullet plane; gravity -9.81; no window",
                  "step_s": FIXED_DT, "sample_stride": 1, "duration_s": duration,
                  "settle_ticks": SETTLE_TICKS, "airborne_settle_ticks": 0,
                  "comparison": "same mode core car, initial conditions and commands; only three load exponents differ",
                  "baseline_A": "peak/longitudinal/lateral load exponents all 1",
                  "candidate_B": "current mode config exponents; full configs retained",
                  "electronic_switches": {"abs_enabled": enabled, "tcs_enabled": enabled, "esc_enabled": enabled},
                  "initialization": "one assignment of speed/pure rolling; airborne +2m or coast yaw +.5rad/s only at initialization; no runtime state edits",
                  "acceleration": "0 km/h; throttle 1; direction 1",
                  "constant_turn": "40 km/h; steering 3 degrees, throttle .15 fixed; no imposed radius",
                  "force_feedback": "full normal_load, force_grip, force_longitudinal_stiffness and force_lateral_stiffness per wheel retained; force_contact_tick labels force inputs; SI force and completed sample share an outer contact tick with separate phase fields",
                  "tire_contact_moment": "pre-force pose and force-phase supports; matched force_contact_tick; Fx/Fy last substep and cumulative impulse/dt mean at sampled fixed contact; body-up projection; excludes axle reactions and other torques, not net body moment",
                  "scope": "all raw outcomes and deltas retained; no mandatory distance/yaw improvement or high fidelity acceptance"}}
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=6)
    parser.add_argument("--cases", nargs="+", choices=LOAD_CASES, default=LOAD_CASES)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=MODES)
    parser.add_argument("--electronics-off", action="store_true")
    args = parser.parse_args()
    run_matrix(args.output, args.duration, args.cases, args.modes, not args.electronics_off)


if __name__ == "__main__":
    main()
