"""TCS设置跨模式、重开、玩家/NPC配置与成绩键的生命周期。"""

import json

import pytest

from driving_modes import DrivingMode
from race import BestTimes
from session import Session
from settings import DrivingModeStore
from vehicle_state import FIXED_DT, WheelDynamicsState


def test_tcs_choice_persists_and_rebuilds_player_and_traffic_from_same_config(tmp_path):
    settings_path = tmp_path / "driving-mode.json"
    store = DrivingModeStore(settings_path)
    session = Session(track="endless", scores=BestTimes(tmp_path / "scores.json"))
    try:
        initial_world = session.simulation
        assert session.tcs_enabled
        session.set_tcs_enabled(False)
        session.set_driving_mode(DrivingMode.SIMULATION)
        assert session.simulation is initial_world
        assert not session.tcs_enabled and session.abs_enabled
        assert store.save(session.driving_mode, session.abs_enabled, session.tcs_enabled)
        restored = DrivingModeStore(settings_path)
        assert restored.mode is DrivingMode.SIMULATION
        assert restored.abs_enabled and not restored.tcs_enabled

        session.start(countdown=False)
        assert initial_world.closed
        assert session.simulation.config is session.vehicle_config
        assert session.simulation.player.config is session.vehicle_config
        assert all(car.config is session.vehicle_config for car in session.simulation.npcs)
        assert not session.current.player.tcs_enabled
        with pytest.raises(ValueError, match="主菜单"):
            session.set_tcs_enabled(True)

        running_world = session.simulation
        session.menu()
        session.set_tcs_enabled(True)
        session.start(countdown=False)
        assert session.simulation is not running_world
        assert running_world.closed
        assert session.current.player.tcs_enabled
        assert session.current.player.traction_state.torque_scale == 1.0
        rebuilt_world = session.simulation
        session.menu()
        session.start(countdown=False)
        assert session.simulation is rebuilt_world
    finally:
        session.close()


def test_player_reset_and_npc_recycle_clear_tcs_controller_memory():
    session = Session(track="endless")
    try:
        simulation = session.simulation
        feedback = tuple(WheelDynamicsState(
            omega=10 * 1.6 / car.config.wheel_radius,
            longitudinal_speed=10,
            sample_support=True,
            sample_tick=1,
        ) for car in (simulation.player, simulation.npcs[0]) for _ in range(4))
        simulation.player.traction.advance(1, 1, False, feedback[:4],
                                           simulation.player.config.wheel_radius, FIXED_DT)
        assert simulation.player.traction.state.active
        simulation.player.reset((0, 0, .55))
        assert not simulation.player.traction.state.active
        assert simulation.player.traction.state.torque_scale == 1.0

        npc = simulation.npcs[0]
        npc.reset((0, 5000, .55))
        npc.traction.advance(1, 1, False, feedback[4:], npc.config.wheel_radius, FIXED_DT)
        assert npc.traction.state.active
        simulation._update_stream()
        assert simulation.traffic_cycles > 0
        assert not npc.traction.state.active
        assert npc.traction.state.torque_scale == 1.0
    finally:
        session.close()


def test_mode_abs_tcs_variants_get_distinct_score_keys():
    keys = {
        (mode, abs_enabled, tcs_enabled): mode.score_variant(abs_enabled, tcs_enabled)
        for mode in DrivingMode
        for abs_enabled in (False, True)
        for tcs_enabled in (False, True)
    }
    assert len(set(keys.values())) == 8
    assert all(":abs-" in value and ":tcs-" in value for value in keys.values())
    assert DrivingMode.GAME.score_variant(True).startswith("game-controls-v19:")
    assert DrivingMode.SIMULATION.score_variant(True).startswith("reference-v22:")


def test_store_reads_old_abs_only_file_and_reports_invalid_tcs(tmp_path):
    path = tmp_path / "driving-mode.json"
    path.write_text(json.dumps({"mode": "game", "abs_enabled": False}), encoding="utf-8")
    restored = DrivingModeStore(path)
    assert not restored.abs_enabled and restored.tcs_enabled and not restored.notice
    path.write_text(json.dumps({"mode": "game", "abs_enabled": True, "tcs_enabled": 1}), encoding="utf-8")
    restored = DrivingModeStore(path)
    assert restored.tcs_enabled and "TCS" in restored.notice
