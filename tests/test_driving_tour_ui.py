"""预算巡回真实控件与转场；合成终态仅验证呈现/保存，不作为驾驶成绩。"""

from pathlib import Path
from unittest.mock import patch

import pytest
from test_tour_budget import result

from application import CoastalDrive
from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES
from driving_modes import DrivingMode
from driving_tour import LEGS
from race import GameMode
from session import Phase
from tour_budget import BudgetTour


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, load_initial_scene=False, output=tmp_path/'game')
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    yield game
    game.close_game()


def depart(game):
    game.challenge_action('challenge-start')
    while game.session.phase == Phase.COUNTDOWN:
        game.session.countdown_step(360)
    assert game.session.phase == Phase.DRIVING and game.tour_active
    game._shown_phase = None
    game.refresh_panel()


def finish_fixture(game, *, passed=True):
    game.session.highway.snapshot = result(game.session.mode, game.budget_drafts[game.budget_mode], valid=passed)
    game.session.phase = Phase.RESULTS
    game._shown_phase = None
    game.refresh_panel()


def test_independent_budget_three_stage_scoring_and_next_stage_do_not_recount(app):
    original = app.workspace_vehicle, app.session.vehicle_config
    app.back_to_menu()
    app.open_driving_tour()
    assert not app.tour_panel.root.isHidden() and app.main_menu.home.isHidden()
    assert any(item.getText() == '计分轮次' for item in app.tour_panel.labels)
    assert any(item.getText() == '每站用时与油耗同次达铜牌' for item in app.tour_panel.labels)
    app.tour_panel.activate(0)
    assert app.career_panel.page == 'challenge' and app.budget_mode == LEGS[0]
    app.challenge_action('challenge-value', ('power', '110'))
    depart(app)
    finish_fixture(app, passed=False)
    assert not app.tour_store.current
    app.challenge_action('challenge-retry')
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    for index, mode in enumerate(LEGS):
        assert app.session.mode == mode
        finish_fixture(app)
        assert len(app.tour_store.current) == index+1
        app._shown_phase = None
        app.refresh_panel()
        assert len(app.tour_store.current) == index+1 and not app.tour_pending
        assert any(button['extraArgs'][0] == 'tour-next' for button in app.career_panel.buttons)
        if index < 2:
            app.challenge_action('tour-next')
            assert app.career_panel.page == 'challenge' and app.budget_drafts[LEGS[index+1]] == BuildDraft()
            depart(app)
    assert app.tour_store.best == app.tour_store.latest == app.tour_store.current
    assert app.tour_store.current[0].build == BuildDraft(power=1.1)
    app.challenge_action('tour-next')
    assert not app.tour_panel.root.isHidden() and not app.tour_active
    assert app.tour_panel.details[1].getText() == '金牌'
    assert any(item.getText() == '金牌 · 9/9分' for item in app.tour_panel.labels)
    assert (app.workspace_vehicle, app.session.vehicle_config) == original
    assert len(BudgetTour(app.tour_store.path, app.tour_store.variant, app.tour_physics()).current) == 3


def test_historical_stage_practice_uses_recorded_build_without_advancing_active_round(app):
    app.open_driving_tour()
    store, panel = app.tour_store, app.tour_panel
    historical = BuildDraft(front_tire=1.3)
    for mode, build in zip(LEGS, (BuildDraft(), historical, BuildDraft()), strict=True):
        store.accept(mode, store.variant, store.context['physics'], result(mode, build))
    store.restart()
    store.accept(LEGS[0], store.variant, store.context['physics'], result(LEGS[0]))
    before = store.path.read_bytes()
    app.open_driving_tour()
    draft = BuildDraft(power=1.1)
    spec = ROAD_CHALLENGES[LEGS[1]]
    app.budget_drafts[LEGS[1]] = draft
    assert app.budget_plans.save(spec, draft)

    panel.activate(5)
    panel.activate(7)
    panel.activate(12)
    assert app.budget_origin == 'tour-practice' and app.budget_mode == LEGS[1]
    assert app.career_panel.challenge_data[1] == historical
    assert app.career_panel.challenge_entries['front_tire'].get() == '65'
    assert any('单站练习' in label.getText() for label in app.career_panel.labels)
    app.challenge_action('challenge-start')
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    assert app.session.challenge_build == historical and not app.tour_active
    finish_fixture(app)
    assert store.path.read_bytes() == before and len(store.current) == 1
    assert app.budget_plans.load(spec) == draft
    assert not any(button['extraArgs'][0] == 'tour-next' for button in app.career_panel.buttons)
    app.challenge_action('challenge-back')
    assert not panel.root.isHidden() and (panel.page, panel.history) == (1, 1)
    assert app.budget_drafts[LEGS[1]] == draft
    panel.activate(0)
    panel.activate(0)
    assert app.budget_origin == 'tour' and app.budget_mode == LEGS[1]
    assert app.career_panel.challenge_data[1] == draft


