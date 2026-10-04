"""两模式实体输入轴旧/新标准对照；固定控制和初值，保存真实逐步观测。"""

import argparse
import gzip
import hashlib
import json
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]
from physics.drivetrain_probe import command
from physics.esc_probe import CASES, EXTRA_CASES, run_trial, trial_config, write_csv
from physics.reference_ab import _create_vehicle, _step

from driving_modes import DrivingMode
from vehicle_state import FIXED_DT, VehicleCommand

MECHANICAL_CASES = ("manual-shift", "interrupted-shift", "neutral-clutch")


def mechanical_trial(case, config, duration, output):
    world, car = _create_vehicle(config)
    rows = []
    try:
        for _ in range(240):
            _step(world, car, VehicleCommand(brake=1.))
        if case != "neutral-clutch":
            car.reset(car.spawn, speed=15.)
        for tick in range(round(duration / FIXED_DT)):
            time = tick * FIXED_DT
            request = (VehicleCommand(gear=0, clutch=1., throttle=.5 if time < 1.5 else 0.)
                       if case == "neutral-clutch" else command(case, time))
            _step(world, car, request)
            rows.append({"tick": tick + 1, "input": asdict(request), "car": asdict(car.snapshot())})
        residual = max(w["force_residual"] for r in rows for w in r["car"]["wheel_dynamics"])
        heats = {name: sum(r["car"]["powertrain_state"][name] for r in rows)
                 for name in ("clutch_heat", "gear_heat", "synchronizer_heat", "engine_drag_heat")}
        assert residual < .001 and all(value >= -1e-9 for value in heats.values())
        changes = [{"tick": r["tick"], "gear": r["car"]["gear"],
                    "shaft_omega": r["car"]["powertrain_state"]["shaft_omega"],
                    "sync_slip": r["car"]["powertrain_state"]["synchronizer_slip"]}
                   for i, r in enumerate(rows) if i and r["car"]["gear"] != rows[i - 1]["car"]["gear"]]
        return {"case": case, "config": asdict(config), "ticks": len(rows), "end_speed": car.signed_speed(),
                "end_rpm": rows[-1]["car"]["rpm"], "end_train": rows[-1]["car"]["powertrain_state"],
                "max_force_residual": residual, "heats_j": heats, "gear_changes": changes}
    except (ArithmeticError, AssertionError) as error:
        output.with_suffix(".failure.json").write_text(json.dumps({"error": repr(error),
            "completed_ticks": len(rows), "config": asdict(config)}, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    finally:
        car.close()
        with gzip.open(output, "wt", encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def run_matrix(output, duration=6.):
    output.mkdir(parents=True, exist_ok=False)

    def hashes():
        return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for group in ("src", "tests", "tools") for p in sorted((ROOT / group).rglob("*.py"))}

    cases = (*CASES, *EXTRA_CASES, *MECHANICAL_CASES)
    pending = [(mode, case, enabled) for mode in ("game", "simulation") for case in cases for enabled in (False, True)]
    report = {"status": "running", "started_utc": datetime.now(UTC).isoformat(), "source_before": hashes(), "results": [],
              "protocol": {"duration_s": duration, "frequency_hz": 120, "layout": "default RWD reference and game",
                "standard_cases": [*CASES, *EXTRA_CASES], "mechanical_cases": list(MECHANICAL_CASES),
                "change": "input_shaft_enabled only; engine/control curves identical within each pair",
                "initialization": "native settle, then one explicit initial wheel/input-shaft speed; shifts reset once to 15 m/s",
                "claim": "standard two-mode old/new mechanism comparison; FWD/AWD joint mechanics/lifecycle covered separately; no human/performance gate"}}

    def save():
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    save()
    try:
        for mode in ("game", "simulation"):
            for case in cases:
                pair = {"mode": mode, "case": case}
                report["results"].append(pair)
                for enabled in (False, True):
                    label = "on" if enabled else "off"
                    base = DrivingMode(mode).vehicle_config if case in MECHANICAL_CASES else trial_config(case, True, mode)
                    config = replace(base, input_shaft_enabled=enabled)
                    if case in MECHANICAL_CASES:
                        filename = f"{mode}-{case}-{label}.jsonl.gz"
                        result = mechanical_trial(case, config, duration, output / filename)
                    else:
                        result, rows = run_trial(case, True, duration, mode, config)
                        result["max_force_residual"] = max(row[f"state.wheel_dynamics.{i}.force_residual"] for row in rows for i in range(4))
                        result["heats_j"] = {name: sum(row[f"state.powertrain_state.{name}"] for row in rows[1:])
                                             for name in ("clutch_heat", "gear_heat", "synchronizer_heat", "engine_drag_heat")}
                        assert result["max_force_residual"] < .001 and all(value >= -1e-9 for value in result["heats_j"].values())
                        filename = f"{mode}-{case}-{label}.csv.gz"
                        write_csv(output / filename, rows)
                    pair[label] = {**result, "trace": filename}
                    pending.remove((mode, case, enabled))
                    save()
                    print(f"DONE {mode}/{case}/{label}", flush=True)
    except (ArithmeticError, AssertionError, ValueError, OSError) as error:
        report.update(status="failed", error=repr(error), failed_trial=pending[0], not_run=pending[1:])
        save()
        raise
    after = hashes()
    report.update(status="completed", finished_utc=datetime.now(UTC).isoformat(), source_after=after,
                  source_stable=report["source_before"] == after)
    save()
    assert report["source_stable"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=6.)
    args = parser.parse_args()
    run_matrix(args.output, args.duration)
