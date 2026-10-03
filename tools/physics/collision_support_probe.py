"""两模式原生车身支撑A/B及再接触子步对照，保持同一120Hz物理核心。"""

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from physics.esc_probe import CASES, EXTRA_CASES, MODES, run_trial, trial_config, write_csv
from physics.tire_compliance_probe import energy_summary
from physics.tire_compliance_probe import source_hashes as tire_source_hashes


def source_hashes():
    hashes = tire_source_hashes()
    path = Path(__file__)
    hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def run(output, duration, recontact):
    output.mkdir(parents=True, exist_ok=False)
    plan = ([(mode, "airborne-recontact", True, steps) for mode in MODES for steps in (2, 4, 8, 16)]
            if recontact else [(mode, case, centered, 2) for mode in MODES
                              for case in CASES+EXTRA_CASES for centered in (False, True)])
    pending = plan.copy()
    report = {"status": "running", "source_before": source_hashes(), "trials": [],
              "protocol": {"body_step_s": 1/120, "duration_s": duration, "sample_stride": 1,
                  "world": "independent infinite plane; original gravity, solver and vehicle action",
                  "comparison": "same complete mode config, inputs and initial conditions; only native collider representation or tire_substeps differs",
                  "collider": "A original Box; B four zero-margin native Boxes exactly cover nominal sharp box, symmetric plane support at common face center; original inertia retained; general GJK rounded corners deliberately differ",
                  "initialization": "once-only trial initialization; no runtime motion edits",
                  "electronics": "ABS/TCS/ESC enabled; controller and rigid-body step unchanged at 120Hz",
                  "scope": "simulation truth, raw changes retained; not real-car calibration or visible performance"}}
    def save():
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                        allow_nan=False)+"\n", encoding="utf-8")
    try:
        for mode, case, centered, steps in plan:
            config = replace(trial_config(case, True, mode), centered_collision_support=centered,
                             tire_substeps=steps)
            summary, rows = run_trial(case, True, duration, mode, vehicle_config=config)
            label = "B" if centered else "A"
            filename = f"{mode}-{case}-{label}-{steps}.csv.gz"
            write_csv(output / filename, rows)
            report["trials"].append({**summary, "mode": mode, "case": case,
                "centered_collision_support": centered, "tire_substeps": steps,
                "csv_gz": filename, "energy": energy_summary(rows),
                "maximum_force_residual_n": max(abs(row[f"state.wheel_dynamics.{index}.force_residual"])
                                                for row in rows[1:] for index in range(4))})
            pending.pop(0)
            save()
            print(f"Completed {mode} {case} {label} {steps}", flush=True)
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", failed_trial=pending[0], not_run=pending[1:],
                      error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["source_after"] = source_hashes()
        report["source_unchanged"] = report["source_before"] == report["source_after"]
        save()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=6)
    parser.add_argument("--recontact-substeps", action="store_true")
    args = parser.parse_args()
    run(args.output, args.duration, args.recontact_substeps)
