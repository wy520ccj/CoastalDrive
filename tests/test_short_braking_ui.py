"""新题与配方的实际菜单/同窗交接；成绩夹具只用于显示验证。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from race import GameMode
from session import Phase
from vehicle_workspace import WorkspaceVehicle
from workshop import build_config


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, output=tmp_path/'game', lab_output=tmp_path/'reports', workspace_vehicle=
        WorkspaceVehicle('reference-rwd', build_config(0, False)))
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.back_to_menu()
    game.choose_braking_lesson()
    yield game
    game.close_game()


def finish(app, workspace):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


def test_rules_toggle_and_preview_install_preserve_other_hardware_and_course(app):
    assert '170米' in app.panel_note.getText() and app.panel_option_count == 4
    app.buttons[1]['command']()
    assert app.braking_mode == GameMode.SHORT_BRAKING and '80–85' in app.panel_note.getText()
    original = app.workspace_vehicle
    app.buttons[2]['command']()
    assert app.tire_tuning.topic == 'brakes' and not app.tire_tuning.buttons[7].isHidden()
    app.tire_tuning.activate(2)
    assert app.workspace_vehicle == original and '70%' in app.tire_tuning.preview.getText()
    app.tire_tuning.activate(4)
    assert app.workspace_vehicle.config.front_brake_share == .7
    assert app.workspace_vehicle.config.brake_torque == original.config.brake_torque
    app.back_from_tire_tuning()
    app.buttons[0]['command']()
    for _ in range(360):
        app.session.tick()
    assert app.session.mode == GameMode.SHORT_BRAKING and app.session.highway.snapshot.braking.short
    app.apply_scene(app.session.current, 0.)
    assert app.scene.braking_markers.standard.isHidden() and not app.scene.braking_markers.short.isHidden()


def test_same_window_lab_return_keeps_short_course_and_new_hardware(app):
    app.choose_braking_lesson(GameMode.SHORT_BRAKING)
    app.open_brake_tuning()
    app.tire_tuning.activate(2)
    app.tire_tuning.activate(4)
    app.back_from_tire_tuning()
    app.start_braking_lesson()
    window, config = app.win, app.workspace_vehicle.config
    app.open_vehicle_lab()
    finish(app, 'lab')
    assert app.lab.engineered_config == config
    app.lab.back_to_game()
    finish(app, 'game')
    assert app.win is window and app.session.mode == GameMode.SHORT_BRAKING
    assert app.session.vehicle_config.front_brake_share == .7


@pytest.mark.parametrize('save_notice', ['', '本次成绩未保存；请检查存储目录，可继续练习。'])
def test_result_fixture_brake_tuning_preserves_result_on_cancel_and_prepares_same_course(app, save_notice):
    app.choose_braking_lesson(GameMode.SHORT_BRAKING)
    app.start_braking_lesson()
    for _ in range(360):
        app.session.tick()
    state = app.session.highway.snapshot
    result = replace(state.braking, finished=True, succeeded=True, entry_kph=83.9, stopping_m=37.,
                     medal='铜', reason='铜牌 · 已停稳1秒', best_distance=37., save_notice=save_notice)
    app.session.highway.snapshot = replace(state, braking=result, finished=True, succeeded=True, reason=result.reason)
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    assert '37.00m' in app.panel_detail.getText() and app.buttons[3]['text'] == '调整制动分配'
    lower = app.panel['frameSize'][2]
    for button in app.buttons[:4]:
        assert button.getZ()+button['frameSize'][2] >= lower+.04
    assert app.panel_detail.getTightBounds(app.panel)[0].z > app.buttons[0].getZ()+.06+.03
    before = app.session.highway.snapshot
    app.buttons[3]['command']()
    app.back_from_tire_tuning()
    assert app.session.highway.snapshot is before
    app.open_brake_tuning()
    app.tire_tuning.activate(2)
    app.tire_tuning.activate(4)
    assert app.session.phase == Phase.MENU and app.braking_mode == GameMode.SHORT_BRAKING
    assert app.session.vehicle_config.front_brake_share == .7
    assert app.player_road_ab.a is None
