"""同配置两模式转子A/B，保留所有输入、快照、轴承冲量及指定转向做功。"""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from physics.esc_probe import MODES, run_trial, source_hashes, trial_config, write_csv
from physics.tire_compliance_probe import energy_summary
from physics.tire_load_probe import LOAD_CASES


def run_matrix(output, duration=6., cases=LOAD_CASES, modes=MODES):
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    results = []
    pending = [(mode, case, enabled) for mode in modes for case in cases for enabled in (False, True)]
    report = {"status": "running", "source_sha256_before": before, "cases": results,
              "protocol": {"duration_s": duration, "step_hz": 120, "sample_stride": 1,
                           "comparison": "same complete mode config and controls; only wheel_rotor_transport differs",
                           "scope": "contact energy and actuator steering work diagnostics; not total engine/collision energy proof"}}

    def save():
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    save()
    try:
        for mode in modes:
            for case in cases:
                pair = {"mode": mode, "case": case}
                results.append(pair)
                for label, enabled in (("A", False), ("B", True)):
                    config = replace(trial_config(case, True, mode), wheel_rotor_transport=enabled)
                    summary, rows = run_trial(case, True, duration, mode, vehicle_config=config)
                    filename = f"{mode}-{case}-{label}.csv.gz"
                    write_csv(output / filename, rows)
                    work = sum(row[f"state.wheel_dynamics.{i}.steering_work"] for row in rows[1:] for i in range(4))
                    pair[label] = {**summary, "trace": filename, "steering_work_j": work, "contact_energy": energy_summary(rows)}
                    pending.remove((mode, case, enabled))
                    save()
                    print(f"DONE {mode} {case} {label} speed={summary['final_horizontal_speed_mps']:.6g} steering-work={work:.6g}", flush=True)
                metrics = ("final_horizontal_speed_mps", "path_distance_m", "peak_abs_unwrapped_heading_deg",
                           "peak_abs_yaw_rate_radps", "abs_sideslip_integral_rad_s", "abs_yaw_error_integral_rad")
                pair["B_minus_A"] = {key: pair["B"][key] - pair["A"][key] for key in metrics}
    except (ArithmeticError, ValueError, OSError) as error:
        report.update(status="failed", error=f"{type(error).__name__}: {error}", failed_trial=pending[0], not_run=pending[1:])
        save()
        raise
    after = source_hashes()
    report.update(status="completed", source_sha256_after=after, source_stable=before == after)
    save()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=6.)
    parser.add_argument("--cases", nargs="+", choices=LOAD_CASES, default=LOAD_CASES)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=MODES)
    args = parser.parse_args()
    run_matrix(args.output, args.duration, args.cases, args.modes)
