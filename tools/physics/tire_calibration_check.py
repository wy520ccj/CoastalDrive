"""合成部件恢复/错误留出拒绝及同μ完整车辆A/B，保留非实测边界。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))
sys.path.insert(0, str(ROOT/"tests"))
sys.path.insert(0, str(ROOT/"tools"))

from physics.fit_tire_bench import calibrate
from tire_bench_reference import write_bench

from lab_experiment import LabExperiment, LabOptions
from lab_records import LabRecord, changed_conditions, export_record, load_record
from vehicle_designs import vehicle_design
from vehicle_parameters import config_from_document


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    good = write_bench(output/"good-data", noise_N=3.)
    bad = write_bench(output/"bad-data", invalid_combined=True, noise_N=3.)
    assert calibrate(*good, output/"accepted", "reference-rwd")
    assert not calibrate(*bad, output/"rejected", "reference-rwd")
    document = json.loads((output/"accepted/candidate-vehicle.json").read_text(encoding="utf-8"))
    candidate = config_from_document(document, vehicle_design("reference-rwd").config)
    records = []
    for label, config, metadata in (("A", vehicle_design("reference-rwd").config, None),
                                    ("B", candidate, document["metadata"])):
        run = LabExperiment(LabOptions(speed_kph=100, friction=candidate.road_friction),
                            config=config, parameter_metadata=metadata)
        try:
            while not run.done:
                run.step()
            assert run.reason == "stopped"
            record = LabRecord.from_run(run)
            assert record.metadata["source_start"] == record.metadata["source_end"]
            records.append(record)
            print(label, json.dumps(run.summary()))
        finally:
            run.close()
    export_record(records[1], output/"vehicle-AB", records[0])
    loaded = load_record(output/"vehicle-AB")
    assert loaded.samples == records[1].samples and loaded.snapshots == records[1].snapshots
    assert records[0].samples != records[1].samples
    result = {"data_kind": "synthetic algorithm fixture, NOT measured tire data",
              "same_mu": candidate.road_friction,
              "A": records[0].metadata["summary"], "B": records[1].metadata["summary"],
              "changed_conditions": changed_conditions(*records), "candidate_export_load_exact": True}
    (output/"summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                               allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    check(parser.parse_args().output.resolve())
