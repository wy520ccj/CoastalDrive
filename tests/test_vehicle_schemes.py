"""真实试验的多方案保存、隔离、可比条件与原始记录损坏。"""

import json
import shutil
from dataclasses import replace

import pytest

import workshop_cornering as cornering
from lab_experiment import LabExperiment, LabOptions
from lab_records import LabRecord
from vehicle_schemes import (
    compare_schemes,
    list_schemes,
    load_scheme,
    save_scheme,
    scheme_folder,
    sync_road_progress,
)
from vehicle_workspace import WorkspaceVehicle


@pytest.fixture(scope="module")
def trials():
    records = []
    for config in (cornering.BASE_CONFIG, cornering.build_config(1, False, False),
                   cornering.build_config(2, False, False), cornering.build_config(3, False, False)):
        run = LabExperiment(cornering.OPTIONS, config=config)
        try:
            while not run.done:
                run.step()
            records.append(LabRecord.from_run(run))
        finally:
            run.close()
    return records


def store(root, trials, index, name="海岸配方"):
    baseline, candidate = trials[0], trials[index]
    result = cornering.evaluate(baseline, candidate, index, False, False)
    return save_scheme(root, name, candidate, baseline, result)


def test_names_are_revisions_full_records_are_independent_and_portable(tmp_path, trials):
    a, b = store(tmp_path, trials, 1), store(tmp_path, trials, 2)
    assert a.id != b.id and a.name == b.name
    assert len(list_schemes(tmp_path)[0]) == 2
    a.records()
    b.records()
    assert a.vehicle.workshop_result["medal"] == "铜" and b.vehicle.workshop_result["medal"] == "金"
    moved = tmp_path/"moved"
    shutil.copytree(b.folder, moved/b.id)
    loaded = load_scheme(moved, b.id)
    assert loaded.records()[1].snapshots == trials[2].snapshots
    assert loaded.vehicle.report_path == str(moved/b.id/"trial"/"report.html")
    assert not (moved/a.id).exists()


def test_side_effects_failed_recipe_and_same_condition_deltas(tmp_path, trials):
    a, b, sharp = [store(tmp_path, trials, index) for index in (1, 2, 3)]
    result = compare_schemes(a, b)
    assert result["comparable"]
    rows = {label: (left, right) for label, left, right, _ in result["rows"]}
    assert rows["循迹误差"][1] < rows["循迹误差"][0]
    assert rows["峰值侧偏"][1] > rows["峰值侧偏"][0]
    assert rows["预算"] == (1, 2)
    assert sharp.vehicle.workshop_result is None and not sharp.challenge["passed"]
    assert "侧偏" in "".join(sharp.records()[2]["unmet"])


def test_road_progress_is_per_exact_scheme_and_electronics_detaches(tmp_path, trials):
    a, b = store(tmp_path, trials, 1), store(tmp_path, trials, 2)
    completed = replace(b.vehicle, workshop_result={**b.vehicle.workshop_result, "road_validated": True})
    sync_road_progress(tmp_path, completed)
    assert load_scheme(tmp_path, b.id).vehicle.workshop_result["road_validated"]
    assert not load_scheme(tmp_path, a.id).vehicle.workshop_result["road_validated"]
    loaded = load_scheme(tmp_path, b.id)
    loaded.records()
    with pytest.raises(ValueError):
        sync_road_progress(tmp_path, replace(completed, scheme_id=a.id))
    changed = replace(b.vehicle.config, stability=replace(b.vehicle.config.stability, esc_enabled=True))
    detached = b.vehicle.with_electronics(changed)
    assert detached.scheme_id is None and detached.workshop_result is None
    assert b.vehicle.with_electronics(b.vehicle.config).scheme_id == b.id
    old = tmp_path/"old.json"
    WorkspaceVehicle(b.vehicle.design_id, b.vehicle.config).save(old)
    document = json.loads(old.read_text(encoding="utf-8"))
    document.pop("scheme_id")
    old.write_text(json.dumps(document), encoding="utf-8")
    assert WorkspaceVehicle.load(old).scheme_id is None


@pytest.mark.parametrize("name", ["", "  ", "a"*25, "a\nb", 123])
def test_invalid_name_does_not_create_any_scheme(tmp_path, trials, name):
    with pytest.raises(ValueError):
        store(tmp_path, trials, 1, name)
    assert not list(tmp_path.iterdir())


def test_write_failure_or_damaged_item_keeps_other_schemes(tmp_path, trials, monkeypatch):
    good = store(tmp_path, trials, 1)
    import vehicle_schemes
    def fail(*args, **kwargs):
        raise OSError("disk full")
    with monkeypatch.context() as patch:
        patch.setattr(vehicle_schemes, "export_record", fail)
        with pytest.raises(OSError):
            store(tmp_path, trials, 2)
    schemes, errors = list_schemes(tmp_path)
    assert [item.id for item in schemes] == [good.id] and not errors
    broken = tmp_path/("f"*32)
    broken.mkdir()
    (broken/"scheme.json").write_text("{broken", encoding="utf-8")
    schemes, errors = list_schemes(tmp_path)
    assert [item.id for item in schemes] == [good.id] and len(errors) == 1
    good.records()


@pytest.mark.parametrize("target", ["trial/snapshots.bin", "trial/vehicle.json", "vehicle.json", "scheme.json"])
def test_damaged_config_record_or_receipt_cannot_apply(tmp_path, trials, target):
    item = store(tmp_path, trials, 2)
    path = item.folder/target
    if target.endswith("snapshots.bin"):
        path.write_bytes(b"broken")
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        if target == "trial/vehicle.json":
            data["mass"] += 1
        elif target == "vehicle.json":
            data["vehicle_config"]["mass"] += 1
        else:
            data["challenge"]["improvement_pct"] += 1
        path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises((ValueError, KeyError, TypeError)):
        load_scheme(tmp_path, item.id).records()


@pytest.mark.parametrize("key", ["source_start", "runtime_start", "driver"])
def test_different_versions_or_controller_are_not_claimed_as_gain(tmp_path, trials, key):
    a = save_scheme(tmp_path, "原条件", trials[2])
    value = {**trials[2].metadata[key], "different": True}
    metadata = {**trials[2].metadata, key: value}
    b = save_scheme(tmp_path, "异条件", replace(trials[2], metadata=metadata))
    result = compare_schemes(a, b)
    assert not result["comparable"] and result["mismatches"]


def test_generic_complete_trial_has_metrics_and_changed_environment_is_flagged(tmp_path, trials):
    a, b = [save_scheme(tmp_path, name, trials[index]) for name, index in (("A", 1), ("B", 2))]
    result = compare_schemes(a, b)
    assert result["comparable"] and result["rows"]
    run = LabExperiment(LabOptions(vehicle_id="reference-fwd", duration=.1, speed_kph=20, friction=.6))
    try:
        while not run.done:
            run.step()
        c = save_scheme(tmp_path, "另一工况", LabRecord.from_run(run))
    finally:
        run.close()
    assert "试验工况/车型/路面" in compare_schemes(a, c)["mismatches"]
    assert load_scheme(tmp_path, c.id).vehicle.design_id == "reference-fwd"
    assert c.records()[1].metadata["summary"]["options"]["vehicle_id"] == "reference-fwd"


@pytest.mark.parametrize("identity", ["../elsewhere", "", "a"*31, 123])
def test_scheme_identity_is_not_a_path(tmp_path, identity):
    with pytest.raises(ValueError):
        scheme_folder(tmp_path, identity)
