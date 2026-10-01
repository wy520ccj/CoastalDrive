"""标准试验时序、A/B配置隔离与逐步证据契约。"""

import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from physics.tcs_probe import CASES, FIXED_DT, command_at, run_matrix, run_trial, trial_config


@pytest.mark.parametrize("case", CASES)
def test_pair_only_changes_tcs_switch(case):
    baseline = asdict(trial_config(case, False))
    enabled = asdict(trial_config(case, True))
    assert baseline["traction"].pop("tcs_enabled") is False
    assert enabled["traction"].pop("tcs_enabled") is True
    assert baseline == enabled


def test_lift_and_brake_boundaries_preserve_explicit_priority_request():
    assert command_at("lift-off", 2 - FIXED_DT)[1].throttle == 1
    phase, command = command_at("lift-off", 2)
    assert phase == "lift-off" and command.throttle == command.brake == 0
    phase, command = command_at("driver-brake", 2)
    assert phase == "driver-brake" and command.throttle == command.brake == 1
    assert command_at("reverse", 0)[1].direction == -1


@pytest.mark.parametrize("case", ["low-mu", "airborne-recontact"])
def test_every_tick_retains_force_request_and_completed_feedback(case):
    summary, rows = run_trial(case, True, .1)
    assert [row["tick"] for row in rows] == list(range(13))
    assert summary["ticks"] == 12
    for row in rows[1:]:
        for wheel in range(4):
            for field in ("drive_torque", "brake_torque", "normal_load", "fx", "fy", "omega", "kappa", "sample_tick", "force_contact_tick"):
                assert f"state.wheel_dynamics.{wheel}.{field}" in row
            assert f"state.traction_state.feedback_ticks.{wheel}" in row
            assert f"state.traction_state.brake_requests.{wheel}" in row
        assert "state.traction_state.torque_scale" in row
    if case == "airborne-recontact":
        assert rows[0]["state.position.2"] > 2
        assert all(seconds == pytest.approx(.1) for seconds in summary["airborne_wheel_seconds"])
        assert summary["recontact_counts"] == [0] * 4


@pytest.mark.parametrize("duration", [0, -.1, float("nan"), float("inf")])
def test_invalid_duration_rejected(duration):
    with pytest.raises(ValueError):
        run_trial("asphalt", False, duration)


def test_airborne_trial_falls_and_recontacts_without_runtime_reposition():
    summary, rows = run_trial("airborne-recontact", True, 1.0)
    assert rows[-1]["state.position.2"] < rows[0]["state.position.2"]
    assert all(seconds > 0 for seconds in summary["airborne_wheel_seconds"])
    assert all(count >= 1 for count in summary["recontact_counts"])
    assert all(rows[-1][f"state.wheel_dynamics.{wheel}.sample_support"] for wheel in range(4))


def test_matrix_preserves_dynamic_contact_fields_after_real_landing(tmp_path):
    output = tmp_path / "airborne"
    report = run_matrix(output, 1, ("airborne-recontact",))
    assert report["status"] == "completed"
    for label in ("A", "B"):
        with (output / f"airborne-recontact-{label}.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 121
        assert all(f"state.wheel_contacts.{wheel}.contact_point.2" in rows[-1] for wheel in range(4))
        assert all(rows[-1][f"state.wheel_contacts.{wheel}.contact_point.2"] for wheel in range(4))
        assert all(count >= 1 for count in report["cases"][0][label]["recontact_counts"])


def test_matrix_records_failure_and_unrun_trials(tmp_path):
    output = tmp_path / "failed"
    with pytest.raises(ValueError):
        run_matrix(output, 0, ("asphalt", "reverse"))
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["failed_trial"] == ["asphalt", "A"]
    assert report["not_run"] == [["asphalt", "B"], ["reverse", "A"], ["reverse", "B"]]
    assert report["source_sha256_after"] == report["source_sha256_before"]
