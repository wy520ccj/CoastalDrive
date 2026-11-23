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


def test_rules_toggle_and_budget_parameter_start_preserve_owned_vehicle(app):
    assert '170米' in app.panel_note.getText() and app.panel_option_count == 4
    app.buttons[1]['command']()
    assert app.braking_mode == GameMode.SHORT_BRAKING and '80–85' in app.panel_note.getText()
    original = app.workspace_vehicle
    app.buttons[0]['command']()
    app.challenge_action('challenge-tab', 2)
    app.challenge_action('challenge-value', ('brake_share', '70'))
    assert app.workspace_vehicle == original
    app.challenge_action('challenge-start')
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    assert app.session.mode == GameMode.SHORT_BRAKING and app.session.highway.snapshot.braking.short
    assert app.session.vehicle_config.front_brake_share == .7
    app.apply_scene(app.session.current, 0.)
    assert app.scene.braking_markers.standard.isHidden() and not app.scene.braking_markers.short.isHidden()


def test_same_window_reference_return_keeps_budget_candidate_and_restores_owned_vehicle(app):
    from challenge_catalog import ROAD_CHALLENGES

    app.choose_braking_lesson(GameMode.SHORT_BRAKING)
    app.open_brake_tuning()
    app.challenge_action('challenge-tab', 2)
    app.challenge_action('challenge-value', ('brake_share', '70'))
    window, original = app.win, app.workspace_vehicle
    app.challenge_action('challenge-lab')
    finish(app, 'lab')
    draft = app.budget_drafts[GameMode.SHORT_BRAKING]
    assert app.lab.engineered_config == ROAD_CHALLENGES[GameMode.SHORT_BRAKING].configuration(draft)
    app.lab.back_to_game()
    finish(app, 'game')
    assert app.win is window and app.session.mode == GameMode.SHORT_BRAKING
    assert app.session.vehicle_config.front_brake_share == .7
    app.back_to_menu()
    assert app.workspace_vehicle == original


@pytest.mark.parametrize('save_notice', ['', '本次成绩未保存；请检查存储目录，可继续练习。'])
def test_budget_result_uses_actual_stopping_metric_and_save_notice(app, save_notice):
    from test_brake_road_ab_ui import result_fixture

    result = result_fixture(app)
    road = app.session.highway.snapshot
    app.session.highway.snapshot = replace(road, engineering=replace(road.engineering, save_notice=save_notice))
    app._shown_phase = None
    app.refresh_panel()
    assert result.stopping_m == 39.
    texts = '\n'.join(label.getText() for label in app.career_panel.labels)
    assert '39' in texts and '停车距离' in texts
    if save_notice:
        assert save_notice in texts
    app.challenge_action('challenge-adjust')
    assert app.career_panel.page == 'challenge' and app.budget_mode == GameMode.SHORT_BRAKING
