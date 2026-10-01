"""保持120Hz刚体步，仅比较轮胎2/8子步的实际响应。"""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from tire_load_probe import MODES, run_trial, source_hashes, trial_config, write_csv

CASES = ("asphalt-brake", "constant-turn", "steering-step", "airborne-recontact")


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    results = []
    pending = [(mode, case, steps) for mode in MODES for case in CASES for steps in (2, 8)]
    report = {"status": "running", "source_before": before, "trials": results,
              "protocol": "candidate load exponents; same mode/commands/initialization; only tire_substeps differs; 120Hz body unchanged",
              "scope": "numerical sensitivity observations, no new acceptance threshold"}
    try:
        for mode in MODES:
            for case in CASES:
                pair = {"mode": mode, "case": case}
                results.append(pair)
                for steps in (2, 8):
                    config = replace(trial_config(case, True, mode), tire_substeps=steps)
                    summary, rows = run_trial(case, True, 6, mode, vehicle_config=config)
                    filename = f"{mode}-{case}-{steps}.csv.gz"
                    write_csv(output / filename, rows)
                    pair[str(steps)] = {**summary, "csv_gz": filename}
                    pair[str(steps)]["maximum_force_residual_n"] = max(
                        row[f"state.wheel_dynamics.{i}.force_residual"]
                        for row in rows for i in range(4))
                    pending.remove((mode, case, steps))
                metrics = ("final_horizontal_speed_mps", "path_distance_m", "heading_change_deg",
                           "peak_abs_yaw_rate_radps", "abs_yaw_error_integral_rad")
                pair["eight_minus_two"] = {key: pair["8"][key] - pair["2"][key] for key in metrics}
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", failed_trial=pending[0], not_run=pending[1:],
                      error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["source_after"] = source_hashes()
        report["source_unchanged"] = before == report["source_after"]
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
