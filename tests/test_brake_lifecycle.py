"""电子配置与输入模式正交，世界重建/reset和成绩分区使用真实配置。"""

import pytest

from driving_modes import DrivingMode
from race import BestTimes, GameMode
from session import Session
from vehicle_state import VehicleCommand


def test_abs_choice_survives_mode_changes_and_reuses_world_on_restart(tmp_path):
    session = Session(track="test", scores=BestTimes(tmp_path / "scores.json"))
    try:
        original = session.simulation
        assert session.abs_enabled
        session.set_abs_enabled(False)
        session.set_driving_mode(DrivingMode.SIMULATION)
        assert session.simulation is original and not session.abs_enabled
        session.start(countdown=False)
        assert original.closed
        config = session.vehicle_config
        assert session.simulation.config is config
        assert not session.current.player.abs_enabled
        assert config.braking.response_time > 0
        world = session.simulation
        session.start(countdown=False)
        assert session.simulation is world
        with pytest.raises(ValueError, match="主菜单"):
            session.set_abs_enabled(True)
        session.menu()
        session.set_driving_mode(DrivingMode.GAME)
        assert not session.abs_enabled
        session.set_abs_enabled(True)
        session.start(countdown=False)
        assert session.current.player.abs_enabled
    finally:
        session.close()


def test_player_and_recycled_npc_reset_independent_brake_memory():
    session = Session(track="endless")
    try:
        sim = session.simulation
        for _ in range(30):
            sim.player.apply_command(VehicleCommand(brake=1))
            sim.npcs[0].apply_command(VehicleCommand(brake=.5))
        assert sim.player.brakes.states[0].pressure > 0
        assert sim.npcs[0].brakes.states[0].pressure > 0
        sim.player.reset((0, 0, .55))
        sim.npcs[0].reset((0, 2000, .55))
        sim._update_stream()
        assert sim.traffic_cycles > 0
        for car in (sim.player, sim.npcs[0]):
            assert car.brakes.config is sim.config.braking
            assert all(state.pressure == 0 and not state.abs_active and state.feedback_tick == 0
                       for state in car.brakes.states)
    finally:
        session.close()


def test_both_modes_and_abs_variants_isolate_previous_scores(tmp_path):
    scores = BestTimes(tmp_path / "scores.json")
    session = Session(track="test", scores=scores)
    try:
        legacy = session.race.circuit.score_id
        scores.record(GameMode.TIME_TRIAL, 80, legacy)
        scores.record(GameMode.TIME_TRIAL, 90, legacy + ":reference-v1")
        ids = []
        for mode in DrivingMode:
            for enabled in (False, True):
                session.menu()
                session.set_driving_mode(mode)
                session.set_abs_enabled(enabled)
                session.start(countdown=False, mode=GameMode.TIME_TRIAL, track="coastal")
                ids.append(session.race.score_id)
                assert session.race.snapshot.best_lap is None
                scores.record(GameMode.TIME_TRIAL, 100 + len(ids), ids[-1])
        assert len(set(ids)) == 4
        assert legacy not in ids and legacy + ":reference-v1" not in ids
    finally:
        session.close()
