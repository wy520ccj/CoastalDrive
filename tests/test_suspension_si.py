"""真实质量变化、原生硬件和JSON单位版本边界。"""

import json
from dataclasses import replace

import pytest
from physics.reference_ab import _create_vehicle
from physics.testbed import load_vehicle_config

from driving_modes import DrivingMode


@pytest.mark.parametrize("field,value", [
    ("suspension_spring_rates", (0.,) * 4),
    ("suspension_spring_rates", (48000.,) * 3),
    ("suspension_compression_damping", (float("nan"),) * 4),
    ("suspension_extension_damping", (-1.,) * 4),
])
def test_hardware_units_reject_invalid_configuration(field, value):
    with pytest.raises(ValueError):
        replace(DrivingMode.GAME.vehicle_config, **{field: value})


def test_four_independent_hardware_rates_reach_native_vehicle():
    config = replace(DrivingMode.GAME.vehicle_config, mass=1800., suspension_coupled_enabled=False,
                     suspension_spring_rates=(32000., 40000., 48000., 56000.),
                     suspension_compression_damping=(3000., 4000., 5000., 6000.),
                     suspension_extension_damping=(0., 1000., 2000., 3000.))
    _world, car = _create_vehicle(config)
    try:
        for i, wheel in enumerate(car._vehicle.getWheels()):
            assert wheel.getSuspensionStiffness() * car._chassis.getMass() == pytest.approx(config.suspension_spring_rates[i], rel=1e-7)
            assert wheel.getWheelsDampingCompression() * car._chassis.getMass() == pytest.approx(config.suspension_compression_damping[i], rel=1e-7)
            assert wheel.getWheelsDampingRelaxation() * car._chassis.getMass() == pytest.approx(config.suspension_extension_damping[i], rel=1e-7)
    finally:
        car.close()


def test_json_suspension_unit_version_boundary(tmp_path):
    path = tmp_path / "hardware.json"
    path.write_text(json.dumps({"mass": 1800, "suspension_stiffness": 30}), encoding="utf-8")
    legacy = load_vehicle_config(path, DrivingMode.GAME.vehicle_config)
    assert not legacy.suspension_si_enabled and legacy.suspension_stiffness == 30
    path.write_text(json.dumps({"suspension_spring_rates": [32000, 40000, 48000, 56000]}), encoding="utf-8")
    si = load_vehicle_config(path, legacy)
    assert si.suspension_si_enabled
    assert si.suspension_spring_rates == (32000, 40000, 48000, 56000)
