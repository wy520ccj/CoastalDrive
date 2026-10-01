"""离地再接触子步/ABS原因隔离；复用已有on2/on8，仅新跑四条。"""

import argparse
import csv
import gzip
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from physics.esc_probe import run_trial, write_csv
from physics.tire_compliance_probe import energy_summary, trial_config
from physics.tire_compliance_probe import source_hashes as compliance_source_hashes

NEW_TRIALS = ((True, 4), (True, 16), (False, 2), (False, 8))


def source_hashes():
    hashes = compliance_source_hashes()
    path = Path(__file__)
    hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def read_rows(path):
    with gzip.open(path, "rt", newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def aligned_comparison(a, b):
    if [int(row["tick"]) for row in a] != [int(row["tick"]) for row in b]:
        raise ValueError("逐tick轨迹时间轴不一致")
    fields = {
        "yaw_rate": lambda row: [float(row["completed_yaw_rate_radps"])],
        "left_right_load_delta": lambda row: [float(row[f"state.wheel_dynamics.{i}.normal_load"])-
                                              float(row[f"state.wheel_dynamics.{i+1}.normal_load"]) for i in (0, 2)],
        "abs_command": lambda row: [float(row[f"state.brake_states.{i}.commanded"]) for i in range(4)],
        "abs_modulation_from_requested": lambda row: [float(row[f"state.brake_states.{i}.commanded"])-
                                                       float(row[f"state.brake_states.{i}.requested"]) for i in range(4)],
        "abs_active": lambda row: [str(row[f"state.brake_states.{i}.abs_active"]) for i in range(4)],
    }
    result = {}
    for name, extract in fields.items():
        differences = []
        for old, new in zip(a[1:], b[1:]):
            va, vb = extract(old), extract(new)
            changed = va != vb if name == "abs_active" else any(abs(x-y) > 1e-9 for x, y in zip(va, vb))
            if changed:
                differences.append({"tick": int(old["tick"]), "time_s": float(old["time_s"]),
                                    "A_values": va, "B_values": vb})
        result[name] = differences[0] if differences else None
    return result


def run(output, reference):
    output = Path(output)
    reference = Path(reference)
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    pending = list(NEW_TRIALS)
    report = {"status": "running", "source_before": before, "trials": {},
              "protocol": {
                  "case": "simulation airborne-recontact 6s, compliance true, TCS/ESC true; ABS on substeps2/4/8/16, ABS off substeps2/8",
                  "reuse": "on2/on8 references are existing full raw trajectories; new runs only on4/on16/off2/off8",
                  "comparison": "same full config except tire_substeps and stated ABS switch; initial airborne +2m and 100km/h, then real fall; no runtime state edits",
                  "divergence": "numeric first divergence >1e-9 observation cutoff only, not acceptance; ABS active compares boolean",
                  "scope": "cause isolation; good component energy/residual does not prove vehicle substep convergence"}}
    current = "reference-validation"
    all_rows = {}
    try:
        baseline_path = reference / "summary.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        changed = [path for path, value in before.items() if path.startswith("src/") and baseline["source_before"][path] != value]
        if changed or not baseline["source_unchanged"]:
            raise ValueError(f"引用轨迹与当前源码不同：{changed}")
        pair = next(pair for pair in baseline["trials"] if pair["mode"] == "simulation" and pair["case"] == "airborne-recontact")
        for steps in (2, 8):
            key = f"on{steps}"
            raw = reference / pair[str(steps)]["csv_gz"]
            all_rows[key] = read_rows(raw)
            report["trials"][key] = {**pair[str(steps)], "reused_csv_gz": raw.relative_to(ROOT).as_posix(),
                                     "reused_raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                                     "reference_summary_sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest()}
        for enabled, steps in NEW_TRIALS:
            current = (enabled, steps)
            key = f"{'on' if enabled else 'off'}{steps}"
            config = replace(trial_config("airborne-recontact", True, "simulation"), tire_substeps=steps)
            config = replace(config, braking=replace(config.braking, abs_enabled=enabled))
            summary, rows = run_trial("airborne-recontact", True, 6, "simulation", vehicle_config=config)
            filename = f"simulation-airborne-recontact-{key}.csv.gz"
            write_csv(output / filename, rows)
            all_rows[key] = rows
            report["trials"][key] = {**summary, "csv_gz": filename, "energy": energy_summary(rows)}
            pending.remove((enabled, steps))
        report["comparisons"] = {}
        for a, b in (("on2", "on4"), ("on4", "on8"), ("on8", "on16"), ("on2", "on8"), ("off2", "off8")):
            report["comparisons"][f"{b}-minus-{a}"] = {
                "first_divergence": aligned_comparison(all_rows[a], all_rows[b]),
                "heading_change_delta_deg": report["trials"][b]["heading_change_deg"]-report["trials"][a]["heading_change_deg"],
                "path_distance_delta_m": report["trials"][b]["path_distance_m"]-report["trials"][a]["path_distance_m"]}
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", failed_trial=current, not_run=pending,
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
    parser.add_argument("--reference", type=Path, default=Path(__file__).parent / "substeps")
    args = parser.parse_args()
    run(args.output, args.reference)
