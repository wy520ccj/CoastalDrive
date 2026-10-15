"""合成部件拟合/拒绝、同一实际轮跳工况A/B与完整保存复算。"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))
sys.path.insert(0, str(ROOT/"tests"))
sys.path.insert(0, str(ROOT/"tools"))

from physics.fit_suspension_bench import calibrate
from suspension_bench_reference import write_bench

from lab_experiment import LabExperiment, LabOptions
from lab_metrics import engineering_analysis
from lab_records import LabRecord, changed_conditions, export_record, load_record, recalculate
from suspension_bench import record_coverage
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import config_from_document


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    base_path = ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json"
    base_document = json.loads(base_path.read_text(encoding="utf-8"))
    assert calibrate(write_bench(output/"good-input.json"), output/"accepted", base_document)
    assert not calibrate(write_bench(output/"bad-input.json", bad_validation=True), output/"rejected", base_document)
    candidate_document = json.loads((output/"accepted/candidate-vehicle.json").read_text(encoding="utf-8"))
    base = config_from_document(base_document, REFERENCE_DESIGN)
    candidate = config_from_document(candidate_document, base)
    # 本轮仅换部件硬件；簧下质量/惯量/轮胎/工况均保持。
    changes = {key for key in asdict(base) if asdict(base)[key] != asdict(candidate)[key]}
    assert changes == {"suspension_spring_rates", "suspension_compression_damping", "suspension_extension_damping"}
    records, results = [], []
    for label, config, metadata in (("A", base, base_document["metadata"]),
                                    ("B", candidate, candidate_document["metadata"])):
        run = LabExperiment(LabOptions(maneuver="ride_bump", speed_kph=18., duration=2.4),
                            config=config, parameter_metadata=metadata)
        try:
            while not run.done: run.step()
            assert run.reason == "time_limit", (run.reason, run.error)
            record = LabRecord.from_run(run)
            assert record.metadata["source_start"] == record.metadata["source_end"]
            assert record.metadata["runtime_start"] == record.metadata["runtime_end"]
            folder = output/label
            export_record(record, folder, records[0] if records else None)
            restored = load_record(folder)
            assert restored.samples == record.samples and restored.snapshots == record.snapshots and restored.commands == record.commands
            repeated_exact = None
            if label == "B":
                repeated = recalculate(restored)
                repeated_exact = (repeated.samples == restored.samples and repeated.snapshots == restored.snapshots
                                  and repeated.commands == restored.commands)
                assert repeated_exact
            results.append({"label": label, "summary": run.summary(),
                "analysis": engineering_analysis(record.samples, record.snapshots, asdict(run.options), run.reason),
                "coverage": record_coverage(metadata, asdict(config), record.samples),
                "record_roundtrip_exact": True, "recalculate_exact": repeated_exact})
            records.append(record)
            (output/"result.json").write_text(json.dumps({"results": results,
                "changed_conditions": changed_conditions(*records) if len(records) == 2 else None},
                ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
            print(json.dumps({"label": label, "frames": len(record.samples), "recalculate_exact": repeated_exact}), flush=True)
        finally:
            run.close()
    assert records[0].samples != records[1].samples


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    check(parser.parse_args().output.resolve())
