"""沿用标准定圆/转向阶跃协议，只比较原生SI与当前共同悬架。"""

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from physics.esc_probe import run_trial, trial_config, write_csv


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for group in ("src", "tests", "tools") for p in sorted((ROOT / group).rglob("*.py"))}
    pending = [(mode, case, enabled) for mode in ("game", "simulation")
               for case in ("constant-turn", "steering-step") for enabled in (False, True)]
    report = {"status": "running", "source_before": hashes(), "results": [],
              "protocol": "standard ESC probe initial conditions/commands; 240 settling + 720 recorded native 120Hz steps; same ABS/TCS/ESC enabled in each mode; only suspension_coupled_enabled differs; no runtime state resets; full per-tick state and actual force-phase moments retained"}
    try:
        for mode, case, enabled in list(pending):
            config = replace(trial_config(case, True, mode), suspension_coupled_enabled=enabled)
            result, rows = run_trial(case, True, 6., mode, config)
            name = f"{mode}-{case}-{'coupled' if enabled else 'native'}.csv.gz"
            write_csv(output / name, rows)
            maximum = max(abs(row[f"state.wheel_dynamics.{i}.force_residual"]) for row in rows for i in range(4))
            assert maximum < .001
            report["results"].append({**result, "coupled": enabled, "trace": name,
                "max_tire_residual_n": maximum, "max_abs_roll_deg": max(abs(row["state.roll"]) for row in rows)})
            pending.remove((mode, case, enabled))
            print(f"DONE {name}: yaw error integral {result['abs_yaw_error_integral_rad']:.6f}", flush=True)
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", error=repr(error), failed_trial=pending[0], not_run=pending[1:])
        raise
    else:
        report["status"] = "completed"
    finally:
        report["source_after"] = hashes()
        report["source_stable"] = report["source_before"] == report["source_after"]
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    assert report["source_stable"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
