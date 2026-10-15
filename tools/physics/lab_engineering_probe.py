"""真实制动/对开/定圆工况留证，工程分析与CSV/完整记录往返核对。"""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lab_experiment import LabExperiment, LabOptions
from lab_metrics import engineering_analysis
from lab_records import LabRecord, export_record, load_record


def probe(output):
    output.mkdir(parents=True, exist_ok=False)
    results = {}
    for label, options in (
        ("dry-braking", LabOptions(friction=1.1)),
        ("low-grip-braking", LabOptions(friction=.6)),
        ("split-braking", LabOptions(maneuver="split_braking", friction=1.1, right_friction=.3)),
        ("constant-radius", LabOptions(maneuver="constant_radius", speed_kph=60, duration=8)),
        ("steady-radius-12", LabOptions(maneuver="constant_radius", speed_kph=60, duration=12)),
    ):
        run = LabExperiment(options)
        try:
            while not run.done:
                run.step()
            record = LabRecord.from_run(run)
            assert run.reason in ("stopped", "time_limit")
            analysis = engineering_analysis(record.samples, record.snapshots,
                                            record.metadata["summary"]["options"], run.reason)
            for row in record.samples[1:]:
                for wheel in ("fl", "fr", "rl", "rr"):
                    budget = row[f"force_grip_{wheel}"]
                    residual = row[f"force_residual_{wheel}"]
                    norm = math.hypot(row[f"fx_{wheel}"], row[f"fy_{wheel}"])
                    assert norm <= budget+math.sqrt(2)*residual+1e-7
            export_record(record, output/label)
            loaded = load_record(output/label)
            assert loaded.samples == record.samples and loaded.snapshots == record.snapshots
            assert record.metadata["source_start"] == record.metadata["source_end"]
            results[label] = {"summary": record.metadata["summary"], "analysis": analysis,
                              "source_unchanged": True, "export_load_exact": True}
            print(label, json.dumps({item["key"]: item["value"] for item in analysis["metrics"]}))
        finally:
            run.close()
    dry, low = (results[label]["analysis"]["metrics"][0]["value"]
                for label in ("dry-braking", "low-grip-braking"))
    assert dry is not None and low is not None and dry > low
    (output/"summary.json").write_text(json.dumps(results, ensure_ascii=False, indent=2,
                                               allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    probe(parser.parse_args().output.resolve())
