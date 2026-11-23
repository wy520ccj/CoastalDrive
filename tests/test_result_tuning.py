"""预算结算与重试回归；合成终态只检验导航/保存，不是驾驶成绩。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from challenge_build import BuildDraft
from race import GameMode
from session import Phase
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
    if (app.session.mode != mode or app.session.phase not in (Phase.COUNTDOWN, Phase.DRIVING)
            or app.session.challenge_spec is None):
        app.start_slalom_lesson()
        app.challenge_action('challenge-start')
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    highway = app.session.highway.snapshot
    stage = replace(highway.slalom, gates=6 if succeeded else 2, entry_kph=75., entry_time=5.,
        gate_times=(2., 4., 6., 8., 10., 11.4) if succeeded else (2., 4., 6.),
        clearances=(.5,)*6 if succeeded else (.5, .5, -.3), errors=(.2,)*6 if succeeded else (.2, .2, 1.2),
        run_seconds=11.4 if succeeded else 6., finished=True, succeeded=succeeded,
        medal='金' if succeeded else '', reason='金牌 · 连续通过全部6道门' if succeeded else '错过第3门；车身超出门线0.30m')
    spec, build = app.session.challenge_spec, app.session.challenge_build
    result = spec.evaluate(build, 20., .05, valid=succeeded, reason=stage.reason, metric_value=stage.run_seconds)
    status = replace(highway.engineering, result=result, seconds=20., litres=.05, consumption=result.consumption)
    app.session.highway.snapshot = replace(highway, finished=True, running=False, slalom=stage,
        elapsed=20., succeeded=succeeded, reason=stage.reason, engineering=status)
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    return app.session.highway.snapshot


@pytest.mark.parametrize('succeeded', [False, True])
def test_adjustment_returns_to_same_draft_and_never_overwrites_owned_vehicle(app, succeeded):
    result_fixture(app, succeeded=succeeded)
    before = app.workspace_vehicle
    app.challenge_action('challenge-adjust')
    assert app.career_panel.page == 'challenge' and app.session.phase == Phase.MENU
    assert app.budget_mode == GameMode.FAST_SLALOM
    app.challenge_action('challenge-value', ('front_tire', '65'))
    assert app.workspace_vehicle == before and not app.workspace_path.exists()
    app.challenge_action('challenge-back')
    assert app.slalom_menu and app.slalom_mode == GameMode.FAST_SLALOM
    assert app.workspace_vehicle == before


@pytest.mark.parametrize('mode', [GameMode.SLALOM_LESSON, GameMode.FAST_SLALOM])
def test_changed_budget_hardware_only_applies_to_explicit_same_course_retry(app, mode):
    result_fixture(app, mode)
    original = app.workspace_vehicle
    app.challenge_action('challenge-adjust')
    app.challenge_action('challenge-value', ('front_tire', '65'))
    app.challenge_action('challenge-start')
    assert app.session.phase == Phase.COUNTDOWN and app.session.mode == mode
    assert app.session.vehicle_config.lateral_stiffness == 65000.
    assert app.workspace_vehicle == original and not app.workspace_path.exists()
    app.back_to_menu()
    assert app.session.base_vehicle_config == original.config


def test_plan_write_failure_keeps_candidate_and_surfaces_error_without_touching_vehicle(app, tmp_path):
    result_fixture(app)
    app.challenge_action('challenge-adjust')
    app.challenge_action('challenge-value', ('front_tire', '65'))
    blocked = tmp_path/'blocked'
    blocked.write_text('原文件', encoding='utf-8')
    app.budget_plans.path = blocked/'plans.json'
    app.challenge_action('challenge-save')
    assert app.budget_drafts[GameMode.FAST_SLALOM].front_tire == 1.3
    assert '未保存' in app.career_panel.challenge_readouts['notice'].getText()
    assert blocked.read_text(encoding='utf-8') == '原文件'
    assert not app.workspace_path.exists()


def test_restore_original_is_free_and_retry_with_same_build_starts_new_attempt(app):
    result_fixture(app)
    original = app.workspace_vehicle
    app.challenge_action('challenge-adjust')
    app.challenge_action('challenge-value', ('front_tire', '65'))
    app.challenge_action('challenge-reset')
    assert app.budget_drafts[GameMode.FAST_SLALOM] == BuildDraft()
    app.challenge_action('challenge-start')
    assert app.session.phase == Phase.COUNTDOWN and app.workspace_vehicle == original
    assert not app.workspace_path.exists()


def test_legacy_tuning_and_ab_actions_cannot_interrupt_live_driving(app):
    app.start_slalom_lesson()
    app.challenge_action('challenge-start')
    before, simulation = app.session.current, app.session.simulation
    app.open_tire_tuning()
    app.open_brake_tuning()
    app.open_player_road_ab('tires')
    assert app.session.phase == Phase.COUNTDOWN and app.session.simulation is simulation
    assert app.session.current == before and app.career_panel.root.isHidden()
    assert app.player_road_panel.root.isHidden()
