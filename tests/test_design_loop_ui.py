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
    app.engine.taskMgr.remove("lab-update")
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


def test_completed_export_failure_retries_without_new_physics_and_survives_reopen(workbench, monkeypatch):
    import lab_game_comparison
    from lab_records import load_record

    app = workbench
    completed_trial(app)
    app.design_loop.show()
    panel = app.design_loop
    reference, baseline, vehicle = panel.record, app.baseline, app.workspace_vehicle
    panel.start_comparison()
    run = panel.comparison.run

    def fail(*args, **kwargs):
        raise OSError('文件暂不可写')

    with monkeypatch.context() as blocked:
        blocked.setattr(lab_game_comparison, 'export_record', fail)
        while panel.comparison is not None:
            panel.update()
    assert run.closed and panel.completed_records is not None and panel.report_path is None
    completed = panel.completed_records
    assert panel.retry_button['state'] == 'normal'
    panel.hide()
    panel.show()
    assert panel.completed_records is completed and panel.retry_button['state'] == 'normal'

    def no_recalculation(*args, **kwargs):
        pytest.fail('重试导出不应新建物理试验')

    monkeypatch.setattr(lab_game_comparison.GameComparison, '__init__', no_recalculation)
    panel.retry_button['command']()
    assert panel.report_path.is_file() and panel.report_button['state'] == 'normal'
    assert panel.retry_button['state'] == 'disabled' and app.notice.root.isHidden()
    assert '已导出' in app.notice.getText() and '失败' not in app.notice.getText()
    saved = load_record(panel.report_path.parent/'game')
    assert saved.snapshots == completed[1].snapshots and saved.commands == completed[1].commands
    path = panel.report_path
    panel.update()
    panel.hide()
    panel.show()
    assert panel.report_path == path and panel.completed_records is completed
    assert app.active_record() is reference and app.baseline is baseline and app.workspace_vehicle is vehicle


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


def test_return_restores_maneuver_drafts_ab_and_cursor(workbench, tmp_path):
    app = workbench
    app.baseline = completed_trial(app)
    options = LabOptions(vehicle_id="reference-awd", maneuver="step_steer", speed_kph=42.5,
                         duration=.1, onset=.025, steering_deg=2.4, cg_height=.43,
                         tire_reference_load=3456.)
    app.set_options(options)
    app.start_experiment()
    while not app.run_state.done:
        app.run_state.step()
    expected = LabRecord.from_run(app.run_state)
    app.entries["cg"].enterText(".49")
    app.entries["right_mu"].enterText("保留无效草稿")
    app.set_plot_group("附着利用率")
    app.show_sample(5)
    app.scene.camera_mode, app.play_speed = 1, .5
    state = app.capture_workspace()
    baseline = app.baseline
    app.close_game()
    restored = VehicleLab(offscreen=True, output=tmp_path/"restored", lab_workspace=state)
    restored.engine.taskMgr.remove("lab-update")
    try:
        assert restored.read_options().maneuver == "step_steer"
        assert restored.read_options().speed_kph == 42.5
        assert restored.read_options().duration == .1
        assert restored.entries["cg"].get() == ".49"
        assert restored.entries["right_mu"].get() == "保留无效草稿"
        assert restored.record.samples == expected.samples
        assert restored.record.metadata["vehicle_config"]["center_of_mass_height"] == .43
        assert restored.baseline is baseline and restored.plots[0].labels == ["A", "B"]
        assert restored.view_index == 5 and restored.timeline["value"] == pytest.approx(5/120)
        assert restored.scene.camera_mode == 1 and restored.play_speed == .5
        assert restored.run_state is None and not restored.playing
    finally:
        restored.close_game()


def test_restart_restores_applied_trial_parameters_and_baseline(workbench, monkeypatch, tmp_path):
    app = workbench
    app.baseline = completed_trial(app)
    options = LabOptions(maneuver="sine_steer", speed_kph=48., duration=.075, onset=.025,
                         steering_deg=2.5, cg_height=.41)
    app.set_options(options)
    app.start_experiment()
    while not app.run_state.done:
        app.run_state.step()
    app.design_loop.show()
    path = tmp_path/"vehicle.json"
    monkeypatch.setattr("vehicle_workspace.workspace_vehicle_path", lambda: path)
    monkeypatch.setattr(app, "userExit", lambda: None)
    app.design_loop.drive()
    vehicle = WorkspaceVehicle.load(path)
    expected = app.design_loop.record
    app.close_game()
    restored = VehicleLab(offscreen=True, output=tmp_path/"restart", workspace_vehicle=vehicle)
    restored.engine.taskMgr.remove("lab-update")
    try:
        assert restored.read_options() == options
        assert restored.record.samples == expected.samples
        assert restored.baseline is not None and restored.plots[0].labels == ["A", "B"]
    finally:
        restored.close_game()


def test_driving_and_pause_provide_direct_return_button(tmp_path, monkeypatch):
    from session import Phase

    app = CoastalDrive(smoke=True, output=tmp_path)
    app.taskMgr.remove("finish-smoke")
    monkeypatch.setattr(app, "userExit", lambda: None)
    try:
        app.refresh_panel()
        assert not app.lab_return_button.isHidden()
        assert app.lab_return_button["text"] == "返回实验台"
        app.session.phase = Phase.PAUSED
        app.refresh_panel()
        last_button = app.buttons[app.panel_option_count-1]
        assert last_button.getZ()+last_button["frameSize"][2] >= app.panel["frameSize"][2]
        index = [button["text"] for button in app.buttons[:app.panel_option_count]].index("专家试验台")
        app.buttons[index]["command"]()
        assert app.next_workspace == "lab"
        pending = app._workspace_steps
        app.lab_return_button["command"]()
        assert app.next_workspace == "lab" and app._workspace_steps is pending
    finally:
        app.close_game()
