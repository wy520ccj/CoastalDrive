"""生涯正常导航、保存边界与暂停返回；合成解锁仅用于界面测试。"""

import time

import pytest
from panda3d.core import Point2

from application import CoastalDrive
from career import CareerProgress
from career_run import CareerResult
from race import GameMode
from session import Phase
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, output=tmp_path/'game',
        workspace_vehicle=WorkspaceVehicle('reference-rwd', vehicle_design('reference-rwd').config))
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.open_career()
    yield game
    game.close_game()


def test_locked_entry_modal_and_garage_are_separate_from_reports(app):
    before = app.session.current
    app.career_action('brief', 'coastal-cup')
    app.career_action('start', 'coastal-cup')
    assert app.session.phase == Phase.MENU and app.session.current == before
    app.key_down('f2')
    app.key_up('f2')
    assert not app.driving_mode_page
    app.key_down('escape')
    app.key_up('escape')
    assert app.career_panel.page == 'board'
    app.career_action('garage')
    assert app.career_panel.page == 'garage' and app.player_road_panel.root.isHidden()
    app.career_action('board')
    assert not app.workshop_vehicle.buffer.isActive()
    assert app.career_panel.page == 'board' and app.session.current == before


def test_purchase_install_failure_preserves_owned_part_and_retry_is_free(app, monkeypatch):
    for event in ('first-drive', 'parking'):
        app.career_progress.record(CareerResult(event, 8., elapsed=25., finished=True, succeeded=True, stars=3))
    before = app.workspace_vehicle
    save = WorkspaceVehicle.save

    def fail(self, path=None):
        raise OSError('测试保存失败')

    monkeypatch.setattr(WorkspaceVehicle, 'save', fail)
    app.career_action('part', 'sport-front')
    assert app.workspace_vehicle == before
    assert app.career_progress.credits == 250 and 'sport-front' in app.career_progress.owned
    assert app.career_panel.page == 'garage'
    monkeypatch.setattr(WorkspaceVehicle, 'save', save)
    app.career_action('part', 'sport-front')
    assert app.workspace_vehicle.config.lateral_stiffness == 70000. and app.career_progress.credits == 250
    assert CareerProgress(app.career_progress.path).owned == {'sport-front'}
    app.career_action('restore')
    assert app.workspace_vehicle == before


def test_collection_preview_lock_and_selection_preserve_actual_vehicle_until_confirmation(app):
    original, snapshot = app.workspace_vehicle, app.session.current
    app.career_action('garage')
    app.career_action('garage-car', 'coastal-gt')
    app.career_action('garage-select')
    assert app.workspace_vehicle == original and app.session.current == snapshot
    app.career_action('garage-car', 'coastal-hatch')
    assert app.workspace_vehicle == original
    app.career_action('garage-select')
    assert app.workspace_vehicle.design_id == 'coastal-hatch'
    assert app.session.base_vehicle_config == app.workspace_vehicle.config
    assert app.vehicle_model_id == 'coastal-hatch'
    assert app.session.current == snapshot
    app.career_action('garage-car', original.design_id)
    app.career_action('garage-select')
    assert app.workspace_vehicle == original


def test_garage_reserves_vehicle_area_and_directional_focus_follows_the_layout(app):
    app.career_action('garage')
    view, panel = app.workshop_vehicle, app.career_panel
    for tab in ('cars', 'upgrade', 'paint'):
        app.career_action('garage-tab', tab)
        left, right, bottom, top = view.frame['frameSize']
        for button in panel.buttons:
            x, z = button.getX(), button.getZ()
            l, r, b, t = button['frameSize']
            assert min(right, x+r)-max(left, x+l) <= 0 or min(top, z+t)-max(bottom, z+b) <= 0
        for angle in (25, -25):
            view.orbit(angle)
            for corner in view.framing_points:
                point = Point2()
                assert view.camera.node().getLens().project(
                    view.camera.getRelativePoint(view.scene, corner), point)
                assert abs(point.x) <= .85 and abs(point.y) <= .79
    # 从页尾向上，应进入同一列的颜色应用，而不是跳到左侧车模角度按钮。
    panel.select(len(panel.buttons)-1)
    panel.key('arrow_up')
    assert panel.buttons[panel.selected]['extraArgs'][0] == 'garage-paint-save'


def test_pause_retry_and_return_keep_original_world_until_explicit_restart(app):
    app.career_action('start', 'first-drive')
    simulation = app.session.simulation
    app.session.pause()
    app._shown_phase = None
    app.key_down('arrow_down')
    app.key_up('arrow_down')
    assert app.career_panel.page == 'pause'
    app.career_action('resume')
    assert app.session.phase == Phase.COUNTDOWN and app.session.simulation is simulation
    app.return_from_test_drive()
    assert app.career_panel.page == 'board' and app.session.phase == Phase.MENU
    assert app.career_progress.stars == 0 and not app.career_progress.path.exists()


def test_production_loader_holds_independent_countdown_until_ready(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, independent_clock=True, output=tmp_path/'game')
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    try:
        game.open_career()
        game.career_active, game.career_event_id = True, 'first-drive'
        game._begin_workspace(game._load_road(GameMode.CAREER, 'endless'), '加载赛事', '测试')
        for _ in range(12):
            game.taskMgr.step()
            if game.session.phase == Phase.PAUSED:
                break
        assert game._workspace_steps is not None and game.session.phase == Phase.PAUSED
        before = game.session.progress()[0]
        time.sleep(.15)
        assert game.session.progress()[0] == before
        for _ in range(16):
            game.taskMgr.step()
            if game._workspace_steps is None:
                break
        game.taskMgr.remove('drive-update')
        assert game.session.phase == Phase.COUNTDOWN and game.session.countdown_ticks > 330
        assert game.session.highway.snapshot.career.elapsed == 0
    finally:
        game.close_game()
