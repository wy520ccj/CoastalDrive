"""真实JSON边界与完整参数导出；临时目录不覆盖历史证据。"""

import json
from dataclasses import asdict, replace

import pytest
from physics.export_reference import export
from physics.reference_ab import _create_vehicle, _step
from physics.testbed import load_vehicle_config

from driving_modes import REFERENCE_CAR
from vehicle_brakes import BrakeConfig
from vehicle_stability import StabilityConfig
from vehicle_state import VehicleCommand
from vehicle_traction import TractionConfig


def write_config(tmp_path, values):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


@pytest.mark.parametrize("complete", [False, True])
def test_json_brakes_and_sequences_can_drive_real_vehicle(tmp_path, complete):
    selected = replace(REFERENCE_CAR, braking=BrakeConfig(response_time=.04, target_slip=.18))
    values = asdict(selected) if complete else {
        "braking": {"abs_enabled": True}, "traction": {"tcs_enabled": False}, "stability": {"esc_enabled": False}}
    values["braking"]["abs_enabled"] = True
    values.update(torque_curve=[[900, 100], [6500, 0]], gear_ratios=[3, 2, 1],
                  body_inertia=[1900, 510, 2290])
    config = load_vehicle_config(write_config(tmp_path, values), selected)
    assert isinstance(config.braking, BrakeConfig)
    assert config.braking.target_slip == .18
    assert config.braking.response_time == .04
    assert config.braking.abs_enabled
    assert isinstance(config.traction, TractionConfig)
    assert config.traction.tcs_enabled is complete
    assert isinstance(config.stability, StabilityConfig)
    assert config.stability.esc_enabled is complete
    assert isinstance(config.torque_curve, tuple)
    assert all(isinstance(node, tuple) for node in config.torque_curve)
    assert isinstance(config.gear_ratios, tuple)
    assert isinstance(config.body_inertia, tuple)
    assert isinstance(config.downstream_inertias, tuple)
    assert isinstance(config.downstream_axes, tuple)
    assert all(isinstance(axis, tuple) for axis in config.downstream_axes)
    world, vehicle = _create_vehicle(config)
    try:
        for _ in range(12):
            _step(world, vehicle, VehicleCommand(brake=.5, direction=1))
        assert all(0 < brake.pressure <= .5 for brake in vehicle.snapshot().brake_states)
    finally:
        vehicle.close()


def test_null_inertia_and_unknown_json_fields(tmp_path):
    config = load_vehicle_config(write_config(tmp_path, {"body_inertia": None}), REFERENCE_CAR)
    assert config.body_inertia is None
    for values in ({"unknown_vehicle": 1}, {"braking": {"unknown_brake": 1}},
                   {"traction": {"unknown_traction": 1}}, {"stability": {"unknown_stability": 1}}):
        with pytest.raises(TypeError):
            load_vehicle_config(write_config(tmp_path, values), REFERENCE_CAR)


def test_export_contains_complete_brake_metadata_and_source(tmp_path):
    path = tmp_path / "reference.json"
    export(path)
    report = json.loads(path.read_text(encoding="utf-8"))
    assert "src/shaft_transmission.py" in report["source_sha256"]
    assert "src/driveline_inertia.py" in report["source_sha256"]
    assert "src/tire_compliance.py" in report["source_sha256"]
    assert "src/tire_properties.py" in report["source_sha256"]
    assert "src/vehicle_stability.py" in report["source_sha256"]
    assert len(report["vehicle_fields"]) == 91
    assert len(report["stability_fields"]) == 10
    assert "src/vehicle_brakes.py" in report["source_sha256"]
    assert len(report["source_sha256"]["src/vehicle_brakes.py"]) == 64
    for mode in report["modes"].values():
        assert set(mode["vehicle_config"]) == set(report["vehicle_fields"])
        assert set(mode["vehicle_config"]["braking"]) == set(report["brake_fields"])
        assert set(mode["vehicle_config"]["traction"]) == set(report["traction_fields"])
        assert set(mode["vehicle_config"]["stability"]) == set(report["stability_fields"])
        assert mode["native_bullet"]["mass"] > 0
    assert all(unit and purpose for unit, purpose in report["brake_fields"].values())
    assert report["schema_version"] == "reference-v21"
    assert all(unit and purpose for unit, purpose in report["traction_fields"].values())
