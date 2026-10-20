"""结算夹具只检查导航/保存边界，真实课题驾驶由专项工具记录。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from race import GameMode
from session import Phase
from tire_tuning import previous_path
from vehicle_workspace import WorkspaceVehicle
from workshop_cornering import build_config


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, output=tmp_path/'game', workspace_vehicle=
        WorkspaceVehicle('reference-rwd', build_config(0, False, False)))
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.back_to_menu()
    game.choose_slalom_lesson(GameMode.FAST_SLALOM)
    yield game
    game.close_game()


def result_fixture(app, mode=GameMode.FAST_SLALOM, succeeded=False):
    app.slalom_mode = mode
    app.start_slalom_lesson()
    for _ in range(360):
        app.session.tick()
    highway = app.session.highway.snapshot
    stage = replace(highway.slalom, gates=6 if succeeded else 2, entry_kph=75., entry_time=5.,
        gate_times=(2., 4., 6., 8., 10., 11.4) if succeeded else (2., 4., 6.),
        clearances=(.5,)*6 if succeeded else (.5, .5, -.3), errors=(.2,)*6 if succeeded else (.2, .2, 1.2),
        run_seconds=11.4 if succeeded else 6., finished=True, succeeded=succeeded,
        medal='金' if succeeded else '', reason='金牌 · 连续通过全部6道门' if succeeded else '错过第3门；车身超出门线0.30m')
    app.session.highway.snapshot = replace(highway, finished=True, running=False, slalom=stage,
        succeeded=succeeded, reason=stage.reason)
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    return app.session.highway.snapshot


@pytest.mark.parametrize('succeeded', [False, True])
def test_cancel_and_same_recipe_preserve_exact_result_car_and_snapshot(app, succeeded):
    result = result_fixture(app, succeeded=succeeded)
    before, car = app.session.current, app.workspace_vehicle
    assert app.panel_option_count == 4 and app.buttons[3]['text'] == '改装前胎再试'
    app.buttons[3]['command']()
    assert not app.tire_tuning.root.isHidden() and app.panel.isHidden()
    assert all(column.isHidden() for column in app.result_sectors)
    app.key_down('enter')
    app.key_up('enter')
    assert app.tire_tuning.recipe == 0
    app.key_down('enter')
    app.key_up('enter')
    assert app.session.phase == Phase.RESULTS and app.session.highway.snapshot is result
    app.key_down('escape')
    app.key_up('escape')
    assert app.tire_tuning.root.isHidden() and app.main_menu.root.isHidden()
    assert app.panel_selection == 3 and app.session.highway.snapshot is result
    assert app.session.current == before and app.workspace_vehicle == car and not app.workspace_path.exists()


@pytest.mark.parametrize('mode', [GameMode.SLALOM_LESSON, GameMode.FAST_SLALOM])
def test_successful_install_prepares_same_course_with_new_hardware_without_old_result(app, mode):
    result_fixture(app, mode)
    app.driving_journey_return = mode == GameMode.SLALOM_LESSON
    input_mode = app.session.driving_mode
    app.open_tire_tuning()
    app.tire_tuning.activate(3)
    app.tire_tuning.activate(4)
    assert app.session.phase == Phase.MENU and app.slalom_mode == mode and app.slalom_menu
    assert app.session.vehicle_config.lateral_stiffness == 70000.
    assert app.session.driving_mode == input_mode
    assert app.driving_journey_return == (mode == GameMode.SLALOM_LESSON)
    assert app.session.highway.snapshot.slalom is None
    assert WorkspaceVehicle.load(app.workspace_path) == app.workspace_vehicle
    app.back_from_tire_tuning()
    app.buttons[0]['command']()
    assert app.session.mode == mode and app.session.simulation.config.lateral_stiffness == 70000.


def test_failed_write_keeps_result_and_preview(app, monkeypatch):
    result = result_fixture(app)
    before = app.session.current
    car = app.workspace_vehicle
    app.open_tire_tuning()
    app.tire_tuning.activate(3)

    def fail(self, path=None):
        raise OSError('测试只读')

    monkeypatch.setattr(WorkspaceVehicle, 'save', fail)
    app.tire_tuning.activate(4)
    assert app.session.phase == Phase.RESULTS and app.session.highway.snapshot is result
    assert app.workspace_vehicle == car and app.session.current == before
    assert app.tire_tuning.recipe == 3 and '未安装' in app.tire_tuning.notice.getText()


@pytest.mark.parametrize('missing', [False, True])
def test_restore_saved_original_from_result_and_failed_missing_backup(app, missing):
    app.open_tire_tuning()
    app.tire_tuning.activate(3)
    app.tire_tuning.activate(4)
    tuned = app.workspace_vehicle
    app.back_from_tire_tuning()
    result = result_fixture(app)
    old_bytes = app.workspace_path.read_bytes()
    if missing:
        previous_path(tuned, app.workspace_path).unlink()
    app.open_tire_tuning()
    app.tire_tuning.activate(5)
    if missing:
        assert app.session.phase == Phase.RESULTS and app.session.highway.snapshot is result
        assert app.workspace_vehicle == tuned and app.workspace_path.read_bytes() == old_bytes
        assert '未恢复' in app.tire_tuning.notice.getText()
        return
    assert app.session.phase == Phase.MENU and app.workspace_vehicle.config.lateral_stiffness == 35000.
    assert tuned != app.workspace_vehicle and app.slalom_mode == GameMode.FAST_SLALOM


def test_active_driving_cannot_open_tuning(app):
    app.start_slalom_lesson()
    app.open_tire_tuning()
    assert app.tire_tuning.root.isHidden()
