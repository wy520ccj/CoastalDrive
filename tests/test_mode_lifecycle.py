"""模式配置在物理世界重建、回收与成绩保存中贯通。"""

import pytest

from driver_assist import GAME_INPUT
from driving_modes import REFERENCE_CAR, DrivingMode
from race import BestTimes, GameMode, RaceTracker
from session import Phase, Session
from simulation import Simulation
from vehicle_config import CAR


def assert_config(sim, mode):
    assert sim.config is mode.vehicle_config
    assert sim.input_config is mode.input_config
    for car in (sim.player, *sim.npcs):
        assert car.config is mode.vehicle_config
        for component in (car.assist, car.powertrain, car.steering, car.tires):
            assert component.config is mode.vehicle_config
    assert sim.player.input_config is mode.input_config
    for car, driver in zip(sim.npcs, sim.drivers):
        assert car.input_config is driver.input_config is GAME_INPUT
        assert driver.config is mode.vehicle_config


def test_switch_mode_restart_track_and_pause_keep_selected_configuration(tmp_path):
    session = Session(scores=BestTimes(tmp_path / "scores.json"), track="test")
    try:
        original = session.simulation
        session.set_driving_mode(DrivingMode.SIMULATION)
        assert session.simulation is original
        session.start(countdown=False, track="highway")
        assert original.closed
        assert_config(session.simulation, DrivingMode.SIMULATION)
        with pytest.raises(ValueError, match="主菜单"):
            session.set_driving_mode(DrivingMode.GAME)
        session.keyboard.press("q")
        assert session.keyboard.direction == -1
        session.pause()
        session.resume()
        assert session.phase == Phase.DRIVING and session.keyboard.direction == -1
        session.start(countdown=False)
        assert session.keyboard.direction == 1
        assert_config(session.simulation, DrivingMode.SIMULATION)
        session.start(countdown=False, track="endless")
        assert_config(session.simulation, DrivingMode.SIMULATION)
        for driver in session.simulation.drivers:
            assert driver.recovery.config is REFERENCE_CAR
        session.menu()
        session.set_driving_mode(DrivingMode.GAME)
        session.start(countdown=False, track="test")
        assert_config(session.simulation, DrivingMode.GAME)
        assert session.simulation.config is CAR
    finally:
        session.close()


def test_stream_recycle_and_reset_preserve_reference_configuration():
    mode = DrivingMode.SIMULATION
    sim = Simulation(track="endless", traffic_count=2, config=mode.vehicle_config,
                     input_config=mode.input_config)
    try:
        car = sim.npcs[0]
        car.reset((0, 2000, .55))
        sim._update_stream()
        assert sim.traffic_cycles > 0
        assert car is sim.npcs[0]
        assert_config(sim, mode)
        assert sim.drivers[0].recovery.config is REFERENCE_CAR
        sim.reset(17)
        assert_config(sim, mode)
    finally:
        sim.close()


def test_normal_legacy_times_and_reference_times_are_separate(tmp_path):
    scores = BestTimes(tmp_path / "scores.json")
    tracker = RaceTracker(GameMode.TIME_TRIAL, scores=scores)
    legacy_id = tracker.circuit.score_id
    scores.record(GameMode.TIME_TRIAL, 100, legacy_id)
    tracker.start(GameMode.TIME_TRIAL, score_variant="reference-v1")
    assert tracker.score_id == legacy_id + ":reference-v1"
    assert tracker.snapshot.best_lap is None
    scores.record(GameMode.TIME_TRIAL, 120, tracker.score_id)
    tracker.start(GameMode.TIME_TRIAL)
    assert tracker.snapshot.best_lap == 100
    tracker.start(GameMode.TIME_TRIAL, score_variant="reference-v1")
    assert tracker.snapshot.best_lap == 120
