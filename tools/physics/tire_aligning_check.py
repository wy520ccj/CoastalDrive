"""同车接触区回正开关/半长与机械步细化；使用真实120Hz Simulation记录。"""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))

from lab_experiment import LabExperiment, LabOptions
from lab_records import LabRecord, changed_conditions, export_record, load_record
from vehicle_designs import REFERENCE_DESIGN


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    records, results = {}, {}
    for label, enabled, half, steps in (("off", False, .08, 2), ("on-2", True, .08, 2),
                                       ("on-4", True, .08, 4), ("on-8", True, .08, 8),
                                       ("half-2", True, .04, 2)):
        config = replace(REFERENCE_DESIGN, tire_aligning_enabled=enabled,
                         tire_contact_half_length=half, tire_substeps=steps)
        run = LabExperiment(LabOptions(maneuver="step_steer", speed_kph=60,
                                       duration=3., onset=.5), config=config)
        try:
            while not run.done:
                run.step()
            assert run.reason == "time_limit", run.summary()
            record = LabRecord.from_run(run)
            assert record.metadata["source_start"] == record.metadata["source_end"]
            export_record(record, output/label)
            loaded = load_record(output/label)
            assert loaded.snapshots == record.snapshots and loaded.samples == record.samples
            records[label] = record
            results[label] = {"summary": run.summary(), "final_yaw": run.samples[-1]["yaw"],
                              "final_beta": run.samples[-1]["beta"],
                              "peak_abs_mz_Nm": max(abs(row[f"mz_{w}"]) for row in run.samples for w in ("fl","fr","rl","rr")),
                              "contact_steering_input_J": sum(row[f"contact_steering_work_{w}"] for row in run.samples[1:]
                                                               for w in ("fl","fr","rl","rr")),
                              "max_force_residual_N": max(w.force_residual for s in run.snapshots[1:] for w in s.player.wheel_dynamics),
                              "collision_count": run.current.collisions-run.initial_collisions}
        finally:
            run.close()
        print(label, json.dumps(results[label], ensure_ascii=False), flush=True)
    assert results["off"]["peak_abs_mz_Nm"] == 0.
    assert results["on-2"]["peak_abs_mz_Nm"] > 1.
    assert results["half-2"]["peak_abs_mz_Nm"] < results["on-2"]["peak_abs_mz_Nm"]
    errors = {key: abs(results[key]["final_yaw"]-results["on-8"]["final_yaw"])
              for key in ("on-2","on-4")}
    assert errors["on-4"] < errors["on-2"]
    assert all(item["collision_count"] == 0 and item["max_force_residual_N"] < .001 for item in results.values())
    summary = {"basis": "通用设计模型的机制/数值验证，非实车标定", "runs": results,
               "on_off_changes": changed_conditions(records["off"], records["on-2"]),
               "yaw_error_relative_to_eight_substeps": errors,
               "full_snapshot_export_load_exact": True}
    (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    check(parser.parse_args().output.resolve())
