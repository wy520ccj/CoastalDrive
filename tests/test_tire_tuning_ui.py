"""实际菜单/车辆交接与失败；不使用界面夹具制造驾驶成绩。"""

from dataclasses import asdict

import pytest

from application import CoastalDrive
from driving_modes import DrivingMode
from race import GameMode
from tire_tuning import previous_path
from vehicle_workspace import WorkspaceVehicle
from workshop_cornering import build_config


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    car = WorkspaceVehicle('reference-rwd', build_config(0, False, False))
    game = CoastalDrive(smoke=True, output=tmp_path/'game', lab_output=tmp_path/'reports', workspace_vehicle=car)
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.back_to_menu()
    game.choose_slalom_lesson(GameMode.FAST_SLALOM)
    yield game
    game.close_game()


def finish(app, workspace):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


def test_preview_cancel_and_keyboard_modal_preserve_current_car(app):
    before = app.workspace_vehicle
    app.select_panel_option(2)
    app.handle_panel_key('enter')
    panel = app.tire_tuning
    assert not panel.root.isHidden() and app.panel.isHidden()
    app.key_down('arrow_right')
    app.key_up('arrow_right')
    app.key_down('enter')
    app.key_up('enter')
    assert panel.recipe == 1 and '45k' in panel.preview.getText()
    assert app.workspace_vehicle == before and not app.workspace_path.exists()
    app.key_down('f2')
    app.key_up('f2')
    assert not app.driving_mode_page
    app.key_down('escape')
    app.key_up('escape')
    assert panel.root.isHidden() and app.slalom_mode == GameMode.FAST_SLALOM and app.panel_selection == 2
    assert not app.workspace_path.exists()


def test_install_keeps_input_and_other_hardware_then_actual_lab_receives_it(app):
    app.session.set_driving_mode(DrivingMode.SIMULATION)
    before = app.workspace_vehicle
    app.open_tire_tuning()
    app.tire_tuning.activate(3)
    assert app.workspace_vehicle == before
    app.tire_tuning.activate(4)
    after = app.workspace_vehicle
    assert after.config.lateral_stiffness == 70000. and app.session.driving_mode == DrivingMode.SIMULATION
    old, new = asdict(before.config), asdict(after.config)
    new['lateral_stiffness'] = old['lateral_stiffness']
    assert new == old and WorkspaceVehicle.load(app.workspace_path) == after
    assert previous_path(after, app.workspace_path).exists()
    app.tire_tuning.activate(6)
    app.buttons[0]['command']()
    assert app.session.mode == GameMode.FAST_SLALOM
    app.open_vehicle_lab()
    finish(app, 'lab')
    assert app.lab.engineered_config == after.config
    app.lab.entries['cg'].enterText('.47')
    app.lab.back_to_game()
    finish(app, 'game')
    assert app.session.mode == GameMode.FAST_SLALOM and app.session.driving_mode == DrivingMode.SIMULATION
    assert app.lab_workspace.fields['cg'] == '.47' and app.workspace_vehicle == after


def test_saved_original_restore_and_same_model_garage_keep_tuning(app):
    original = app.workspace_vehicle
    app.open_tire_tuning()
    app.tire_tuning.activate(3)
    app.tire_tuning.activate(4)
    tuned = app.workspace_vehicle
    app.back_from_tire_tuning()
    app.back_to_menu()
    app.choose_garage()
    app.apply_garage()
    assert app.workspace_vehicle == tuned
    app.choose_slalom_lesson()
    app.open_tire_tuning()
    app.tire_tuning.activate(5)
    assert app.workspace_vehicle == original and WorkspaceVehicle.load(app.workspace_path) == original
    assert app.slalom_mode == GameMode.SLALOM_LESSON


def test_install_and_restore_write_failures_keep_file_session_and_draft(app, monkeypatch):
    app.workspace_vehicle.save(app.workspace_path)
    before, old = app.workspace_vehicle, app.workspace_path.read_bytes()
    app.open_tire_tuning()
    app.tire_tuning.activate(3)

    def fail(self, path=None):
        raise OSError('测试只读')

    monkeypatch.setattr(WorkspaceVehicle, 'save', fail)
    app.tire_tuning.activate(4)
    assert app.workspace_vehicle == before and app.workspace_path.read_bytes() == old
    assert app.tire_tuning.recipe == 3 and '未安装' in app.tire_tuning.notice.getText()


def test_missing_backup_is_reported_and_current_car_kept(app):
    app.open_tire_tuning()
    app.tire_tuning.activate(3)
    app.tire_tuning.activate(4)
    tuned = app.workspace_vehicle
    original = app.workspace_path.read_bytes()
    previous_path(tuned, app.workspace_path).unlink()
    app.tire_tuning.activate(5)
    assert app.workspace_vehicle == tuned and app.workspace_path.read_bytes() == original
    assert '未恢复' in app.tire_tuning.notice.getText()


def test_previous_lab_draft_is_preserved_without_replacing_new_driving_car(app):
    app.start_slalom_lesson()
    app.open_vehicle_lab()
    finish(app, 'lab')
    old_config = app.lab.engineered_config
    app.lab.entries['cg'].enterText('.47')
    app.lab.back_to_game()
    finish(app, 'game')
    app.back_to_menu()
    app.choose_slalom_lesson(GameMode.FAST_SLALOM)
    app.open_tire_tuning()
    app.tire_tuning.activate(3)
    app.tire_tuning.activate(4)
    tuned = app.workspace_vehicle
    app.back_from_tire_tuning()
    app.start_slalom_lesson()
    app.open_vehicle_lab()
    finish(app, 'lab')
    assert app.lab.engineered_config == old_config and app.lab.entries['cg'].get() == '.47'
    assert app.lab.workspace_vehicle == tuned
    app.lab.back_to_game()
    finish(app, 'game')
    assert app.workspace_vehicle == tuned and app.session.vehicle_config.lateral_stiffness == 70000.
