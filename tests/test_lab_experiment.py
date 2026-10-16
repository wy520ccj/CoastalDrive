"""真实固定步制动、参数响应、暂停/单步与失败记录。"""

from dataclasses import replace

import pytest

from lab_experiment import LabExperiment, LabOptions
from lab_signals import sample_signals
from vehicle_state import FIXED_DT, VehicleCommand


def test_pause_single_step_and_lower_friction_produce_real_longer_stop():
    distances = []
    for friction in (1.1, .6):
        run = LabExperiment(LabOptions(friction=friction))
        try:
            initial = run.current
            assert max(brake.pressure for brake in initial.player.brake_states) < .001
            assert run.advance() == 0 and run.current == initial
            state = run.step()
            assert run.samples[1]["pressure_fl"] < run.samples[1]["brake_request"]
            assert state.tick == initial.tick+1
            assert state.time-initial.time == pytest.approx(FIXED_DT)
            assert run.paused
            while not run.done:
                run.step()
            summary = run.summary()
            assert summary["reason"] == "stopped"
            assert len(run.samples) == summary["ticks"]+1
            assert run.elapsed == pytest.approx(run.current.time-run.start_time)
            assert len(run.current.traffic) == 0 and summary["abs_ticks"] > 0
            assert all(row["tick"] == state.tick for row, state in zip(run.samples, run.snapshots))
            distances.append(summary["stopping_distance_m"])
            with pytest.raises(RuntimeError, match="结束"):
                run.step()
        finally:
            run.close()
    assert distances[1] > distances[0]*1.3


def test_exact_commands_and_step_steer_have_mechanical_response():
    run = LabExperiment(LabOptions(maneuver="step_steer", speed_kph=40, duration=1., onset=.2))
    try:
        assert run.command_at(.1).steering == 0
        assert run.command_at(.2).steering == 3.
        while not run.done:
            run.step()
        assert run.reason == "time_limit" and len(run.samples) == 121
        assert max(abs(row["yaw"]) for row in run.samples) > .02
        requested = next(row for row in run.samples if row["steering_request"] == 3.)
        assert requested["steering"] != requested["steering_request"]
    finally:
        run.close()


def test_abs_off_and_manual_requests_are_independent_of_keyboard_assist():
    run = LabExperiment(LabOptions(maneuver="manual", speed_kph=40, duration=.1, abs_enabled=False))
    try:
        run.manual_command = VehicleCommand(brake=.8, gear=0, clutch=0, steering=1.)
        run.paused = False
        while not run.done:
            run.advance(.001)
        assert run.summary()["abs_ticks"] == 0
        assert run.commands[-1] == run.manual_command
        assert all(row["brake_request"] == .8 for row in run.samples[1:])
    finally:
        run.close()


def test_missing_wheel_slip_remains_undefined_and_failure_keeps_completed_steps(monkeypatch):
    run = LabExperiment(LabOptions(duration=.1))
    try:
        state = run.current.player
        wheel = replace(state.wheel_dynamics[0], kappa=None, sample_support=False)
        snapshot = replace(run.current, player=replace(state, wheel_dynamics=(wheel, *state.wheel_dynamics[1:])))
        assert sample_signals(snapshot, VehicleCommand(), run.start_time)["kappa_fl"] is None

        def fail(command):
            raise ArithmeticError("求解残差未收敛")

        monkeypatch.setattr(run.experiment.simulation, "step", fail)
        with pytest.raises(ArithmeticError, match="残差"):
            run.step()
        assert run.reason == "failed" and run.paused and len(run.samples) == 1
        assert run.summary()["error"] == "求解残差未收敛"
    finally:
        run.close()


@pytest.mark.parametrize("kwargs", ({"speed_kph": float("nan")}, {"friction": 0},
                                   {"duration": 100}, {"steering_deg": 100}))
def test_user_configuration_boundary_rejects_invalid_values(kwargs):
    with pytest.raises(ValueError):
        LabOptions(**kwargs)


def test_steering_limit_uses_imported_hardware_instead_of_catalog_default():
    from lab_inputs import LabInputError
    from vehicle_designs import vehicle_design

    config = vehicle_design("reference-rwd").config
    options = LabOptions(maneuver="step_steer", steering_deg=30., onset=0., duration=FIXED_DT)
    with pytest.raises(LabInputError, match="当前模型"):
        LabExperiment(options, config=replace(config, steering_degrees=20.))
    run = LabExperiment(options, config=replace(config, steering_degrees=40.))
    try:
        assert run.command_at(0.).steering == 30.
        run.step()
        assert run.commands[-1].steering == 30.
    finally:
        run.close()
