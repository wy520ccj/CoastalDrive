"""真实实验室控件与游戏窗口：试验配置应用、保存失败和车型切换。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from lab_application import VehicleLab
from lab_experiment import LabOptions
from lab_records import LabRecord
from vehicle_designs import REFERENCE_DESIGN
from vehicle_workspace import WorkspaceVehicle


@pytest.fixture
def workbench(tmp_path_factory):
    app = VehicleLab(offscreen=True, output=tmp_path_factory.mktemp("design-ui"))
    app.taskMgr.remove("lab-update")
    yield app
    app.close_game()


def completed_trial(app):
    app.set_options(LabOptions(speed_kph=15, duration=.025, cg_height=.42))
    app.start_experiment()
    while not app.run_state.done:
        app.run_state.step()
    return LabRecord.from_run(app.run_state)


def test_apply_uses_completed_trial_instead_of_unrun_fields(workbench, monkeypatch, tmp_path):
    app = workbench
    record = completed_trial(app)
    app.entries["cg"].enterText(".9")
    app.design_loop.show()
    assert app.design_loop.record.samples == record.samples
    path = tmp_path/"saved.json"
    monkeypatch.setattr("vehicle_workspace.workspace_vehicle_path", lambda: path)
    monkeypatch.setattr(app, "userExit", lambda: None)
    app.design_loop.drive()
    assert app.next_workspace == "game" and app.next_drive
    assert app.workspace_vehicle.config.center_of_mass_height == .42
    assert WorkspaceVehicle.load(path) == app.workspace_vehicle
    assert app.workspace_vehicle.report_path.endswith("report.html")
    app.design_loop.hide()


def test_save_failure_keeps_lab_and_current_vehicle(workbench, monkeypatch, tmp_path):
    app = workbench
    completed_trial(app)
    app.design_loop.show()
    previous = app.workspace_vehicle
    app.next_workspace, app.next_drive = None, False
    blocked = tmp_path/"blocked"
    blocked.write_text("file", encoding="utf-8")
    monkeypatch.setattr("vehicle_workspace.workspace_vehicle_path", lambda: blocked/"vehicle.json")
    app.design_loop.drive()
    assert app.workspace_vehicle is previous and app.next_workspace is None and not app.next_drive
    assert not app.notice.root.isHidden()
    app.notice.dismiss()
    app.design_loop.hide()


def test_comparison_releases_reference_world_and_close_cancels(workbench):
    app = workbench
    completed_trial(app)
    app.design_loop.show()
    original = app.run_state
    app.design_loop.start_comparison()
    assert original.closed and app.run_state is None
    comparison = app.design_loop.comparison
    app.design_loop.update()
    assert comparison.command_index > 1
    app.design_loop.hide()
    assert comparison.run.closed and app.design_loop.comparison is None
    assert app.record.metadata["summary"]["reason"] == "time_limit"


def test_applied_vehicle_reaches_game_world_and_same_model_garage_keeps_it(tmp_path):
    config = replace(REFERENCE_DESIGN, mass=1440., center_of_mass_height=.41, tire_substeps=2)
    vehicle = WorkspaceVehicle("reference-rwd", config, report_path="reference/report.html")
    app = CoastalDrive(smoke=True, output=tmp_path, workspace_vehicle=vehicle)
    app.taskMgr.remove("finish-smoke")
    try:
        assert app.vehicle_model_id == "reference-rwd"
        assert app.session.simulation.config == replace(config, tire_substeps=1)
        app.session.menu()
        app.toggle_tcs()
        assert WorkspaceVehicle.load(app.workspace_path).config.traction.tcs_enabled == app.session.tcs_enabled
        app.choose_garage()
        app.apply_garage()
        assert app.session.base_vehicle_config == app.workspace_vehicle.config
        assert app.workspace_vehicle.config.mass == config.mass
        app.choose_garage()
        app.cycle_garage_model()
        app.apply_garage()
        assert app.workspace_vehicle.design_id == "reference-fwd"
        assert app.workspace_vehicle.report_path is None
        assert WorkspaceVehicle.load(app.workspace_path).design_id == "reference-fwd"
    finally:
        app.close_game()
