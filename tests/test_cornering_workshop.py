"""同条件真实定圆任务、多目标取舍、原始完成步与工作区保存。"""

import copy
import math
from dataclasses import replace

import pytest

import workshop_cornering as cornering
from lab_experiment import LabExperiment
from lab_records import LabRecord
from race import GameMode, RaceSnapshot
from vehicle_workspace import WorkspaceVehicle
from workshop import road_result, validate_receipt


@pytest.fixture(scope="module")
def trials():
    records = {}
    for selection in ((0, False, False), (1, False, False), (1, True, False), (2, False, False),
                      (3, False, False), (2, True, False), (2, False, True)):
        run = LabExperiment(cornering.OPTIONS, config=cornering.build_config(*selection))
        try:
            while not run.done:
                run.step()
            records[selection] = LabRecord.from_run(run)
        finally:
            run.close()
    return records


def test_actual_records_offer_all_medals_and_real_rejected_tradeoffs(trials):
    base = trials[0, False, False]
    expected = {(0, False, False): None, (1, False, False): "铜", (1, True, False): "银",
                (2, False, False): "金", (3, False, False): None,
                (2, True, False): "银", (2, False, True): None}
    for selection, medal in expected.items():
        result = cornering.evaluate(base, trials[selection], *selection)
        assert result["medal"] == medal and result["passed"] == (medal is not None)
    sharp = cornering.evaluate(base, trials[3, False, False], 3, False, False)
    assert sharp["candidate_metrics"]["mean_error_m"] < .3
    assert sharp["candidate_metrics"]["peak_beta_deg"] > 4
    over = cornering.evaluate(base, trials[2, False, True], 2, False, True)
    assert over["unmet"] == ["预算超出"]
    tire = cornering.evaluate(base, trials[2, False, False], 2, False, False)
    combined = cornering.evaluate(base, trials[2, True, False], 2, True, False)
    assert combined["cost"] > tire["cost"]
    assert combined["candidate_metrics"]["peak_beta_deg"] < tire["candidate_metrics"]["peak_beta_deg"]


@pytest.mark.parametrize("tire", range(4))
@pytest.mark.parametrize("bar", [False, True])
@pytest.mark.parametrize("cg", [False, True])
def test_each_recipe_keeps_surface_peak_electronics_and_unrelated_hardware(tire, bar, cg):
    base, candidate = cornering.BASE_CONFIG, cornering.build_config(tire, bar, cg)
    assert candidate.road_friction == base.road_friction == 1.1
    assert candidate.tire_peak_load_exponent == base.tire_peak_load_exponent
    assert sum(candidate.suspension_antiroll_rates) == sum(base.suspension_antiroll_rates)
    assert replace(candidate, lateral_stiffness=base.lateral_stiffness,
        suspension_antiroll_rates=base.suspension_antiroll_rates,
        center_of_mass_height=base.center_of_mass_height) == base


def test_scoring_uses_snapshots_and_ignores_edited_report_signals(trials):
    base, original = trials[0, False, False], trials[2, False, False]
    metadata = copy.deepcopy(original.metadata)
    metadata["summary"]["mean_path_error_m"] = 0
    samples = tuple({**row, "path_error": 0, "beta": 0, "horizontal_speed": 0} for row in original.samples)
    changed = replace(original, metadata=metadata, samples=samples)
    assert cornering.evaluate(base, changed, 2, False, False) == cornering.evaluate(base, original, 2, False, False)


@pytest.mark.parametrize("kind", ["truncated", "time", "reset", "collision", "nonfinite", "options", "source", "runtime", "hardware", "initial_speed", "driver"])
def test_incomplete_or_mismatched_records_cannot_award(trials, kind):
    base, candidate = trials[0, False, False], trials[2, False, False]
    metadata = copy.deepcopy(candidate.metadata)
    states = list(candidate.snapshots)
    if kind == "truncated":
        states.pop()
    elif kind == "time":
        states[25] = replace(states[25], time=states[25].time+.001)
    elif kind == "reset":
        states[25] = replace(states[25], events=("player_reset",))
    elif kind == "collision":
        states[25] = replace(states[25], collisions=states[25].collisions+1)
    elif kind == "nonfinite":
        states[25] = replace(states[25], player=replace(states[25].player, steering=math.nan))
    elif kind == "options":
        metadata["summary"]["options"]["friction"] = .9
    elif kind == "source":
        metadata["source_end"] = {}
    elif kind == "runtime":
        metadata["runtime_end"] = {}
    elif kind == "hardware":
        metadata["vehicle_config"]["road_friction"] = 1.3
    elif kind == "initial_speed":
        states[0] = replace(states[0], player=replace(states[0].player, velocity=(0., 1., 0.)))
    elif kind == "driver":
        metadata["driver"]["preview_seconds"] = .6
    with pytest.raises(ValueError):
        cornering.evaluate(base, replace(candidate, metadata=metadata, snapshots=tuple(states)), 2, False, False)


def test_saved_receipt_roundtrip_and_road_validation_use_the_same_frozen_car(trials, tmp_path):
    receipt = cornering.evaluate(trials[0, False, False], trials[2, False, False], 2, False, False)
    config = cornering.build_config(2, False, False)
    vehicle = WorkspaceVehicle("reference-rwd", config, workshop_result=receipt)
    path = tmp_path/"vehicle.json"
    vehicle.save(path)
    assert WorkspaceVehicle.load(path) == vehicle
    validate_receipt(receipt, config)
    assert vehicle.with_electronics(replace(config, tire_substeps=1)).workshop_result == receipt
    assert vehicle.with_electronics(replace(config, stability=replace(config.stability, esc_enabled=True))).workshop_result is None
    race = RaceSnapshot(mode=GameMode.TIME_TRIAL, finished=True, last_lap=80.)
    assert road_result(receipt, race, "coastal")["road_validated"]
    assert road_result(receipt, replace(race, invalidated=True), "coastal") is None
    assert road_result(receipt, race, "endless") is None


@pytest.mark.parametrize("key,value", [("medal", "银"), ("improvement_pct", math.nan), ("cost", True)])
def test_corrupted_persisted_receipt_is_rejected(trials, key, value):
    receipt = cornering.evaluate(trials[0, False, False], trials[2, False, False], 2, False, False)
    receipt[key] = value
    with pytest.raises(ValueError):
        validate_receipt(receipt, cornering.build_config(2, False, False))
