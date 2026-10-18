"""真实停车、预算约束、记录条件与道路有效性的挑战回归。"""

import copy
import json
from dataclasses import replace

import pytest

from lab_experiment import LabExperiment
from lab_records import LabRecord
from race import GameMode, RaceSnapshot
from vehicle_workspace import WorkspaceVehicle
from workshop import BASE_CONFIG, OPTIONS, build_config, evaluate, road_result


@pytest.fixture(scope="module")
def trials():
    records = {}
    for selection in ((0, False), (1, False), (2, False), (0, True), (2, True)):
        run = LabExperiment(OPTIONS, config=build_config(*selection))
        try:
            while not run.done:
                run.step()
            records[selection] = LabRecord.from_run(run)
        finally:
            run.close()
    return records


def test_real_trial_offers_failure_efficient_solution_and_expensive_solution(trials):
    baseline = trials[0, False]
    original = evaluate(baseline, baseline, 0, False)
    cheap = evaluate(baseline, trials[2, False], 2, False)
    expensive = evaluate(baseline, trials[0, True], 0, True)
    over = evaluate(baseline, trials[2, True], 2, True)
    assert not original["passed"] and original["medal"] is None
    assert cheap["passed"] and cheap["medal"] == "金" and cheap["cost"] == 1
    assert expensive["passed"] and expensive["medal"] == "银" and expensive["cost"] == 3
    assert not over["passed"] and over["improvement_pct"] > cheap["improvement_pct"]
    assert build_config(2, False).road_friction == BASE_CONFIG.road_friction


@pytest.mark.parametrize("key,value", [("reason", "time_limit"), ("reason", "collision"),
                                      ("stopping_distance_m", float("nan"))])
def test_incomplete_or_invalid_trial_cannot_earn_medal(trials, key, value):
    record = trials[2, False]
    metadata = copy.deepcopy(record.metadata)
    metadata["summary"][key] = value
    with pytest.raises(ValueError):
        evaluate(trials[0, False], replace(record, metadata=metadata), 2, False)


def test_wrong_selection_conditions_or_source_rejected(trials):
    with pytest.raises(ValueError):
        evaluate(trials[0, False], trials[2, False], 1, False)
    for path in ("source_end", "runtime_end"):
        record = trials[2, False]
        metadata = copy.deepcopy(record.metadata)
        metadata[path] = {}
        with pytest.raises(ValueError):
            evaluate(trials[0, False], replace(record, metadata=metadata), 2, False)


def test_receipt_legacy_roundtrip_and_electronics_invalidation(trials, tmp_path):
    receipt = evaluate(trials[0, False], trials[2, False], 2, False)
    config = build_config(2, False)
    vehicle = WorkspaceVehicle("reference-rwd", config, workshop_result=receipt)
    path = tmp_path/"vehicle.json"
    vehicle.save(path)
    assert WorkspaceVehicle.load(path) == vehicle
    assert vehicle.with_electronics(replace(config, tire_substeps=1)).workshop_result == receipt
    changed = replace(config, braking=replace(config.braking, abs_enabled=False))
    assert vehicle.with_electronics(changed).workshop_result is None
    with pytest.raises(ValueError):
        replace(vehicle, config=BASE_CONFIG).save(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document.pop("workshop_result")
    path.write_text(json.dumps(document), encoding="utf-8")
    assert WorkspaceVehicle.load(path).workshop_result is None


def test_only_valid_coastal_lap_completes_road_validation(trials):
    receipt = evaluate(trials[0, False], trials[2, False], 2, False)
    race = RaceSnapshot(mode=GameMode.TIME_TRIAL, finished=True, last_lap=90.)
    assert road_result(receipt, race, "coastal")["road_validated"]
    assert not receipt["road_validated"]
    for invalid in (replace(race, invalidated=True), replace(race, finished=False),
                    replace(race, last_lap=None)):
        assert road_result(receipt, invalid, "coastal") is None
    assert road_result(receipt, race, "endless") is None
    assert road_result(receipt, replace(race, mode=GameMode.FREE_DRIVE), "coastal") is None
