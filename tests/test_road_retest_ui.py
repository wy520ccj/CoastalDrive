"""从真实保存A/B准备参考复测，旧工作区与道路车保持；不伪造新通关。"""

from pathlib import Path

import pytest

from application import CoastalDrive
from lab_experiment import LabOptions
from player_road_ab import PlayerRoadAB
from race import GameMode
from session import Phase
from vehicle_workspace import WorkspaceVehicle
from workshop import build_config


def finish(app, workspace):
    for _ in range(35):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    car = WorkspaceVehicle('reference-rwd', build_config(0, False))
    game = CoastalDrive(smoke=True, output=tmp_path/'game', lab_output=tmp_path/'reports', workspace_vehicle=car)
    car.save(game.workspace_path)
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.back_to_menu()
    yield game
    game.close_game()


def open_pair(app):
    app.choose_braking_lesson(GameMode.SHORT_BRAKING)
    source = Path('docs/evidence/BRAKE-ROAD-AB-01/normal/player-braking-ab.json')
    app.player_brake_ab.path.write_bytes(source.read_bytes())
    app.player_brake_ab = PlayerRoadAB(app.player_brake_ab.path, brakes=True)
    app.open_brake_tuning()
    app.tire_tuning.activate(7)


def test_missing_b_cannot_leave_game_or_change_car(app):
    app.choose_braking_lesson()
    app.open_brake_tuning()
    app.tire_tuning.activate(7)
    before = app.session.current
    assert app.player_road_panel.retest_button['state'] == 'disabled'
    app.open_road_retest()
    assert app.workspace == 'game' and app._workspace_steps is None and app.road_retest_request is None
    assert app.session.current == before and '未进入' in app.player_road_panel.notice.getText()


def test_retest_preserves_old_a_b_drafts_and_returns_original_pair(app):
    old_car = app.workspace_path.read_bytes()
    app.open_vehicle_lab()
    finish(app, 'lab')
    lab = app.lab
    lab.set_options(LabOptions(speed_kph=20., duration=.1, friction=.6))
    lab.start_experiment()
    while not lab.run_state.done:
        lab.run_state.step()
    lab.run_state.paused = True
    lab.record = lab.active_record()
    lab.pin_baseline()
    lab.show_sample(6)
    lab.entries['cg'].enterText('.47')
    old, baseline, cursor = lab.record, lab.baseline, lab.view_index
    lab.back_to_game()
    finish(app, 'game')
    open_pair(app)
    old_pair = app.player_brake_ab.path.read_bytes()
    app.player_road_panel.retest_button['command']()
    finish(app, 'lab')
    lab = app.lab
    assert lab.record.snapshots == old.snapshots and lab.baseline.snapshots == baseline.snapshots
    assert lab.view_index == cursor and lab.entries['cg'].get() == '.47'
    retest = lab.road_retest
    assert retest.comparison.status == 'ready' and retest.comparison.run is None
    lab.engine.messenger.send('tab')
    lab.engine.messenger.send('f1')
    assert not any(entry.guiItem.getFocus() for entry in lab.entries.values())
    assert lab.parameter_help.root.isHidden()
    assert retest.comparison.configs[0].front_brake_share == .45 and retest.comparison.configs[1].front_brake_share == .7
    retest.run_button['command']()
    run = retest.comparison.run
    run.step()
    retest.hide()
    assert run.closed and retest.comparison.partial is not None
    lab.road_retest_button['command']()
    assert retest.comparison.status == 'cancelled' and retest.comparison.run is None
    assert lab.record.snapshots == old.snapshots and lab.baseline.snapshots == baseline.snapshots
    assert lab.entries['cg'].get() == '.47' and lab.view_index == cursor
    retest.back()
    finish(app, 'game')
    assert app.session.phase == Phase.MENU and app.braking_mode == GameMode.SHORT_BRAKING
    assert not app.player_road_panel.root.isHidden() and app.tire_tuning.topic == 'brakes'
    assert app.player_brake_ab.path.read_bytes() == old_pair and app.workspace_path.read_bytes() == old_car
    assert app.lab_workspace.record.snapshots == old.snapshots and app.lab_workspace.retest_state is not None


def test_export_error_keeps_frozen_pair_and_old_workspace(app, monkeypatch):
    open_pair(app)
    app.open_road_retest()
    finish(app, 'lab')
    comparison = app.lab.road_retest.comparison

    def fail(self, folder):
        raise OSError('只读')

    monkeypatch.setattr(type(comparison), 'export', fail)
    app.lab.road_retest.export()
    assert app.lab.road_retest.comparison is comparison and app.lab.road_retest.report_path is None
    assert app.lab.record is app.lab.baseline is None
