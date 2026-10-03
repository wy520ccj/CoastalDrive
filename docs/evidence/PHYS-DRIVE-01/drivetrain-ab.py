"""传动与参考连续性标准A/B；冻结旧策略与新完整闭环，同原生执行器输入。"""

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from physics.esc_probe import MODES, run_trial, trial_config, write_csv
from physics.tire_compliance_probe import energy_summary
from physics.tire_load_probe import LOAD_CASES


def run_matrix(output):
    output.mkdir(parents=True, exist_ok=False)
    hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ("src", "tests", "tools") for p in sorted((ROOT / folder).rglob("*.py"))}
    before = hashes()
    results = []
    pending = [(mode, case, label) for mode in MODES for case in LOAD_CASES for label in ("A", "B")]
    report = {"status": "running", "source_before": before, "cases": results,
        "protocol": {"duration_s": 6., "step_hz": 120, "sample_stride": 1,
            "comparison": "same mode car/commands; finite_drivetrain and stability.continuous_reference are the only two flags changed",
            "A": "explicit frozen ROT mechanism and old zero-below-minimum ESC reference; both off compatibility independently verified",
            "B": "finite engine/clutch/open differential with supported low-speed reference tracking; no wheel-speed or engine-RPM override",
            "initialization": "existing ESC/LOAD protocol: settle, then initial speed/pure rolling or airborne height; engine idle and clutch open, no runtime state edits",
            "scope": "native actuator-input outcomes and signed heat/work; no total native engine/collision energy proof or mandatory metric improvement",
            "phase": "engine omega/RPM read after Bullet; clutch/gear torque/slip from last force substep, work/heat summed per 120Hz tick"}}

    def save():
        (output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")

    save()
    try:
        for mode in MODES:
            for case in LOAD_CASES:
                pair = {"mode": mode, "case": case}
                results.append(pair)
                for label, enabled in (("A", False), ("B", True)):
                    base = trial_config(case, True, mode)
                    config = replace(base, finite_drivetrain=enabled,
                                     stability=replace(base.stability, continuous_reference=enabled))
                    summary, rows = run_trial(case, True, 6., mode, vehicle_config=config)
                    filename = f"{mode}-{case}-{label}.csv.gz"
                    write_csv(output / filename, rows)
                    pair[label] = {**summary, "trace": filename, "contact_energy": energy_summary(rows)}
                    if enabled:
                        prefix = "state.powertrain_state."
                        fields = ("engine_work", "engine_drag_heat", "clutch_heat", "gear_heat")
                        pair[label]["powertrain"] = {f"{field}_sum_j": sum(row[prefix + field] for row in rows[1:]) for field in fields}
                        pair[label]["powertrain"].update({f"{field}_minimum_tick_j": min(row[prefix + field] for row in rows[1:]) for field in fields[1:]})
                        assert all(row[prefix + field] >= -1e-7 for row in rows[1:] for field in fields[1:])
                        assert all(row["state.wheel_dynamics.2.drive_torque"] == row["state.wheel_dynamics.3.drive_torque"] for row in rows)
                    residual = max(row[f"state.wheel_dynamics.{i}.force_residual"] for row in rows for i in range(4))
                    pair[label]["maximum_force_residual_n"] = residual
                    assert residual < .001
                    pending.remove((mode, case, label))
                    save()
                    print(f"DONE {mode}/{case}/{label} speed={summary['final_horizontal_speed_mps']:.6g}", flush=True)
                metrics = ("final_horizontal_speed_mps", "path_distance_m", "peak_abs_unwrapped_heading_deg",
                           "peak_abs_yaw_rate_radps", "abs_sideslip_integral_rad_s", "abs_yaw_error_integral_rad")
                pair["B_minus_A"] = {key: pair["B"][key] - pair["A"][key] for key in metrics}
                save()
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", error=repr(error), failed_trial=pending[0], not_run=pending[1:])
        save()
        raise
    after = hashes()
    report.update(status="completed", source_after=after, source_stable=before == after)
    save()
    assert before == after


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run_matrix(parser.parse_args().output)
