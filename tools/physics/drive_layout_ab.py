"""同车两模式三布局标准对照；复用既有实际工况，保留逐拍输出与失败。"""

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from physics.esc_probe import MODES, run_trial, trial_config, write_csv
from physics.tire_load_probe import LOAD_CASES

LAYOUTS = {"RWD": 0., "FWD": 1., "AWD": .5}


def run_matrix(output, duration=6., cases=LOAD_CASES, modes=MODES):
    output.mkdir(parents=True, exist_ok=False)

    def hashes():
        return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for directory in ("src", "tests", "tools") for p in sorted((ROOT / directory).rglob("*.py"))}

    source = hashes()
    results = []
    pending = [(mode, case, layout) for mode in modes for case in cases for layout in LAYOUTS]
    report = {"status": "running", "source_before": source, "results": results,
              "protocol": {"duration_s": duration, "frequency_hz": 120, "stride": 1,
                           "comparison": "same mode/car/control; only front_drive_share differs",
                           "layouts": LAYOUTS, "scope": "native mechanical layout comparison; not human/performance gate"}}

    def save():
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    save()
    try:
        for mode in modes:
            for case in cases:
                group = {"mode": mode, "case": case}
                results.append(group)
                for layout, share in LAYOUTS.items():
                    config = replace(trial_config(case, True, mode), front_drive_share=share)
                    summary, rows = run_trial(case, True, duration, mode, vehicle_config=config)
                    maximum = max(row[f"state.wheel_dynamics.{i}.force_residual"] for row in rows[1:] for i in range(4))
                    assert maximum < .001
                    for row in rows[1:]:
                        total = row["state.powertrain_state.drive_torque"]
                        for i in range(4):
                            actual = row[f"state.wheel_dynamics.{i}.drive_torque"]
                            expected = total * (share if i < 2 else 1 - share) / 2
                            assert abs(actual - expected) < 1e-10
                    filename = f"{mode}-{case}-{layout}.csv.gz"
                    write_csv(output / filename, rows)
                    group[layout] = {**summary, "trace": filename, "max_force_residual": maximum}
                    pending.remove((mode, case, layout))
                    save()
                    print(f"DONE {mode}/{case}/{layout} speed={summary['final_horizontal_speed_mps']:.4f}", flush=True)
                metrics = ("final_horizontal_speed_mps", "path_distance_m", "peak_abs_unwrapped_heading_deg",
                           "peak_abs_yaw_rate_radps", "abs_sideslip_integral_rad_s", "abs_yaw_error_integral_rad")
                group["FWD_minus_RWD"] = {key: group["FWD"][key] - group["RWD"][key] for key in metrics}
                group["AWD_minus_RWD"] = {key: group["AWD"][key] - group["RWD"][key] for key in metrics}
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", error=repr(error), failed_trial=pending[0], not_run=pending[1:])
        save()
        raise
    after = hashes()
    report.update(status="completed", source_after=after, source_stable=source == after)
    save()
    assert source == after
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=6.)
    parser.add_argument("--cases", nargs="+", choices=LOAD_CASES, default=LOAD_CASES)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=MODES)
    args = parser.parse_args()
    run_matrix(args.output, args.duration, args.cases, args.modes)
