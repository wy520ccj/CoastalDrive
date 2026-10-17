"""工程车辆跨工作方式及磁盘保存，不从显示车型重建硬件。"""

from dataclasses import replace

import pytest

from driving_modes import DrivingMode
from session import Session
from vehicle_designs import REFERENCE_DESIGN
from vehicle_workspace import WorkspaceVehicle


def test_full_design_survives_game_and_saved_roundtrip(tmp_path):
    config = replace(REFERENCE_DESIGN, mass=1432., center_of_mass_height=.42,
                     tire_reference_load=3500., final_drive=4.3, tire_substeps=2)
    vehicle = WorkspaceVehicle("reference-rwd", config, {"basis": "本次工程试验"}, "report.html")
    session = Session(track="test", vehicle_config=config, driving_mode=DrivingMode.GAME,
                      abs_enabled=False, tcs_enabled=False, esc_enabled=True)
    try:
        assert session.simulation.config == replace(config, tire_substeps=1,
            braking=replace(config.braking, abs_enabled=False), traction=replace(config.traction, tcs_enabled=False),
            stability=replace(config.stability, esc_enabled=True))
        actual = vehicle.with_electronics(session.vehicle_config)
        path = tmp_path/"workspace"/"vehicle.json"
        actual.save(path)
        restored = WorkspaceVehicle.load(path)
        assert restored == actual
        assert restored.config.tire_substeps == 2
        assert restored.config.mass == 1432 and restored.parameter_metadata == vehicle.parameter_metadata
    finally:
        session.stop_clock()
        session.simulation.close()


def test_missing_workspace_is_new_session_but_broken_file_is_reported(tmp_path):
    path = tmp_path/"vehicle.json"
    assert WorkspaceVehicle.load(path) is None
    path.write_text("bad json", encoding="utf-8")
    with pytest.raises(ValueError):
        WorkspaceVehicle.load(path)
    path.write_text('{"schema":"other"}', encoding="utf-8")
    with pytest.raises(ValueError, match="格式"):
        WorkspaceVehicle.load(path)


def test_save_failure_preserves_existing_file(tmp_path):
    path = tmp_path/"vehicle.json"
    vehicle = WorkspaceVehicle("reference-rwd", REFERENCE_DESIGN)
    vehicle.save(path)
    original = path.read_bytes()
    invalid = replace(vehicle, parameter_metadata={"invalid": float("nan")})
    with pytest.raises(ValueError):
        invalid.save(path)
    assert path.read_bytes() == original
