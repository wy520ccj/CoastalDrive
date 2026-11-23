"""实际控件与明确结算夹具：前后记录、失败无差值和存储原子边界。"""

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from application import CoastalDrive
from player_road_ab import PlayerRoadAB
from race import GameMode
from session import Phase
from vehicle_workspace import WorkspaceVehicle
from workshop import build_config


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, output=tmp_path/'game', workspace_vehicle=
        WorkspaceVehicle('reference-rwd', build_config(0, False)))
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.back_to_menu()
    yield game
    game.close_game()


def result_fixture(app, *, mode=GameMode.SHORT_BRAKING, succeeded=True, second=False):
    app.choose_braking_lesson(mode)
    if app.session.mode != mode or app.session.phase not in (Phase.COUNTDOWN, Phase.DRIVING):
        app.start_braking_lesson()
        app.challenge_action('challenge-start')
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    state = app.session.highway.snapshot
    short = mode == GameMode.SHORT_BRAKING
    result = replace(state.braking, finished=True, succeeded=succeeded, entry_kph=84.1 if second else 84.,
        hold_seconds=1., stopping_m=(35. if second else 39.) if short else None,
        position=(135. if second else 139.) if short else (172. if second else 162.),
        error_m=None if short else (2. if second else -8.),
        medal=('银' if second else '铜') if short and succeeded else ('金' if second else '铜') if succeeded else '',
        reason='完成' if succeeded else '驶离直行验车带')
    spec = app.session.challenge_spec
    rating = spec.evaluate(app.session.challenge_build, 20., .05, valid=succeeded,
        metric_value=result.stopping_m if short else abs(result.error_m))
    status = replace(state.engineering, result=rating, seconds=20., litres=.05, consumption=rating.consumption)
    app.session.highway.snapshot = replace(state, braking=result, finished=True, running=False,
        succeeded=succeeded, elapsed=20., engineering=status)
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    return result


def fit(app, index=2):
    app.challenge_action('challenge-adjust')
    app.challenge_action('challenge-tab', 2)
    app.challenge_action('challenge-value', ('brake_share', '60' if index == 0 else '70'))
    app.challenge_action('challenge-start')


@pytest.mark.parametrize('mode', [GameMode.SHORT_BRAKING, GameMode.BRAKING_LESSON])
def test_whole_brake_a_b_visible_and_original_tire_pair_preserved(app, mode):
    a = result_fixture(app, mode=mode)
    fit(app)
    ab = app.player_brake_ab
    assert ab.a['result']['position'] == a.position and ab.b is None
    assert not app.player_road_ab.path.exists()
    # 出发倒计时不能打开对照；先正常返回菜单，再查看尚无B的冻结A。
    app.open_player_road_ab('brakes')
    assert app.player_road_panel.root.isHidden()
    app.back_to_menu()
    app.open_player_road_ab('brakes')
    assert '暂无记录' in app.player_road_panel.cards[1].getText()
    app.player_road_panel.key('escape')
    b = result_fixture(app, mode=mode, second=True)
    saved = ab.path.read_bytes()
    app.refresh_panel()
    assert ab.path.read_bytes() == saved and ab.b['result']['entry_kph'] == b.entry_kph
    app.open_brake_tuning()
    app.open_player_road_ab('brakes')
    panel = app.player_road_panel
    assert '前制动60%' in panel.cards[0].getText() and '前制动70%' in panel.cards[1].getText()
    assert ('-4.000m' if b.short else '-6.000m') in panel.delta.getText()
    assert '+0.100km/h' in panel.delta.getText()
    assert panel.delta.getTightBounds(panel.root)[0].z > panel.notice.getTightBounds(panel.root)[1].z+.015
    loaded = PlayerRoadAB(ab.path, brakes=True)
    assert (loaded.a, loaded.b) == (ab.a, ab.b)


def test_failed_b_not_scored_and_source_changes_only_parallel_values(app):
    result_fixture(app)
    fit(app)
    result_fixture(app, succeeded=False, second=True)
    app.open_brake_tuning()
    app.open_player_road_ab('brakes')
    assert '无有效成绩' in app.player_road_panel.cards[1].getText()
    assert 'B−A' not in app.player_road_panel.delta.getText()
    ab = app.player_brake_ab
    ab.b['context']['world']['source'] = 'different'
    app.player_road_panel.show(ab)
    assert '条件不同' in app.player_road_panel.delta.getText()


def test_same_budget_build_does_not_freeze_a_or_save_owned_vehicle(app):
    result_fixture(app)
    original = app.workspace_vehicle
    fit(app, 0)
    assert app.player_brake_ab.a is None
    assert app.workspace_vehicle == original and not app.workspace_path.exists()


def test_ab_write_failure_retains_saved_vehicle_and_warns(app):
    result_fixture(app)
    replace_file = Path.replace

    def fail_comparison(path, target):
        if target == app.player_brake_ab.path:
            raise OSError('只读对照')
        return replace_file(path, target)

    with patch.object(Path, 'replace', fail_comparison):
        fit(app)
    assert app.session.vehicle_config.front_brake_share == .7 and app.session.phase == Phase.COUNTDOWN
    assert app.player_brake_ab.capture_blocked and app.player_brake_ab.a is None
    assert '未保存' in app.player_brake_ab.notice
    assert not app.workspace_path.exists()
