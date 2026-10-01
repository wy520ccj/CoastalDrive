"""胎体弹性配置通过JSON与既有车型生命周期。"""
import json
from dataclasses import asdict, replace

import pytest
from physics.testbed import load_vehicle_config

from driving_modes import DrivingMode
from simulation import Simulation

FIELDS = ("tire_compliance", "tire_contact_stiffness", "tire_contact_damping")


def compliance_values(config):
    return tuple(asdict(config)[name] for name in FIELDS)


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("complete", [False, True])
def test_compliance_json_preserves_explicit_selection_and_reset(tmp_path, mode, enabled, complete):
    selected = mode.configured_vehicle(False, True, False)
    values = asdict(selected) if complete else {}
    expected = (enabled, 130000.0, 850.0)
    values.update(zip(FIELDS, expected))
    path = tmp_path / "vehicle.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    config = load_vehicle_config(path, selected)
    assert compliance_values(config) == expected
    assert type(config.tire_compliance) is bool
    assert compliance_values(load_vehicle_config(path, config)) == expected
    assert config.braking.abs_enabled is False
    assert config.traction.tcs_enabled is True
    assert config.stability.esc_enabled is False
    simulation = Simulation(0, config=config, traffic_count=1, input_config=mode.input_config)
    try:
        assert simulation.player.config is config
        assert simulation.npcs[0].config is config
        simulation.player.reset((0, 0, .55))
        simulation.npcs[0].reset((0, 2000, .55))
        assert compliance_values(simulation.player.config) == expected
        assert compliance_values(simulation.npcs[0].config) == expected
        simulation.reset(1)
        assert simulation.player.config is config
        assert simulation.npcs[0].config is config
        assert compliance_values(simulation.player.config) == expected
        assert compliance_values(simulation.npcs[0].config) == expected
    finally:
        simulation.close()


@pytest.mark.parametrize("mode", list(DrivingMode))
def test_mode_electronics_preserve_compliance_hardware(mode):
    config = mode.configured_vehicle(False, False, False)
    assert compliance_values(config) == compliance_values(mode.vehicle_config)
    explicit = replace(config, tire_compliance=True)
    assert explicit.tire_compliance
    assert explicit.tire_contact_stiffness == 150000.0
    assert explicit.tire_contact_damping == 1000.0
