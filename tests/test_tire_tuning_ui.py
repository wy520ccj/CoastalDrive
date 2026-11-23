"""旧配方入口转到独立预算；只在当前挑战临时应用车辆。"""

import pytest

from application import CoastalDrive
from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES
from race import GameMode
from session import Phase
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    original = WorkspaceVehicle('reference-rwd', vehicle_design('reference-rwd').config)
    game = CoastalDrive(smoke=True, output=tmp_path/'game', lab_output=tmp_path/'reports', workspace_vehicle=original)
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    game.back_to_menu()
    yield game
    game.close_game()


def finish(app, workspace):
    for _ in range(60):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


def test_old_tire_link_opens_budget_without_permanent_install_or_keyboard_leaks(app):
    original = app.workspace_vehicle
    app.choose_slalom_lesson(GameMode.FAST_SLALOM)
    app.open_tire_tuning()
    panel = app.career_panel
    assert panel.page == 'challenge' and app.budget_mode == GameMode.FAST_SLALOM
    assert panel.challenge_entries['front_tire'].get() == '50'
    entry = panel.challenge_entries['front_tire']
    app.challenge_action('challenge-value', ('front_tire', '65'))
    entry['focus'] = 1
    app.key_down('escape')
    app.key_up('escape')
    assert panel.page == 'challenge' and not entry['focus']
    app.key_down('escape')
    app.key_up('escape')
    assert panel.root.isHidden() and app.slalom_menu
    assert app.workspace_vehicle == original and not app.workspace_path.exists()


@pytest.mark.parametrize('index,mode', [(0, GameMode.FAST_SLALOM), (1, GameMode.SHORT_BRAKING)])
def test_workshop_cards_use_same_budget_model_and_back_returns_to_workshop(app, index, mode):
    original = app.workspace_vehicle
    app.open_workshop_garage()
    app.workshop_garage.activate(index)
    assert app.career_panel.page == 'challenge' and app.budget_mode == mode
    assert app.budget_origin == 'workshop'
    assert app.career_panel.challenge_data[0] is ROAD_CHALLENGES[mode]
    app.challenge_action('challenge-back')
    assert not app.workshop_garage.root.isHidden() and app.session.phase == Phase.MENU
    assert app.workspace_vehicle == original


def test_budget_save_and_retry_never_use_old_vehicle_backup_or_overwrite_player_file(app):
    original = app.workspace_vehicle
    original.save(app.workspace_path)
    before = app.workspace_path.read_bytes()
    app.choose_braking_lesson(GameMode.SHORT_BRAKING)
    app.open_brake_tuning()
    app.challenge_action('challenge-tab', 2)
    app.challenge_action('challenge-value', ('brake_share', '70'))
    app.challenge_action('challenge-save')
    assert app.budget_plans.load(ROAD_CHALLENGES[GameMode.SHORT_BRAKING]) == BuildDraft(brake_share=.7)
    app.challenge_action('challenge-start')
    assert app.session.vehicle_config.front_brake_share == .7
    app.back_to_menu()
    assert app.workspace_path.read_bytes() == before and app.workspace_vehicle == original


def test_budget_reference_staging_replaces_old_expert_draft_only_after_explicit_request(app):
    original = app.workspace_vehicle
    app.open_expert_parameters()
    finish(app, 'lab')
    app.lab.entries['cg'].enterText('.47')
    app.lab.back_to_game()
    finish(app, 'game')
    app.choose_slalom_lesson(GameMode.FAST_SLALOM)
    app.open_tire_tuning()
    app.challenge_action('challenge-value', ('front_tire', '65'))
    draft = app.budget_drafts[GameMode.FAST_SLALOM]
    app.challenge_action('challenge-lab')
    finish(app, 'lab')
    assert app.lab.engineered_config == ROAD_CHALLENGES[GameMode.FAST_SLALOM].configuration(draft)
    assert app.lab.entries['cg'].get() == ''
    app.lab.back_to_game()
    finish(app, 'game')
    assert app.workspace_vehicle == original and app.session.mode == GameMode.FAST_SLALOM
