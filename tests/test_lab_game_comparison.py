"""真实物理对照的输入、配置、终止和可追溯结果。"""

import json
from dataclasses import replace

import pytest

from lab_experiment import LabExperiment, LabOptions
from lab_game_comparison import GameComparison, comparison_report, reference_vehicle
from lab_records import LabRecord, load_record, recalculate
from vehicle_designs import REFERENCE_DESIGN


@pytest.fixture(scope="module")
def reference():
    config = replace(REFERENCE_DESIGN, mass=1400., center_of_mass_height=.43, tire_substeps=2)
    run = LabExperiment(LabOptions(maneuver="step_steer", speed_kph=35, duration=.3, onset=.05), config=config)
    try:
        while not run.done:
            run.step()
        return LabRecord.from_run(run)
    finally:
        run.close()


def test_same_hardware_and_commands_use_game_substeps_and_recalculate(reference, tmp_path):
    comparison = GameComparison(reference)
    try:
        while not comparison.done:
            comparison.advance(.1)
        actual = LabRecord.from_run(comparison.run)
        report = comparison_report(reference, actual)
        assert comparison.run.config.mass == 1400
        assert report["config_changes"] == {"tire_substeps": {"reference": 2, "game": 1}}
        assert actual.commands == reference.commands
        assert report["same_command_prefix"] and report["common_seconds"] == .3
        assert report["assessment"] == "未设置合格阈值"
        page = comparison.export(tmp_path/"comparison")
        assert page.exists() and (page.parent/"reference/report.html").exists()
        saved = load_record(page.parent/"game")
        assert saved.metadata["runtime_profile"] == "game"
        assert recalculate(saved).samples == saved.samples
        assert json.loads((page.parent/"comparison.json").read_text(encoding="utf-8"))["same_command_prefix"]
    finally:
        comparison.close()


@pytest.mark.parametrize("reason", [None, "failed", "collision", "reset"])
def test_incomplete_or_failed_trial_cannot_be_applied(reference, reason):
    metadata = {**reference.metadata, "summary": {**reference.metadata["summary"], "reason": reason}}
    with pytest.raises(ValueError, match="完成"):
        reference_vehicle(replace(reference, metadata=metadata))


def test_old_source_cannot_be_used_for_current_fidelity_comparison(reference):
    metadata = {**reference.metadata, "source_start": {"old": "source"}}
    with pytest.raises(ValueError, match="源码"):
        GameComparison(replace(reference, metadata=metadata))


def test_different_end_times_do_not_invent_stopping_distance(reference):
    metadata = {**reference.metadata, "summary": {**reference.metadata["summary"],
                "ticks": 3, "reason": "stopped", "stopping_distance_m": 1.2}}
    short = replace(reference, metadata=metadata, samples=reference.samples[:4], commands=reference.commands[:4])
    report = comparison_report(reference, short)
    assert report["common_seconds"] == .025
    assert report["reference_ticks"] != report["game_ticks"]
    assert report["metrics"][0]["delta"] is None
