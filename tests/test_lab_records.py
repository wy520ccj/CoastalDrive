"""保存/载入120Hz真实记录、完整快照复算和A/B条件审计。"""

import csv
import json
from dataclasses import replace

import pytest

from lab_experiment import LabExperiment, LabOptions
from lab_records import LabRecord, changed_conditions, export_record, load_record, recalculate


def record(options):
    run = LabExperiment(options)
    try:
        while not run.done:
            run.step()
        return LabRecord.from_run(run)
    finally:
        run.close()


def test_export_load_and_recalculate_reproduce_full_actual_snapshots(tmp_path):
    original = record(LabOptions(speed_kph=40, duration=.25))
    report = export_record(original, tmp_path/"trial")
    loaded = load_record(tmp_path/"trial")
    assert loaded.samples == original.samples
    assert loaded.snapshots == original.snapshots
    repeated = recalculate(loaded)
    assert repeated.samples == loaded.samples
    assert repeated.snapshots == loaded.snapshots
    assert repeated.commands == loaded.commands
    assert "Snapshot.player.wheel_dynamics" in report.read_text(encoding="utf-8")
    with (tmp_path/"trial/signals.csv").open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(original.samples)
    assert float(rows[-1]["speed"]) == original.samples[-1]["speed"]
    with pytest.raises(FileExistsError):
        export_record(original, tmp_path/"trial")


def test_ab_includes_all_actual_conditions_and_both_original_runs(tmp_path):
    baseline = record(LabOptions(speed_kph=40, duration=.1))
    candidate = record(LabOptions(speed_kph=40, duration=.1, friction=.6))
    changes = changed_conditions(baseline, candidate)
    assert set(changes) == {"options.friction", "vehicle.road_friction"}
    export_record(candidate, tmp_path/"ab", baseline)
    assert load_record(tmp_path/"ab/baseline-A").samples == baseline.samples
    assert (tmp_path/"ab/comparison.json").is_file()
    # 基线是独立快照，不会因为继续运行候选而改变。
    assert baseline.samples[-1]["speed"] != candidate.samples[-1]["speed"]


def test_corrupt_snapshot_and_different_model_versions_are_rejected(tmp_path):
    original = record(LabOptions(speed_kph=40, duration=.1))
    export_record(original, tmp_path/"trial")
    path = tmp_path/"trial/snapshots.bin"
    path.write_bytes(path.read_bytes()+b"corrupt")
    with pytest.raises(ValueError, match="损坏"):
        load_record(tmp_path/"trial")
    changed = replace(original, metadata={**original.metadata, "source_start": {"different": "version"}})
    with pytest.raises(ValueError, match="版本"):
        recalculate(changed)


def test_signal_tampering_and_vehicle_file_mismatch_are_rejected(tmp_path):
    original = record(LabOptions(speed_kph=40, duration=.1))
    export_record(original, tmp_path/"signal")
    path = tmp_path/"signal/experiment.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["samples"][1]["speed"] += 1.
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="信号数据"):
        load_record(tmp_path/"signal")
    export_record(original, tmp_path/"vehicle")
    path = tmp_path/"vehicle/vehicle.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["mass"] += 100
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="完整配置"):
        load_record(tmp_path/"vehicle")
