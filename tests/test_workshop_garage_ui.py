"""当前车的改装、练习、结果与方案入口形成同窗闭环。"""

import pytest

from application import CoastalDrive
from race import GameMode
from session import Phase


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, load_initial_scene=False, output=tmp_path/'game', lab_output=tmp_path/'reports')
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.open_workshop_garage()
    yield game
    game.close_game()


def test_workshop_challenge_prepares_fixed_car_and_back_preserves_owned_vehicle(app):
    original, window = app.workspace_vehicle, app.win
    assert app.main_menu.home.isHidden()
    app.workshop_garage.activate(0)
    assert app.budget_mode == GameMode.FAST_SLALOM and app.budget_origin == 'workshop'
    app.challenge_action('challenge-value', ('front_tire', '65'))
    assert app.session.phase == Phase.MENU and app.workspace_vehicle == original
    app.challenge_action('challenge-start')
    assert app.session.mode == GameMode.FAST_SLALOM and app.session.phase == Phase.COUNTDOWN
    assert app.session.vehicle_config.lateral_stiffness == 65000.
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    app.session.finish()
    app._shown_phase = None
    app.refresh_panel()
    assert app.career_panel.page == 'challenge-result'
    app.challenge_action('challenge-back')
    assert not app.workshop_garage.root.isHidden() and app.win is window
    assert app.main_menu.home.isHidden()
    assert app.workspace_vehicle == original and not app.workspace_path.exists()


def test_brakes_route_and_repeated_budget_pages_reuse_one_display_buffer(app):
    app.workshop_garage.activate(1)
    assert app.budget_mode == GameMode.SHORT_BRAKING
    buffer = app.workshop_vehicle.buffer
    windows = app.graphicsEngine.getNumWindows()
    for _ in range(3):
        app.challenge_action('challenge-back')
        app.workshop_garage.activate(0)
        app.challenge_action('challenge-back')
        app.workshop_garage.activate(1)
    assert app.workshop_vehicle.buffer == buffer
    assert app.graphicsEngine.getNumWindows() == windows
    app.challenge_action('challenge-back')
    app.workshop_garage.activate(5)
    app._shown_phase = None
    app.refresh_panel()
    assert not app.main_menu.home.isHidden() and app.main_menu.credits.getText() == ''
    assert not buffer.isActive()
    assert all(not item.isActive() for item in app.workshop_vehicle.pipeline._filtermgr.buffers)


@pytest.mark.parametrize('part,mode', [(0, GameMode.FAST_SLALOM), (1, GameMode.SHORT_BRAKING)])
def test_primary_starts_temporary_budget_vehicle_and_returns_to_same_draft(app, part, mode):
    original = app.workspace_vehicle
    original.save(app.workspace_path)
    saved = app.workspace_path.read_bytes()
    app.workshop_garage.activate(part)
    app.challenge_action('challenge-start')
    assert app.session.phase == Phase.COUNTDOWN and app.session.mode == mode
    assert app.career_panel.root.isHidden()
    assert app.workspace_path.read_bytes() == saved
    app.return_from_test_drive()
    assert app.session.phase == Phase.MENU and app.career_panel.page == 'challenge'
    assert app.workspace_vehicle == original and app.workspace_path.read_bytes() == saved
    app.challenge_action('challenge-back')
    assert not app.workshop_garage.root.isHidden()


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


def test_free_trial_and_budget_return_do_not_leave_stale_workshop_origin(app):
    original = app.workspace_vehicle
    app.workshop_garage.activate(0)
    app.challenge_action('challenge-value', ('front_tire', '65'))
    app.challenge_action('challenge-back')
    app.workshop_garage.activate(2)
    assert app.highway_menu
    app.back_to_modes()
    assert not app.workshop_garage.root.isHidden() and app.workspace_vehicle == original
    app.workshop_garage.activate(5)
    app.choose_slalom_lesson(GameMode.FAST_SLALOM)
    app.start_slalom_lesson()
    assert app.budget_origin == 'slalom'
    app.challenge_action('challenge-back')
    assert app.slalom_menu and app.workshop_garage.root.isHidden()
