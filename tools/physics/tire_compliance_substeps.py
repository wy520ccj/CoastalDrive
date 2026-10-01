"""柔性轮胎2/8子步敏感性；保持120Hz刚体步，不引入新验收门槛。"""

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from physics.esc_probe import MODES, run_trial, write_csv
from physics.tire_compliance_probe import energy_summary, trial_config
from physics.tire_compliance_probe import source_hashes as compliance_source_hashes

CASES = ("asphalt-brake", "constant-turn", "steering-step", "airborne-recontact")
SUBSTEPS = (2, 8)


def substep_config(case, mode, steps):
    return replace(trial_config(case, True, mode), tire_substeps=steps)


def source_hashes():
    hashes = compliance_source_hashes()
    path = Path(__file__)
    hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def run(output, duration=6.0):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    results = []
    pending = [(mode, case, steps) for mode in MODES for case in CASES for steps in SUBSTEPS]
    report = {"status": "running", "source_before": before, "trials": results,
              "protocol": {
                  "comparison": "same mode car, commands, initial conditions, load exponents, K/b; compliance and ABS/TCS/ESC on; only tire_substeps 2/8 differs",
                  "body_step_s": 1/120, "duration_s": duration, "sample_stride": 1,
                  "energy_phase": "energy and deformation from final tire substep at force_contact_tick; dissipation is sum of all tire substeps within each body tick; trial sums exclude initial row",
                  "scope": "simulation truth; numerical sensitivity observations only; no new acceptance threshold or real-car validation"}}
    try:
        for mode in MODES:
            for case in CASES:
                pair = {"mode": mode, "case": case}
                results.append(pair)
                for steps in SUBSTEPS:
                    config = substep_config(case, mode, steps)
                    summary, rows = run_trial(case, True, duration, mode, vehicle_config=config)
                    filename = f"{mode}-{case}-{steps}.csv.gz"
                    write_csv(output / filename, rows)
                    pair[str(steps)] = {**summary, "csv_gz": filename, "energy": energy_summary(rows),
                        "maximum_force_residual_n": max(abs(row[f"state.wheel_dynamics.{index}.force_residual"])
                                                        for row in rows[1:] for index in range(4))}
                    pending.remove((mode, case, steps))
                metrics = ("final_horizontal_speed_mps", "path_distance_m", "heading_change_deg",
                           "peak_abs_yaw_rate_radps", "abs_yaw_error_integral_rad")
                pair["eight_minus_two"] = {key: pair["8"][key]-pair["2"][key] for key in metrics}
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
    parser.add_argument("--duration", type=float, default=6)
    args = parser.parse_args()
    run(args.output, args.duration)
