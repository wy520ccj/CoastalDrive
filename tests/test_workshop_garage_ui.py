"""当前车的改装、练习、结果与方案入口形成同窗闭环。"""

import pytest

from application import CoastalDrive
from race import GameMode
from session import Phase


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, output=tmp_path/'game', lab_output=tmp_path/'reports')
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.open_workshop_garage()
    yield game
    game.close_game()


def test_current_vehicle_preview_cancel_and_same_course_trial_return(app):
    original, snapshot, window = app.workspace_vehicle, app.session.current, app.win
    app.workshop_garage.activate(0)
    assert app.slalom_mode == GameMode.SLALOM_PRACTICE
    assert app.workshop_vehicle.identity[1] == original.config
    app.tire_tuning.activate(3)
    app.tire_tuning.activate(8)
    assert app.session.phase == Phase.MENU and app.workspace_vehicle == original
    app.tire_tuning.activate(6)
    assert not app.workshop_garage.root.isHidden() and app.session.current == snapshot
    app.workshop_garage.activate(0)
    app.tire_tuning.activate(3)
    app.tire_tuning.activate(4)
    assert app.workspace_vehicle.config.lateral_stiffness == 70000.
    app.tire_tuning.activate(8)
    assert app.session.mode == GameMode.SLALOM_PRACTICE and app.session.phase == Phase.COUNTDOWN
    for _ in range(360):
        app.session.tick()
    assert app.session.phase == Phase.DRIVING
    app.session.finish()
    app._shown_phase = None
    app.refresh_panel()
    assert app.panel_title.getText() == '练习结束'
    app.buttons[3]['command']()
    assert app.tire_tuning.original == app.workspace_vehicle
    app.tire_tuning.activate(6)
    app.buttons[1]['command']()
    assert not app.workshop_garage.root.isHidden() and app.win is window
    assert not app.player_road_ab.path.exists()
    app.back_to_menu()
    app.session.finish()
    app._shown_phase = None
    app.refresh_panel()
    assert not app.panel_title.isHidden()


def test_brakes_route_and_repeated_preview_reuses_one_buffer(app):
    app.workshop_garage.activate(1)
    assert app.braking_mode == GameMode.SHORT_BRAKING and app.tire_tuning.topic == 'brakes'
    buffer = app.workshop_vehicle.buffer
    windows = app.graphicsEngine.getNumWindows()
    for _ in range(3):
        app.tire_tuning.activate(6)
        app.workshop_garage.activate(0)
        app.tire_tuning.activate(6)
        app.workshop_garage.activate(1)
    assert app.workshop_vehicle.buffer == buffer
    assert app.graphicsEngine.getNumWindows() == windows
    app.tire_tuning.activate(6)
    app.workshop_garage.activate(5)
    assert not buffer.isActive()


def test_scheme_library_returns_to_same_garage_and_preserves_car(app):
    vehicle, window = app.workspace_vehicle, app.win
    app.workshop_garage.activate(3)
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == 'lab' and not app.lab.schemes.root.isHidden()
    app.taskMgr.remove('lab-update')
    app.lab.back_to_game()
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    app.taskMgr.remove('drive-update')
    assert app.workspace == 'game' and not app.workshop_garage.root.isHidden()
    assert app.win is window and app.workspace_vehicle == vehicle


def test_trial_and_engineering_menus_return_to_garage_without_stale_context(app):
    app.choose_driving_mode()
    assert not app.driving_mode_page
    app.workshop_garage.activate(2)
    app.back_to_modes()
    assert not app.workshop_garage.root.isHidden()
    app.workshop_garage.activate(4)
    app.journey.activate(3)
    assert not app.workshop_garage.root.isHidden() and not app.workshop_lab_return
    app.workshop_garage.activate(5)
    app.back_to_menu()
    assert not app.workshop_garage_return
