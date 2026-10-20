"""真实巡回控件与转场；合成终态只验证计分/呈现，不写单项玩家最佳。"""

from dataclasses import replace

import pytest
from test_driving_tour import result

from application import CoastalDrive
from driving_tour import LEGS, DrivingTour
from race import GameMode
from session import Phase


@pytest.fixture
def app(tmp_path):
    game = CoastalDrive(smoke=True, output=tmp_path)
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    yield game
    game.close_game()


def drive(game):
    for _ in range(360):
        game.session.tick()
    assert game.session.phase == Phase.DRIVING
    game._shown_phase = None
    game.refresh_panel()


def finish_fixture(game, *, passed=True, seconds=None):
    highway = result(game.session.mode, seconds=seconds)
    if highway.sprint is not None:
        highway = replace(highway, sprint=replace(highway.sprint, reason='巡回结算规则夹具'))
    else:
        highway = replace(highway, overtake=replace(highway.overtake, reason='巡回结算规则夹具'))
    if not passed:
        highway = replace(highway, succeeded=False)
    game.session.highway.snapshot = highway
    game.session.phase = Phase.RESULTS
    game._shown_phase = None
    game.refresh_panel()


def test_tour_entry_keyboard_round_retry_and_deduplicated_completion(app):
    app.back_to_menu()
    assert len(app.main_menu.buttons) == 8
    app.choose_sprint_routes()
    assert app.panel_option_count == 7
    app.select_panel_option(5)
    app.handle_panel_key('enter')
    assert not app.tour_panel.root.isHidden() and app.main_menu.root.isHidden() is False
    app.key_down('escape')
    app.key_up('escape')
    assert app.sprint_menu and app.panel_selection == 5
    app.open_driving_tour()
    app.tour_panel.activate(0)
    drive(app)
    assert app.tour_active and app.session.mode == LEGS[0] and not app.tour_banner.isHidden()
    config = app.session.vehicle_config
    finish_fixture(app, seconds=106.)
    assert app.tour_store.current == () and '仍需铜牌' in app.tour_message.getText()
    app.buttons[0]['command']()
    drive(app)
    finish_fixture(app, passed=False)
    assert app.tour_store.current == () and '重试' in app.buttons[0]['text']
    app.buttons[0]['command']()
    drive(app)
    for index, mode in enumerate(LEGS):
        assert app.session.mode == mode and app.session.vehicle_config == config
        finish_fixture(app)
        assert len(app.tour_store.current) == index+1
        app._shown_phase = None
        app.refresh_panel()
        assert len(app.tour_store.current) == index+1
        assert not app.tour_pending
        if index < 2:
            assert '下一站' in app.buttons[0]['text']
            app.buttons[0]['command']()
            drive(app)
    assert '再跑一轮' == app.buttons[0]['text'] and app.tour_store.new_best
    restored = DrivingTour(app.tour_store.path, app.session.score_variant())
    assert restored.best == app.tour_store.current
    app.buttons[1]['command']()
    assert not app.tour_panel.root.isHidden() and app.tour_banner.isHidden()
    app.tour_panel.activate(1)
    assert app.tour_store.current == () and app.tour_store.best == restored.best


def test_leaving_for_lab_or_solo_pauses_tour_and_same_car_can_resume(app):
    app.open_driving_tour()
    app.start_tour_leg()
    drive(app)
    finish_fixture(app)
    expected = app.tour_store.current
    window = app.win
    app.open_vehicle_lab()
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == 'lab' and not app.tour_active
    app.lab.back_to_game()
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.win is window and app.workspace == 'game' and not app.tour_active
    app.open_driving_tour()
    assert app.tour_store.current == expected
    app.start_tour_leg()
    assert app.session.mode == LEGS[1]
    app.start_game(mode=GameMode.FREE_DRIVE)
    assert not app.tour_active
    assert app.tour_store.current == expected


def test_changed_inputs_cannot_credit_a_different_tour_group(app):
    app.open_driving_tour()
    app.start_tour_leg()
    drive(app)
    original_variant = app.tour_store.variant
    finish_fixture(app)
    app.back_to_menu()
    app.session.set_abs_enabled(not app.session.abs_enabled)
    assert app.session.score_variant() != original_variant
    app.open_driving_tour()
    assert app.tour_store.variant != original_variant and not app.tour_store.current
    assert len(DrivingTour(app.tour_store.path, original_variant).current) == 1