def test_practice_can_explicitly_save_to_the_shared_draft(app):
    app.open_driving_tour()
    mode = LEGS[0]
    spec = ROAD_CHALLENGES[mode]
    app.prepare_tour_practice(mode, BuildDraft(power=1.1))
    app.challenge_action('challenge-value', ('power', '105'))
    app.challenge_action('challenge-save')
    app.challenge_action('challenge-value', ('power', '110'))
    app.challenge_action('challenge-back')
    assert app.budget_drafts[mode] == app.budget_plans.load(spec) == BuildDraft(power=1.05)


def test_overview_history_and_menu_pause_keep_current_progress_and_legacy_bytes(app):
    source = Path('tests/data/fixtures/COASTAL-TOUR-01/normal/driving-tour.json')
    legacy_path = app.session.race.scores.path.with_name('driving-tour.json')
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.write_bytes(source.read_bytes())
    legacy_bytes = legacy_path.read_bytes()
    app.open_driving_tour()
    app.start_tour_leg()
    depart(app)
    finish_fixture(app)
    expected = app.tour_store.current
    app.challenge_action('challenge-back')
    assert app.tour_store.current == expected and not app.tour_panel.root.isHidden()
    app.tour_panel.activate(5)
    app.tour_panel.activate(10)
    assert app.tour_panel.page == 1 and app.tour_panel.history == 4
    assert len(app.tour_panel.rows()) == 3
    assert all('牌' in item.getText() for item in app.tour_panel.details)
    app.tour_panel.activate(0)
    assert app.tour_panel.page == 0
    app.tour_panel.key('escape')
    assert app.sprint_menu and app.panel_selection == 5
    app.open_driving_tour()
    app.start_tour_leg()
    assert app.budget_mode == LEGS[1] and app.career_panel.page == 'challenge'
    app.start_game(mode=GameMode.FREE_DRIVE)
    assert not app.tour_active and app.tour_store.current == expected
    assert legacy_path.read_bytes() == legacy_bytes


def test_save_failure_has_retry_and_retains_old_saved_round(app):
    app.open_driving_tour()
    app.start_tour_leg()
    depart(app)
    finish_fixture(app)
    path, saved = app.tour_store.path, app.tour_store.path.read_bytes()
    app.challenge_action('tour-next')
    depart(app)
    real_replace = Path.replace

    def fail_tour(file, destination):
        if destination == path:
            raise OSError('巡回测试只读')
        return real_replace(file, destination)

    with patch.object(Path, 'replace', fail_tour):
        finish_fixture(app)
    assert app.tour_store.unsaved and len(app.tour_store.current) == 2 and path.read_bytes() == saved
    button = next(item for item in app.career_panel.buttons if item['extraArgs'][0] == 'tour-save')
    button['command'](*button['extraArgs'])
    assert not app.tour_store.unsaved and path.read_bytes() != saved
    assert not any(item['extraArgs'][0] == 'tour-save' for item in app.career_panel.buttons)
    app.challenge_action('challenge-back')
    previous, saved = app.tour_store.current, path.read_bytes()
    with patch.object(Path, 'replace', fail_tour):
        app.tour_panel.activate(1)
    assert not app.tour_panel.root.isHidden() and app.career_panel.root.isHidden()
    assert app.tour_store.current == previous and path.read_bytes() == saved
    assert '原进度保留' in app.tour_panel.notice.getText() and not app.tour_store.unsaved
    app.tour_panel.activate(0)
    assert app.budget_mode == LEGS[2] and app.career_panel.page == 'challenge'


def test_reference_lab_roundtrip_keeps_tour_leg_and_budget_plan(app):
    app.open_driving_tour()
    app.start_tour_leg()
    app.challenge_action('challenge-value', ('power', '110'))
    original = app.workspace_vehicle
    app.challenge_action('challenge-lab')
    for _ in range(60):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == 'lab' and not app.tour_active
    app.lab.back_to_game()
    for _ in range(60):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == 'game' and app.workspace_vehicle == original
    assert app.tour_active and app.tour_pending and app.session.mode == LEGS[0]
    assert app.budget_drafts[LEGS[0]] == BuildDraft(power=1.1)


def test_changed_input_group_does_not_credit_original_round(app):
    app.open_driving_tour()
    app.start_tour_leg()
    app.session.set_driving_mode(DrivingMode.SIMULATION)
    depart(app)
    finish_fixture(app)
    assert not app.tour_store.current
    assert '条件改变' in app.tour_status
    assert any('条件改变' in label.getText() for label in app.career_panel.labels)


def test_switching_driving_mode_keeps_unsaved_round_in_its_own_group(app):
    app.open_driving_tour()
    store = app.tour_store
    with patch.object(Path, 'replace', side_effect=OSError('巡回测试只读')):
        store.accept(LEGS[0], store.variant, store.context['physics'], result(LEGS[0]))
    pending = store.current
    assert pending and store.unsaved and not store.path.exists()

    app.tour_panel.key('escape')
    app.set_driving_mode(DrivingMode.SIMULATION)
    app.open_driving_tour()
    assert app.tour_store.key != store.key and not app.tour_store.current
    app.tour_panel.key('escape')
    app.set_driving_mode(DrivingMode.GAME)
    app.open_driving_tour()
    assert app.tour_store is store and store.current == pending and store.unsaved
    app.tour_panel.activate(3)
    assert not store.unsaved and BudgetTour(store.path, store.variant, store.context['physics']).current == pending
