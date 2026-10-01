"""独立ESC选择的存储、重建和成绩分区。"""
import json
from itertools import product

import pytest

from driving_modes import DrivingMode
from session import Session
from settings import DrivingModeStore


def test_store_preserves_omitted_switches_and_validates_esc(tmp_path):
    path = tmp_path / "mode.json"
    store = DrivingModeStore(path)
    assert store.save(DrivingMode.SIMULATION, False, False, False)
    assert store.save(DrivingMode.GAME, abs_enabled=True)
    loaded = DrivingModeStore(path)
    assert (loaded.abs_enabled, loaded.tcs_enabled, loaded.esc_enabled) == (True, False, False)
    assert loaded.save(DrivingMode.GAME, tcs_enabled=True)
    assert not DrivingModeStore(path).esc_enabled
    path.write_text(json.dumps({"mode": "game", "esc_enabled": 0}), encoding="utf-8")
    invalid = DrivingModeStore(path)
    assert invalid.esc_enabled and "ESC" in invalid.notice
    with pytest.raises(TypeError):
        invalid.save(DrivingMode.GAME, esc_enabled=1)


def test_all_electronic_score_variants_are_independent():
    for mode in DrivingMode:
        variants = {mode.score_variant(*switches) for switches in product((False, True), repeat=3)}
        assert len(variants) == 8
        for switches in product((False, True), repeat=3):
            config = mode.configured_vehicle(*switches)
            assert (config.braking.abs_enabled, config.traction.tcs_enabled,
                    config.stability.esc_enabled) == switches


def test_session_preserves_esc_across_mode_toggle_restart_and_npcs():
    session = Session(esc_enabled=False)
    try:
        session.set_abs_enabled(False)
        session.set_tcs_enabled(False)
        session.set_driving_mode(DrivingMode.SIMULATION)
        assert not session.esc_enabled
        session.start(countdown=False)
        assert session.simulation.player.config is session.vehicle_config
        assert all(car.config is session.vehicle_config for car in session.simulation.npcs)
        assert not session.current.player.esc_enabled
        session.menu()
        session.set_esc_enabled(True)
        assert not session.abs_enabled and not session.tcs_enabled
        session.start(countdown=False)
        assert session.current.player.esc_enabled
        session.start(countdown=False)
        assert session.current.player.esc_enabled
    finally:
        session.close()
