"""真实控件/结算夹具，分别检查失败无时间差、同题完整B与重开。"""

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
    app.open_tire_tuning()
    app.tire_tuning.activate(index)
    app.tire_tuning.activate(4)


def test_result_install_freezes_actual_fixture_a_and_observes_once_complete_b(app):
    a_result = result_fixture(app)
    fit(app)
    assert app.player_road_ab.a['result']['reason'] == a_result.slalom.reason
    assert app.player_road_ab.a['config']['lateral_stiffness'] == 35000. and app.player_road_ab.b is None
    app.tire_tuning.activate(7)
    assert '暂无记录' in app.player_road_panel.cards[1].getText()
    app.key_down('escape')
    app.key_up('escape')
    assert app.player_road_panel.root.isHidden() and not app.tire_tuning.root.isHidden()
    app.back_from_tire_tuning()
    b_result = result_fixture(app, succeeded=True)
    saved = app.player_road_ab.path.read_bytes()
    app.refresh_panel()
    assert app.player_road_ab.path.read_bytes() == saved
    assert app.player_road_ab.b['result']['run_seconds'] == b_result.slalom.run_seconds
    app.open_tire_tuning()
    app.tire_tuning.activate(7)
    panel = app.player_road_panel
    assert '无有效总时间' in panel.cards[0].getText() and '有效11.400s' in panel.cards[1].getText()
    assert 'B−A' not in panel.delta.getText() and '未到达' in panel.columns[1].getText()
    for column in panel.columns:
        lower, upper = column.getTightBounds(panel.root)
        assert lower.z > -.37 and upper.x < 1.60
    loaded = PlayerRoadAB(app.player_road_ab.path)
    assert loaded.a == app.player_road_ab.a and loaded.b == app.player_road_ab.b


def test_same_recipe_cancel_and_failed_vehicle_save_never_freeze_a(app, monkeypatch):
    result_fixture(app)
    fit(app, 0)
    assert app.player_road_ab.a is None and not app.player_road_ab.path.exists()
    app.back_from_tire_tuning()
    app.open_tire_tuning()

    def fail(self, path=None):
        raise OSError('只读')

    monkeypatch.setattr(WorkspaceVehicle, 'save', fail)
    app.tire_tuning.activate(3)
    app.tire_tuning.activate(4)
    assert app.player_road_ab.a is None and not app.player_road_ab.path.exists()
    assert app.session.phase == Phase.RESULTS


def test_ab_write_failure_still_allows_saved_hardware_and_reports_notice(app):
    result_fixture(app)
    replace_file = Path.replace

    def fail_comparison(path, target):
        if target == app.player_road_ab.path:
            raise OSError('道路对照目录只读')
        return replace_file(path, target)

    with patch.object(Path, 'replace', fail_comparison):
        fit(app)
    assert app.session.vehicle_config.lateral_stiffness == 70000.
    assert app.session.phase == Phase.MENU and app.player_road_ab.a is None
    assert app.player_road_ab.capture_blocked
    assert '未保存' in app.player_road_ab.notice and '道路对照有提示' in app.tire_tuning.notice.getText()


def test_different_input_settings_only_show_values_without_time_delta(app):
    result_fixture(app, succeeded=True)
    fit(app)
    app.back_from_tire_tuning()
    from driving_modes import DrivingMode
    app.session.set_vehicle_config(app.session.vehicle_config)
    app.session.set_driving_mode(DrivingMode.SIMULATION)
    result_fixture(app, succeeded=True)
    app.open_tire_tuning()
    app.tire_tuning.activate(7)
    assert '条件不同' in app.player_road_panel.delta.getText()
    assert 'B−A' not in app.player_road_panel.delta.getText()
