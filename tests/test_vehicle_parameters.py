"""工程文件恢复不可变硬件，元数据不进入物理状态。"""

import json
from dataclasses import asdict, replace

import pytest
from physics.reference_ab import _create_vehicle, _step

from driving_modes import REFERENCE_CAR
from vehicle_parameters import SCHEMA, load_vehicle_config, save_vehicle_config
from vehicle_state import VehicleCommand


def test_grouped_file_round_trip_reaches_actual_vehicle_hardware(tmp_path):
    config = replace(REFERENCE_CAR, mass=1450., wheel_radius=.35, wheel_width=.225,
                     axle_track_widths=(1.52, 1.55),
                     front_drive_share=1., torque_curve=((900, 100), (6500, 0)),
                     braking=replace(REFERENCE_CAR.braking, target_slip=.18))
    path = tmp_path / "engineering.json"
    metadata = {"mass": {"unit": "kg", "kind": "design", "definition": "车身质量"}}
    save_vehicle_config(path, config, metadata=metadata)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["metadata"] == metadata
    assert document["parameters"]["tires"]["wheel_width"] == .225
    loaded = load_vehicle_config(path, REFERENCE_CAR)
    assert asdict(loaded) == asdict(config)
    world, car = _create_vehicle(loaded)
    try:
        assert car._chassis.getMass() == 1450.
        assert tuple(w.getWheelRadius() for w in car._vehicle.getWheels()) == pytest.approx((.35,) * 4)
        assert car.config.driven_wheels == (0, 1)
        for _ in range(12):
            _step(world, car, VehicleCommand(brake=.5, direction=1))
        assert all(0 < brake.pressure <= .5 for brake in car.snapshot().brake_states)
    finally:
        car.close()


def test_partial_engineering_file_inherits_hardware_and_nested_electronics(tmp_path):
    path = tmp_path / "partial.json"
    path.write_text(json.dumps({"schema": SCHEMA, "parameters": {
        "chassis": {"mass": 1350}, "electronics": {"braking": {"abs_enabled": False}}
    }}), encoding="utf-8")
    loaded = load_vehicle_config(path, REFERENCE_CAR)
    assert loaded.mass == 1350
    assert not loaded.braking.abs_enabled
    assert loaded.braking.target_slip == REFERENCE_CAR.braking.target_slip
    assert loaded.suspension_spring_rates == REFERENCE_CAR.suspension_spring_rates


@pytest.mark.parametrize("document", (
    {"schema": "unknown", "parameters": {}},
    {"schema": SCHEMA, "parameters": {"unknown": {}}},
    {"schema": SCHEMA, "parameters": {"tires": {"mass": 1200}}},
))
def test_engineering_file_rejects_unknown_version_and_misplaced_fields(tmp_path, document):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError):
        load_vehicle_config(path, REFERENCE_CAR)
