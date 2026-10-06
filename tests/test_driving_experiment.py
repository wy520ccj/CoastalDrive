"""20Hz直接请求、120Hz逐拍采样、生命周期和实际记录重放。"""

from dataclasses import replace

import pytest
from physics.experiment import record, replay

from driving_experiment import DrivingExperiment, ExperimentOptions, observation_digest
from driving_modes import DrivingMode
from sensor_sampling import SensorConfig
from vehicle_parameters import save_vehicle_config
from vehicle_state import VehicleCommand


def test_control_request_advances_exactly_six_ticks_and_sensor_frames_and_reset_repeats():
    experiment = DrivingExperiment(sensors=SensorConfig(), options=ExperimentOptions(seed=17))
    try:
        initial = experiment.current.snapshot
        command = VehicleCommand(throttle=.5, direction=1, steering=2.)
        result = experiment.step(command)
        assert result.snapshot.tick == initial.tick + 6
        assert tuple(state.estimate.tick for state in result.sensing) == tuple(range(1, 7))
        digest = observation_digest(result)
        assert experiment.reset().snapshot == initial
        assert observation_digest(experiment.step(command)) == digest
    finally:
        experiment.close()


def test_direct_commands_share_hardware_in_both_input_modes_and_timeout_is_explicit():
    game = DrivingExperiment(mode=DrivingMode.GAME, options=ExperimentOptions(maximum_control_steps=2))
    simulation = DrivingExperiment(mode=DrivingMode.SIMULATION, options=ExperimentOptions(maximum_control_steps=2))
    try:
        command = VehicleCommand(throttle=.6, gear=1, steering=2.)
        for _ in range(2):
            actual, expected = game.step(command), simulation.step(command)
            assert observation_digest(actual) == observation_digest(expected)
        assert not actual.terminated and actual.truncated and actual.reason == "time_limit"
        assert actual.snapshot.tick == 12
        with pytest.raises(RuntimeError, match="reset"):
            game.step(command)
    finally:
        game.close()
        simulation.close()


def test_native_collision_is_terminal_and_keeps_impacts_across_all_six_ticks():
    options = ExperimentOptions(initial_position=(95., 716.8, .55), initial_speed=20.)
    experiment = DrivingExperiment(options=options)
    try:
        initial = experiment.current.snapshot
        assert initial.player.speed == pytest.approx(20.)
        result = experiment.step(VehicleCommand(clutch=0., gear=0))
        assert result.snapshot.tick == 6
        assert result.terminated and result.reason == "collision"
        assert result.snapshot.collisions > initial.collisions
        assert "player_collision" in result.events
        assert result.impacts
    finally:
        experiment.close()


def test_record_replay_compares_full_physics_and_noisy_estimate_and_parameter_ab(tmp_path):
    commands = [VehicleCommand(throttle=.8, gear=1, steering=1.)] * 8
    baseline = record(commands, tmp_path / "baseline", sensors=SensorConfig(), options=ExperimentOptions(seed=23))
    replayed = replay(tmp_path / "baseline/experiment.json", tmp_path / "replay")
    assert replayed["full_observation_exact"] and replayed["actual_control_steps"] == 8
    assert baseline["steps"][-1]["observation"]["snapshot"]["tick"] == 48
    experiment = DrivingExperiment()
    try:
        candidate = replace(experiment.vehicle_config, mass=1500.)
    finally:
        experiment.close()
    save_vehicle_config(tmp_path / "candidate.json", candidate)
    compared = replay(tmp_path / "baseline/experiment.json", tmp_path / "ab", tmp_path / "candidate.json")
    assert compared["kind"] == "same_commands_parameter_ab"
    assert compared["changed_vehicle_fields"] == {"mass": {"baseline": 1200., "candidate": 1500.}}
    assert compared["candidate_final"]["snapshot"]["player"]["speed"] != compared["baseline_final"]["snapshot"]["player"]["speed"]
