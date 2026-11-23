"""道路完整A/B从预算方案启动建立，保存失败不阻止实际试跑。"""

from pathlib import Path
from unittest.mock import patch

import pytest
from test_result_tuning import result_fixture

from application import CoastalDrive
from player_road_ab import PlayerRoadAB
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


def fit(app, index=3):
    app.challenge_action('challenge-adjust')
    app.challenge_action('challenge-tab', 1)
    app.challenge_action('challenge-value', ('front_tire', '50' if index == 0 else '65'))
    app.challenge_action('challenge-start')


def test_changed_budget_build_freezes_whole_a_and_observes_one_whole_b(app):
    a_result = result_fixture(app)
    original = app.workspace_vehicle
    fit(app)
    store = app.player_road_ab
    assert store.a['result']['reason'] == a_result.slalom.reason
    assert store.a['config']['lateral_stiffness'] == 50000. and store.b is None
    b_result = result_fixture(app, succeeded=True)
    saved = store.path.read_bytes()
    app.refresh_panel()
    assert store.path.read_bytes() == saved
    assert store.b['result']['run_seconds'] == b_result.slalom.run_seconds
    app.open_player_road_ab('tires')
    panel = app.player_road_panel
    assert '无有效总时间' in panel.cards[0].getText() and '有效11.400s' in panel.cards[1].getText()
    assert 'B−A' not in panel.delta.getText() and '未到达' in panel.columns[1].getText()
    loaded = PlayerRoadAB(store.path)
    assert (loaded.a, loaded.b) == (store.a, store.b)
    assert app.workspace_vehicle == original and not app.workspace_path.exists()
    panel.key('escape')
    assert panel.root.isHidden() and app.career_panel.page == 'challenge-result'


def test_same_build_and_cancel_do_not_replace_a(app):
    result_fixture(app)
    app.challenge_action('challenge-adjust')
    app.challenge_action('challenge-back')
    assert app.player_road_ab.a is None
    result_fixture(app)
    fit(app, 0)
    assert app.player_road_ab.a is None and not app.player_road_ab.path.exists()


def test_ab_write_failure_keeps_player_car_and_allows_temporary_challenge(app):
    result_fixture(app)
    original = app.workspace_vehicle
    replace_file = Path.replace

    def fail_comparison(path, target):
        if target == app.player_road_ab.path:
            raise OSError('道路对照目录只读')
        return replace_file(path, target)

    with patch.object(Path, 'replace', fail_comparison):
        fit(app)
    assert app.session.vehicle_config.lateral_stiffness == 65000.
    assert app.session.phase == Phase.COUNTDOWN and app.player_road_ab.a is None
    assert app.player_road_ab.capture_blocked and '未保存' in app.player_road_ab.notice
    assert app.workspace_vehicle == original and not app.workspace_path.exists()
    result_fixture(app, succeeded=True)
    assert any('未保存' in label.getText() for label in app.career_panel.labels)


def test_different_input_settings_show_values_without_time_delta(app):
    from driving_modes import DrivingMode

    result_fixture(app, succeeded=True)
    fit(app)
    app.session.finish()
    app.session.menu()
    app.session.set_driving_mode(DrivingMode.SIMULATION)
    result_fixture(app, succeeded=True)
    app.open_player_road_ab('tires')
    assert '条件不同' in app.player_road_panel.delta.getText()
    assert 'B−A' not in app.player_road_panel.delta.getText()
