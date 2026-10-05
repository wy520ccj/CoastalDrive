"""ESC工况时序、A/B隔离与真实落地完整压缩轨迹。"""

import csv
import gzip
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from panda3d.core import TransformState, Vec3
from physics.esc_probe import (
    CASES,
    FIXED_DT,
    MODES,
    command_at,
    run_matrix,
    run_trial,
    source_hashes,
    tire_contact_moments,
    trial_config,
)

from vehicle_state import WheelContactState, WheelDynamicsState


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("case", CASES)
def test_pair_changes_only_esc_switch(case, mode):
    a = asdict(trial_config(case, False, mode))
    b = asdict(trial_config(case, True, mode))
    assert a["stability"].pop("esc_enabled") is False
    assert b["stability"].pop("esc_enabled") is True
    assert a == b
    assert a["braking"]["abs_enabled"] and a["traction"]["tcs_enabled"]


def test_commands_switch_at_exact_interval_boundaries():
    before = command_at("corner-brake", 1.5-FIXED_DT)[1]
    after = command_at("corner-brake", 1.5)[1]
    assert (before.steering, before.throttle, before.brake) == (2, .15, 0)
    assert (after.steering, after.throttle, after.brake) == (2, 0, .7)
    assert command_at("steering-step", .5-FIXED_DT)[1].steering == 0
    assert command_at("steering-step", .5)[1].steering == 3
    assert command_at("steering-step", .5)[1].throttle == .3
    assert command_at("steering-saturation", .5-FIXED_DT)[1].steering == 0
    saturation = command_at("steering-saturation", .5)[1]
    assert saturation.steering == 12 and saturation.throttle == .3
    assert command_at("reverse", 0)[1].direction == -1
    coast = command_at("coast-disturbance", 4)[1]
    assert coast.throttle == coast.brake == coast.steering == 0


def test_completed_yaw_observation_and_all_tick_requests_retained():
    summary, rows = run_trial("coast-disturbance", True, .1)
    assert summary["ticks"] == 12
    assert [row["tick"] for row in rows] == list(range(13))
    assert rows[0]["completed_yaw_rate_radps"] == pytest.approx(.5)
    for row in rows[1:]:
        assert "completed_yaw_rate_radps" in row
        assert "state.stability_state.reference_yaw_rate" in row
        assert "state.stability_state.feedback_tick" in row
        for index in range(4):
            for field in ("fx", "fy", "omega", "normal_load", "kappa", "alpha", "sample_tick"):
                assert f"state.wheel_dynamics.{index}.{field}" in row
            assert f"state.brake_states.{index}.pressure" in row
            assert f"state.brake_states.{index}.requested" in row
            assert f"state.stability_state.brake_requests.{index}" in row
            assert row[f"tire_moment.{index}.force_contact_tick"] == row[f"state.wheel_dynamics.{index}.force_contact_tick"]
        assert row["mean_tire_contact_yaw_moment_nm"] == pytest.approx(sum(
            row[f"tire_moment.{index}.mean_total_contact_yaw_nm"] for index in range(4)))


def test_contact_moment_uses_real_tangent_lateral_and_cumulative_impulse():
    pose = TransformState.makePosHpr(Vec3(0, 0, 1), Vec3(45, 0, 0))
    orientation = pose.getQuat()
    point = pose.getPos()+orientation.xform(Vec3(-1, 1, -1))
    contact = WheelContactState(True, tuple(point), (0, 0, 1), 1000, 1000, .3, .1, None, "asphalt")
    wheel = WheelDynamicsState(fx=-1000, fy=100, force_contact_tick=7,
                              longitudinal_impulse=-800*FIXED_DT, lateral_impulse=200*FIXED_DT)
    values = tire_contact_moments(pose, (contact,), 7, (wheel,))[0]
    assert values["last_substep_fx_contact_yaw_nm"] == pytest.approx(1000, abs=.001)
    assert values["last_substep_fy_contact_yaw_nm"] == pytest.approx(-100, abs=.001)
    assert values["mean_total_contact_yaw_nm"] == pytest.approx(600, abs=.001)
    with pytest.raises(ValueError, match="tick"):
        tire_contact_moments(pose, (contact,), 8, (wheel,))


def test_stability_source_is_in_hash_account():
    assert "src/vehicle_stability.py" in source_hashes()
    assert "src/suspension.py" in source_hashes()
    assert "src/vehicle_suspension.py" in source_hashes()


def test_dynamic_contact_gzip_after_real_landing(tmp_path):
    output = tmp_path / "landing"
    report = run_matrix(output, 1, ("airborne-recontact",), ("simulation",))
    assert report["status"] == "completed"
    for label in ("A", "B"):
        with gzip.open(output / f"simulation-airborne-recontact-{label}.csv.gz", "rt", encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        assert len(rows) == 121
        assert float(rows[-1]["state.position.2"]) < float(rows[0]["state.position.2"])
        for index in range(4):
            supported = [row for row in rows if row.get(f"state.wheel_contacts.{index}.in_contact") == "True"]
            assert supported
            assert all(row[f"state.wheel_contacts.{index}.contact_point.2"] for row in supported)
            assert max(float(row[f"state.wheel_contacts.{index}.normal_load"]) for row in supported) > 0.
        assert all(n >= 1 for n in report["cases"][0][label]["recontact_counts"])
    with pytest.raises(FileExistsError):
        run_matrix(output, .1)


def test_failure_records_failed_and_unrun_trials(tmp_path):
    output = tmp_path / "failed"
    with pytest.raises(ValueError):
        run_matrix(output, 0, ("asphalt-brake", "reverse"), ("simulation",))
    report = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert report["failed_trial"] == ["simulation", "asphalt-brake", "A"]
    assert report["not_run"] == [["simulation", "asphalt-brake", "B"],
                                  ["simulation", "reverse", "A"], ["simulation", "reverse", "B"]]


@pytest.mark.parametrize("duration", [0, -.1, float("nan"), float("inf")])
def test_invalid_duration_rejected(duration):
    with pytest.raises(ValueError):
        run_trial("asphalt-brake", False, duration)
