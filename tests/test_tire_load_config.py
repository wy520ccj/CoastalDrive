"""轮荷指数通过既有车型配置、JSON和物理生命周期。"""
import json
from dataclasses import asdict

import pytest
from physics.testbed import load_vehicle_config

from driving_modes import DrivingMode
from session import Session
from settings import DrivingModeStore
from simulation import Simulation

FIELDS = ("tire_peak_load_exponent", "longitudinal_load_exponent", "lateral_load_exponent")


def exponents(config):
    return tuple(asdict(config)[name] for name in FIELDS)


@pytest.mark.parametrize("mode", list(DrivingMode))
def test_modes_preserve_load_exponents_through_electronics_and_saved_selection(tmp_path, mode):
    store = DrivingModeStore(tmp_path / "driving.json")
    assert store.save(mode, False, True, False)
    loaded = DrivingModeStore(store.path)
    config = loaded.mode.configured_vehicle(loaded.abs_enabled, loaded.tcs_enabled, loaded.esc_enabled)
    assert exponents(config) == (.90, .90, .85)
    assert exponents(config) == exponents(mode.vehicle_config)
    session = Session(driving_mode=loaded.mode, abs_enabled=False, esc_enabled=False)
    try:
        session.set_driving_mode(mode)
        session.start(countdown=False)
        assert exponents(session.vehicle_config) == (.90, .90, .85)
        assert session.simulation.player.config is session.vehicle_config
        assert all(car.config is session.vehicle_config for car in session.simulation.npcs)
        session.start(countdown=False)
        assert exponents(session.simulation.player.config) == (.90, .90, .85)
    finally:
        session.close()


@pytest.mark.parametrize("complete", [False, True])
def test_custom_load_exponents_json_and_reset_use_same_config(tmp_path, complete):
    selected = DrivingMode.SIMULATION.vehicle_config
    values = asdict(selected) if complete else {}
    expected = (.81, .92, .76)
    values.update(zip(FIELDS, expected))
    path = tmp_path / "vehicle.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    config = load_vehicle_config(path, selected)
    assert exponents(config) == expected
    assert exponents(load_vehicle_config(path, config)) == expected
    simulation = Simulation(0, config=config, traffic_count=1)
    try:
        assert simulation.player.config is config
        assert simulation.npcs[0].config is config
        simulation.player.reset((0, 0, .55))
        simulation.npcs[0].reset((0, 2000, .55))
        simulation.reset(1)
        assert simulation.player.config is config
        assert simulation.npcs[0].config is config
        assert exponents(simulation.player.config) == expected
        assert exponents(simulation.npcs[0].config) == expected
    finally:
        simulation.close()


def test_load_exponent_json_errors_remain_explicit(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_vehicle_config(path, DrivingMode.GAME.vehicle_config)
    path.write_text(json.dumps({"unknown_load_exponent": .9}), encoding="utf-8")
    with pytest.raises(TypeError):
        load_vehicle_config(path, DrivingMode.GAME.vehicle_config)
