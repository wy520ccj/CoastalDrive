"""真实实验场、路径驾驶员和按空间接点变化的对开附着。"""

import pytest

from lab_experiment import LabExperiment, LabOptions
from lab_maneuvers import lane_offset
from lab_records import LabRecord, recalculate


@pytest.mark.parametrize("mode,mean_limit,peak_limit", (("constant_radius", .5, 1.5),
                                                      ("double_lane_change", .3, .8)))
def test_closed_loop_tracks_reference_path_without_overwriting_physical_state(mode, mean_limit, peak_limit):
    run = LabExperiment(LabOptions(maneuver=mode, speed_kph=60, duration=12))
    try:
        assert run.experiment.simulation.track == "lab"
        assert run.experiment.simulation._world.getNumRigidBodies() == 2
        while not run.done:
            run.step()
        summary = run.summary()
        assert summary["reason"] == "time_limit" and summary["ticks"] == 1440
        assert summary["mean_path_error_m"] < mean_limit
        assert summary["maximum_path_error_m"] < peak_limit
        assert run.samples[-1]["speed"] == pytest.approx(60., abs=1.)
        assert summary["peak_lateral_acceleration_mps2"] > .5
        assert any(command.throttle > 0 for command in run.commands)
        assert all(contact.surface == "asphalt" for snapshot in run.snapshots[1:]
                   for contact in snapshot.player.wheel_contacts if contact.in_contact)
        if mode == "double_lane_change":
            assert max(state.player.position[0]-run.snapshots[0].player.position[0] for state in run.snapshots) > 3.
            assert abs(run.snapshots[-1].player.position[0]-run.snapshots[0].player.position[0]) < .4
    finally:
        run.close()


def test_split_grip_uses_actual_contact_coordinates_and_records_yaw_and_stop():
    run = LabExperiment(LabOptions(maneuver="split_braking"))
    try:
        boundary = run.snapshots[0].player.position[0]
        simulation = run.experiment.simulation
        assert simulation.on_asphalt(boundary-1, 0)
        assert not simulation.on_asphalt(boundary+1, 0)
        assert run.config.grass_rolling_coefficient == run.config.rolling_coefficient
        while not run.done:
            run.step()
        for snapshot in run.snapshots:
            for contact in snapshot.player.wheel_contacts:
                if contact.in_contact:
                    expected = "asphalt" if contact.contact_point[0] < boundary else "grass"
                    assert contact.surface == expected
        surfaces = {contact.surface for state in run.snapshots for contact in state.player.wheel_contacts}
        assert surfaces == {"asphalt", "grass"}
        assert run.reason == "stopped" and run.summary()["peak_yaw_rate_radps"] > .1
        assert run.summary()["stopping_distance_m"] > 0
        first = tuple(contact.surface for contact in run.snapshots[0].player.wheel_contacts)
        assert any(tuple(contact.surface for contact in state.player.wheel_contacts) != first
                   for state in run.snapshots[1:])
    finally:
        run.close()


def test_closed_loop_record_recalculates_saved_actuator_inputs_exactly():
    run = LabExperiment(LabOptions(maneuver="constant_radius", speed_kph=60, duration=.5))
    try:
        while not run.done:
            run.step()
        record = LabRecord.from_run(run)
    finally:
        run.close()
    actual = recalculate(record)
    assert actual.samples == record.samples
    assert actual.snapshots == record.snapshots


def test_reference_lane_change_geometry_is_continuous_and_returns_to_original_lane():
    assert lane_offset(0) == lane_offset(20) == lane_offset(100) == lane_offset(180) == 0
    assert lane_offset(50) == lane_offset(70) == 3.5
    assert lane_offset(35) == lane_offset(85) == 1.75
