"""生涯正常导航、保存边界与暂停返回；合成解锁仅用于界面测试。"""

import time
from dataclasses import replace
from types import SimpleNamespace

import pytest
from panda3d.core import Point3

from application import CoastalDrive
from career import EVENT_BY_ID, CareerProgress
from career_run import CareerResult
from race import GameMode
from session import Phase
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, load_initial_scene=False, output=tmp_path/'game',
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


def test_season_board_preview_follows_focus_and_returns_to_same_event(app, monkeypatch):
    panel = app.career_panel
    assert panel.board_event.id == 'first-drive'
    panel.key('arrow_down')
    assert panel.board_event.id == 'parking'
    assert panel.buttons[panel.primary]['extraArgs'] == ['brief', 'parking']
    panel.key('enter')
    assert panel.page == 'brief' and panel.event_id == 'parking'
    panel.key('escape')
    assert panel.page == 'board' and panel.board_event.id == 'parking'

    app.career_action('board-chapter', 2)
    assert panel.board_event.id == 'coastal-cup'
    assert any(label.getText() == '9 星解锁' for label in panel.labels)
    monkeypatch.setattr(app, 'getAspectRatio', lambda: 4/3)
    panel.resize(4/3)
    assert panel.board_event.id == 'coastal-cup'
    panel.key('enter')
    assert panel.page == 'brief'
    assert not app.career_progress.available(EVENT_BY_ID[panel.event_id])


def test_home_continue_opens_the_event_named_on_the_button(app):
    progress = app.career_progress
    progress.record(CareerResult('first-drive', 8., elapsed=25., finished=True, succeeded=True, stars=3))
    app.career_action('exit')
    index = app.main_menu.continue_index
    assert app.main_menu.subtitles[index].getText() == EVENT_BY_ID['parking'].name
    app.main_menu.select(index)
    app.key_down('enter')
    app.key_up('enter')
    assert app.career_panel.page == 'brief' and app.career_panel.event_id == 'parking'


def test_club_races_follow_normal_focus_and_keep_the_independent_rules(app):
    panel = app.career_panel
    valley, traffic = GameMode.VALLEY_PACE, GameMode.HILL_TRAFFIC
    app.career_action('board-chapter', 1)
    for _ in range(2):
        app.key_down('arrow_down')
        app.key_up('arrow_down')
    assert panel.board_event.id == valley
    panel.key('enter')
    assert panel.page == 'brief' and panel.event_id == valley
    app.start_career_event(valley, stock=True)
    assert app.session.phase == Phase.MENU and panel.page == 'brief'
    panel.key('escape')
    assert panel.page == 'board' and panel.board_event.id == valley

    for event_id in ('first-drive', 'parking'):
        app.career_progress.record(CareerResult(event_id, 8., elapsed=20., finished=True, succeeded=True, stars=3))
    app.open_career(event=panel.board_event)
    panel.key('arrow_down')
    assert panel.board_event.id == traffic
    panel.key('enter')
    assert any('前后净距≥10米' in label.getText() for label in panel.labels)
    panel.key('enter')
    assert app.session.phase == Phase.COUNTDOWN and app.session.mode == traffic
    assert app.session.seed == 23 and app.session.simulation.traffic_count == 12
    assert app.budget_origin == 'club' and app.career_progress.stars == 6
    app.challenge_action('challenge-back')
    assert panel.page == 'brief' and panel.event_id == traffic
    panel.key('escape')
    assert panel.board_event.id == traffic
    app.start_sprint(valley)
    app.challenge_action('challenge-back')
    assert app.sprint_menu and panel.root.isHidden()


def test_gamepad_events_can_navigate_the_season_and_pause_without_driving(app):
    panel = app.career_panel
    app.career_action('exit')
    app.messenger.send('menu-pad-face_a')
    assert panel.page == 'brief' and panel.event_id == 'first-drive'
    app.messenger.send('menu-pad-face_b')
    assert panel.page == 'board' and panel.board_event.id == 'first-drive'
    app.messenger.send('menu-pad-dpad_down')
    app.messenger.send('menu-pad-face_a')
    assert panel.page == 'brief' and panel.event_id == 'parking'
    app.messenger.send('menu-pad-face_a')
    assert app.session.phase == Phase.COUNTDOWN
    app.messenger.send('menu-pad-dpad_left')
    app.messenger.send('menu-pad-face_b')
    assert not app.driving_keys_held and app.session.phase == Phase.COUNTDOWN
    app.messenger.send('menu-pad-start')
    assert app.session.phase == Phase.PAUSED
    app.messenger.send('menu-pad-start')
    assert app.session.phase == Phase.COUNTDOWN


def test_sector_chase_selection_and_practice_use_the_same_valley_route(app):
    from sector_chase import CHASE_COURSES
    from sprint_routes import VALLEY_BRAKING_VERSION

    mode = GameMode.VALLEY_PACE
    app.career_action('chase-menu', mode)
    assert app.career_panel.page == 'board'
    for event_id in ('first-drive', 'parking'):
        app.career_progress.record(
            CareerResult(event_id, 8., elapsed=25., finished=True, succeeded=True, stars=3))
    app.career_action('chase-menu', mode)
    assert app.career_panel.page == 'sector-chase'
    app.career_panel.key('enter')
    assert app.career_panel.page == 'challenge'
    assert not any(button['extraArgs'][0] == 'challenge-auto' for button in app.career_panel.buttons)
    app.challenge_action('challenge-start')
    for _ in range(360):
        app.session.tick()
    assert app.session.highway.snapshot.sprint.rules_version == VALLEY_BRAKING_VERSION
    assert app.session.highway.snapshot.engineering.chase == CHASE_COURSES[mode]
    app.session.finish()
    app.refresh_panel()
    assert app.career_panel.page == 'sector-chase-result'
    app.career_action('chase-practice', 1)
    for _ in range(360):
        app.session.tick()
    assert app.session.highway.snapshot.engineering.practice_sector == 1
    assert app.session.engineering.scores is None
    app.session.finish()
    app.refresh_panel()
    app.career_action('chase-full')
    assert app.session.practice_sector is None
    app.challenge_action('challenge-back')
    assert app.career_panel.page == 'sector-chase'


def test_cup_uses_selected_car_and_resumes_between_app_views(app):
    from challenge_build import BuildDraft
    from season_cup import CUP_LEGS

    for event_id in ('first-drive', 'parking', 'slalom'):
        app.career_progress.record(
            CareerResult(event_id, 8., elapsed=25., finished=True, succeeded=True, stars=3))
    original = app.workspace_vehicle
    original_model = app.vehicle_model_id
    car = 'coastal-hatch'
    app.career_action('cup-menu')
    assert app.career_panel.page == 'season-cup'
    app.career_action('cup-preview', car)
    app.career_panel.key('enter')
    assert app.cup_store.current == ()
    app.career_panel.key('enter')
    assert app.budget_mode == GameMode.TIME_TRIAL
    spec = app.cup_store.specs[GameMode.TIME_TRIAL]
    assert spec.design_id == car and spec.budget == 5000
    app.challenge_action('challenge-start')
    assert app.session.vehicle_config == spec.base_config
    assert app.vehicle_model_id == car and app.workspace_vehicle == original
    for _ in range(360):
        app.session.tick()
    target = spec.targets[-1]
    result = spec.evaluate(BuildDraft(), target.seconds, target.consumption*spec.distance_m/100_000)
    status = replace(app.session.highway.snapshot.engineering, result=result)
    app.session.highway.snapshot = replace(app.session.highway.snapshot, engineering=status)
    app.session.race.snapshot = replace(app.session.race.snapshot, finished=True, invalidated=False)
    app.session.phase = Phase.RESULTS
    app.refresh_panel()
    assert len(app.cup_store.current) == 1
    assert app.career_progress.stars == 9

    app.challenge_action('challenge-back')
    assert app.vehicle_model_id == original_model and app.workspace_vehicle == original
    app.cup_store = None
    app.continue_career()
    assert len(app.cup_store.current) == 1 and app.cup_store.legs == CUP_LEGS
    app.select_cup_car('game-tuned')
    assert app.cup_store.current == ()
    app.select_cup_car(car)
    assert len(app.cup_store.current) == 1
    app.start_cup_leg()
    assert app.budget_mode == GameMode.RIDGE_SPRINT and app.tour_round == 1


def test_brief_stock_start_and_retry_keep_saved_setup(app):
    from challenge_build import BuildDraft
    from challenge_catalog import CAREER_CHALLENGES

    spec = CAREER_CHALLENGES['first-drive']
    draft = BuildDraft(power=1.1)
    assert app.budget_plans.save(spec, draft)
    original = app.budget_plans.path.read_bytes()
    app.career_action('brief', spec.id)
    app.career_panel.key('enter')
    assert app.budget_active and app.session.vehicle_config == spec.configuration(BuildDraft())
    app.challenge_action('challenge-retry')
    assert app.session.vehicle_config == spec.configuration(BuildDraft())
    assert app.budget_plans.path.read_bytes() == original

    app.challenge_action('challenge-back')
    assert app.career_panel.page == 'brief' and app.career_panel.event_id == spec.id
    app.career_action('start', spec.id)
    assert app.career_panel.page == 'challenge' and app.budget_drafts[spec.id] == draft
    app.challenge_action('challenge-start')
    assert app.session.vehicle_config == spec.configuration(draft)


def test_garage_paint_coat_stays_on_paint_and_clears_for_engineering_preview(app):
    app.career_action('garage')
    app.career_action('garage-car', 'game-tuned')
    app.career_action('garage-select')
    view = app.workshop_vehicle
    reflection = view.floor_reflection
    assert len(view.scene.findAllMatches('garage-floor-reflection')) == 1
    paint = view.car_root.find('**/paint')
    assert paint.getShader() is not None
    assert all(part.getShader() is None for part in view.car_root.findAllMatches('**/+GeomNode')
               if part.getName() != 'paint' and part.getName() != 'part-highlight')
    before, vehicle = app.session.current, app.workspace_vehicle
    app.career_action('garage-tab', 'paint')
    assert view.floor_reflection == reflection
    app.career_action('garage-paint', 2)
    assert reflection.isEmpty() and view.floor_reflection != reflection
    assert len(view.scene.findAllMatches('garage-floor-reflection')) == 1
    assert view.car_root.find('**/paint').getShader() is not None
    assert app.session.current == before and app.workspace_vehicle == vehicle
    box = tuple(view.frame['frameSize'])
    view.show(app.career_panel.root, box, app.career_preview, studio=False,
              skin_index=app.career_preview_skin)
    assert view.car_root.find('**/paint').getShader() is None
    assert view.floor_reflection is None
    assert app.session.current == before and app.workspace_vehicle == vehicle


def test_retired_purchase_entry_preserves_historical_ownership_money_and_vehicle(app):
    progress = app.career_progress
    assert progress.save({}, {'sport-front'}, 500)
    original, snapshot = app.workspace_vehicle, app.session.current
    saved = progress.path.read_bytes()
    app.career_action('part', 'sport-front')
    assert app.career_panel.page == 'challenge'
    assert app.budget_mode == progress.recommended().id
    assert progress.credits == 500 and progress.owned == {'sport-front'}
    assert progress.path.read_bytes() == saved
    app.challenge_action('challenge-value', ('power', '110'))
    app.challenge_action('challenge-save')
    app.career_action('restore')
    assert app.career_panel.page == 'challenge'
    assert app.workspace_vehicle == original and app.session.current == snapshot
    assert progress.path.read_bytes() == saved


def test_upgrade_navigation_uses_independent_challenge_plans_and_handles_save_failure(app, tmp_path):
    from challenge_build import BuildDraft
    from challenge_catalog import CAREER_CHALLENGES

    app.career_action('garage')
    app.career_action('garage-tab', 'upgrade')
    assert app.career_panel.page == 'challenge'
    app.challenge_action('challenge-value', ('power', '110'))
    app.challenge_action('challenge-save')
    assert app.budget_plans.load(CAREER_CHALLENGES['first-drive']) == BuildDraft(power=1.1)
    app.open_budget_challenge('parking')
    assert app.budget_drafts['parking'] == BuildDraft()
    app.open_budget_challenge('first-drive')
    assert app.budget_drafts['first-drive'].power == 1.1
    blocked = tmp_path/'file-instead-of-folder'
    blocked.write_text('原文件', encoding='utf-8')
    app.budget_plans.path = blocked/'plans.json'
    app.challenge_action('challenge-save')
    assert '未保存' in app.career_panel.challenge_readouts['notice'].getText()
    assert blocked.read_text(encoding='utf-8') == '原文件'
    assert app.budget_drafts['first-drive'].power == 1.1
    assert app.career_progress.credits == 0 and not app.career_progress.path.exists()


def test_selected_collection_vehicle_is_preserved_when_challenge_uses_its_fixed_car(app):
    from challenge_catalog import CAREER_CHALLENGES

    for event in ('first-drive', 'parking'):
        app.career_progress.record(CareerResult(event, 8., elapsed=25., finished=True, succeeded=True, stars=3))
    app.career_action('garage')
    app.career_action('garage-car', 'gr86-2022-premium-6mt')
    app.career_action('garage-select')
    original = app.workspace_vehicle
    original_bytes = app.workspace_path.read_bytes()
    app.start_career_event('parking')
    assert app.career_panel.page == 'challenge'
    assert app.budget_drafts['parking'].cost == 0
    app.challenge_action('challenge-start')
    assert app.session.vehicle_config == CAREER_CHALLENGES['parking'].base_config
    assert app.workspace_vehicle == original
    app.back_to_menu()
    assert app.workspace_path.read_bytes() == original_bytes and app.workspace_vehicle == original


def test_multiple_car_and_part_rewards_fit_narrow_result_panel(app, monkeypatch):
    progress = app.career_progress
    progress.record(CareerResult('first-drive', 8., elapsed=30., finished=True, succeeded=True, stars=2))
    result = CareerResult('parking', 8., elapsed=21., finished=True, succeeded=True, stars=3)
    award = progress.record(result)
    assert len(award['vehicles']) == 4
    assert sum(name.startswith('零件：') for name in award['unlocked']) == 2
    monkeypatch.setattr(app, 'getAspectRatio', lambda: 4/3)
    panel = app.career_panel
    panel.show_result(progress, result, award)
    rewards = [label for label in panel.labels if any(token in label.getText()
        for token in ('新解锁', '· 新车', '同时解锁：', '运动前轮'))]
    assert len(rewards) == 4
    bounds = [label.getTightBounds(panel.content) for label in rewards]
    for low, high in bounds:
        assert low.z >= 1-828*2/941
    for index, (low, high) in enumerate(bounds):
        for other_low, other_high in bounds[index+1:]:
            assert min(high.z, other_high.z) <= max(low.z, other_low.z)
    only_event = CareerProgress(progress.path.with_name('event-only.json'))
    result = CareerResult('first-drive', 8., elapsed=30., finished=True, succeeded=True, stars=2)
    award = only_event.record(result)
    assert award['unlocked'] == ('穿过海风',)
    panel.show_result(only_event, result, award)
    assert any(label.getText() == '赛事：穿过海风' for label in panel.labels)


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


@pytest.mark.parametrize('event_id,car_id', [('first-drive', 'club-coupe'), ('slalom', 'porsche-930')])
def test_new_car_reward_opens_its_preview_and_returns_to_the_earned_event(app, monkeypatch, event_id, car_id):
    original = app.workspace_vehicle
    if event_id == 'slalom':
        for previous in ('first-drive', 'parking'):
            app.career_progress.record(CareerResult(previous, 8., elapsed=25., finished=True, succeeded=True, stars=3))
    result = CareerResult(event_id, 8., elapsed=25., finished=True, succeeded=True, stars=3)
    award = app.career_progress.record(result)
    monkeypatch.setattr(app, 'getAspectRatio', lambda: 4/3)
    app.career_panel.show_result(app.career_progress, result, award)
    reward_title = next(label for label in app.career_panel.labels if '· 新车' in label.getText())
    low, high = reward_title.getTightBounds(app.career_panel.content)
    assert high.x <= -4/3+(941.*4/3*.031+941.*4/3*.32-24)*2/941
    button = next(button for button in app.career_panel.buttons if button['extraArgs'][0] == 'garage-new')
    button['command'](*button['extraArgs'])
    assert app.career_panel.page == 'garage' and app.career_garage_tab == 'cars'
    assert app.career_preview.design_id == car_id and app.workspace_vehicle == original
    panel = app.career_panel
    for aspect in (4/3, 16/9):
        monkeypatch.setattr(app, 'getAspectRatio', lambda current=aspect: current)
        app.career_action('garage-tab', 'cars')
        app.career_action('garage-car', car_id)
        for label in panel.labels:
            if label.getText() in ('Porsche 911 Turbo', 'BMW 1M Coupé', 'Subaru WRX STI', '远航 GT'):
                low, high = label.getTightBounds(panel.content)
                # 车名标签须严格落在可视画幅与横向车卡范围内，不超出边界。
                margin_x = 941. * aspect * .028 * 2 / 941
                assert low.x >= -aspect + margin_x - 0.01 and high.x <= aspect - margin_x + 0.01
    app.career_action('garage-select')
    assert app.workspace_vehicle.design_id == car_id
    app.career_action('garage-back')
    assert app.career_panel.page == 'brief' and app.career_panel.event_id == event_id


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
            from ui.garage_framing import project_vertices

            points = project_vertices(view.framing_vertices, view.scene, view.camera)
            assert points is not None
            assert (abs(points[:, 0]) <= .91).all() and (abs(points[:, 1]) <= .87).all()
    # 从页尾向上，应进入同一列的颜色应用，而不是跳到左侧车模角度按钮。
    panel.select(len(panel.buttons)-1)
    panel.key('arrow_up')
    assert panel.buttons[panel.selected]['extraArgs'][0] == 'garage-paint-save'


def test_pause_retry_and_return_keep_original_world_until_explicit_restart(app):
    app.career_action('start', 'first-drive')
    app.challenge_action('challenge-start')
    simulation = app.session.simulation
    app.session.pause()
    app._shown_phase = None
    app.key_down('arrow_down')
    app.key_up('arrow_down')
    assert app.career_panel.page == 'challenge-pause'
    app.career_action('resume')
    assert app.session.phase == Phase.COUNTDOWN and app.session.simulation is simulation
    app.return_from_test_drive()
    assert app.career_panel.page == 'challenge' and app.session.phase == Phase.MENU
    assert app.career_progress.stars == 0 and not app.career_progress.path.exists()


def test_driving_hud_reads_current_event_and_pause_button_keeps_the_world(app):
    app.career_active, app.career_event_id = True, 'first-drive'
    app.session.start(mode=GameMode.CAREER, track='endless', career_event_id='first-drive')
    app.refresh_panel()
    app.hud.resize(16/9)
    before, simulation = app.session.current, app.session.simulation
    app.hud.update(before, app.session.race.snapshot, app.session.highway.snapshot,
        track='endless', countdown='', notice='', driving_mode=app.session.driving_mode)
    view = app.hud.career
    assert not view.root.isHidden() and app.hud.status_frame.isHidden()
    assert app.lab_return_button.isHidden()
    assert view.title.getText() == '海岸初驶'
    assert view.goal_text.getText() == '三星目标 27 秒'
    assert view.timer.getText() == '00:00.00'
    assert app.session.current == before
    view.pause['command'](*view.pause['extraArgs'])
    assert app.session.phase == Phase.PAUSED and app.career_panel.page == 'pause'
    assert app.session.simulation is simulation and app.session.current == before
    app.career_action('resume')
    assert app.session.phase == Phase.COUNTDOWN and app.session.simulation is simulation
    assert app.session.current == before


def test_budget_career_countdown_displays_current_joint_gold_target(app):
    app.start_career_event('first-drive', stock=True)
    app.update(SimpleNamespace(cont=None))
    assert app.session.phase == Phase.COUNTDOWN and app.session.highway.snapshot.engineering is None
    assert not app.hud.career.root.isHidden()
    assert app.hud.career.goal_text.getText() == '金牌 ≤22.2s · ≤17.9 L/100km'
    app.challenge_action('challenge-back')
    app.career_action('start', 'first-drive')
    app.challenge_action('challenge-auto')
    app.update(SimpleNamespace(cont=None))
    assert app.session.phase == Phase.COUNTDOWN and app.budget_auto
    assert app.hud.career.goal_text.getText() == '自动试车 · 不计成绩'


def test_driving_hud_event_details_and_two_aspects_do_not_write_or_leave_old_panels(app):
    app.career_active, app.career_event_id = True, 'first-drive'
    app.session.start(mode=GameMode.CAREER, track='endless', career_event_id='first-drive')
    app.refresh_panel()
    before, vehicle = app.session.current, app.workspace_vehicle
    view = app.hud.career
    for event_id in EVENT_BY_ID:
        event = EVENT_BY_ID[event_id]
        result = CareerResult(event_id, 8., position=event.distance*.4, elapsed=65.25,
                              passed=(True, False) if event.kind == 'slalom' else (), stopping_ticks=24)
        highway = replace(app.session.highway.snapshot, career=result)
        app.hud.update(before, app.session.race.snapshot, highway, track='endless', countdown='', notice='')
        assert view.title.getText() == event.name and view.timer.getText() == '01:05.25'
        assert view.primary.getText() == ('1/5' if event.kind == 'slalom' else '120 m' if event.kind == 'parking' else '40%')
        if event.kind == 'parking':
            assert '0.2 秒' in view.detail.getText() and '3 米' in view.goal_text.getText()
        for aspect in (16/9, 4/3):
            app.hud.resize(aspect)
            for card in (view.status, view.goal, view.hints, view.speed_card, view.pause):
                left, right, bottom, top = card['frameSize']
                low = app.aspect2d.getRelativePoint(card, Point3(left, 0, bottom))
                high = app.aspect2d.getRelativePoint(card, Point3(right, 0, top))
                assert -aspect <= low.x < high.x <= aspect
                assert -1 <= low.z < high.z <= 1
            hint_high = app.aspect2d.getRelativePoint(view.hints, Point3(view.hints['frameSize'][1], 0, 0))
            speed_low = app.aspect2d.getRelativePoint(view.speed_card, Point3(0, 0, 0))
            assert hint_high.x < speed_low.x
    assert app.session.current == before and app.workspace_vehicle == vehicle
    assert app.career_progress.credits == 0 and not app.career_progress.path.exists()
    app.hud.update(before, app.session.race.snapshot, replace(highway, career=None),
        track='endless', countdown='', notice='')
    assert view.root.isHidden()
    assert all(not widget.isHidden() for widget in
               (app.hud.status_frame, app.hud.notice_frame, app.hud.speed_frame, app.hud.help_frame))


def test_redesigned_pages_keep_keyboard_actions_and_resize_without_writing_progress(app, monkeypatch):
    panel = app.career_panel
    snapshot, vehicle = app.session.current, app.workspace_vehicle
    # 从列表进入章节栏，切到海岸杯后打开锁定赛事的简报。
    panel.key('arrow_up')
    panel.key('arrow_right')
    assert panel.buttons[panel.selected]['extraArgs'] == ['board-chapter', 2]
    panel.key('enter')
    assert panel.buttons[panel.selected]['extraArgs'] == ['brief', 'coastal-cup']
    panel.key('enter')
    assert panel.page == 'brief' and panel.event_id == 'coastal-cup'
    panel.select(panel.primary)
    panel.key('enter')
    assert app.session.current == snapshot and not app.career_active
    result = CareerResult('first-drive', 8., elapsed=25., finished=True, succeeded=True, stars=3)
    award = app.career_progress.record(result)
    records, credits = dict(app.career_progress.records), app.career_progress.credits
    monkeypatch.setattr(app, 'getAspectRatio', lambda: 4/3)
    for page in ('board', 'brief', 'result', 'pause'):
        if page == 'board':
            panel.show_board(app.career_progress)
        elif page == 'brief':
            panel.show_brief(app.career_progress, EVENT_BY_ID['parking'])
        elif page == 'result':
            panel.show_result(app.career_progress, result, award)
        else:
            panel.show_pause(app.career_progress, EVENT_BY_ID['first-drive'])
        selected = panel.buttons[panel.selected]['extraArgs']
        panel.layout_aspect = 16/9
        panel.resize(4/3)
        assert panel.page == page and panel.layout_aspect == 4/3
        assert panel.buttons[panel.selected]['extraArgs'] == selected
        assert app.session.current == snapshot and app.workspace_vehicle == vehicle
        assert app.career_progress.records == records and app.career_progress.credits == credits
    panel.show_result(app.career_progress, result, award)
    panel.key('enter')
    assert panel.page == 'board' and app.career_progress.credits == credits


def test_result_save_retry_awards_once_and_exposes_the_real_new_car(app, monkeypatch):
    app.career_action('start', 'first-drive')
    result = CareerResult('first-drive', 8., elapsed=25., finished=True, succeeded=True, stars=3)
    app.session.highway.snapshot = replace(app.session.highway.snapshot, career=result)
    save = CareerProgress.save

    def fail(self, records, owned, credits):
        self.notice = '生涯进度未保存：测试文件访问失败。'
        return False

    monkeypatch.setattr(CareerProgress, 'save', fail)
    app.career_action('save')
    assert app.career_progress.credits == 0 and app.career_progress.stars == 0
    assert not app.career_award['saved'] and not app.career_award['vehicles']
    assert app.career_panel.buttons[app.career_panel.primary]['extraArgs'][0] == 'save'
    monkeypatch.setattr(CareerProgress, 'save', save)
    app.career_panel.key('enter')
    assert app.career_panel.page == 'result' and app.career_award['saved']
    assert app.career_progress.credits == 300 and app.career_progress.stars == 3
    assert 'club-coupe' in app.career_award['vehicles']
    app.career_action('save')
    assert app.career_award['credits'] == 0 and not app.career_award['vehicles']
    assert app.career_progress.credits == 300


@pytest.mark.parametrize(('mode', 'budget'), [(GameMode.CAREER, False), (GameMode.FREE_DRIVE, False),
                                            (GameMode.CAREER, True)], ids=('career', 'free', 'budget-career'))
def test_production_loader_holds_independent_countdown_until_ready(tmp_path, monkeypatch, mode, budget):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, independent_clock=True, output=tmp_path/'game')
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    try:
        if budget:
            def load_from_start(*, mode, track, tour=False):
                game._begin_workspace(game._load_road(mode, track), '加载赛事', '测试')

            monkeypatch.setattr(game, 'start_game', load_from_start)
            game.start_career_event('first-drive', stock=True)
            assert game.budget_active and not game.career_active
        else:
            if mode == GameMode.CAREER:
                game.open_career()
                game.career_active, game.career_event_id = True, 'first-drive'
            game._begin_workspace(game._load_road(mode, 'endless'), '加载赛事', '测试')
        for _ in range(12):
            game.taskMgr.step()
            if game.session.phase == Phase.PAUSED:
                break
        assert game._workspace_steps is not None and game.session.phase == Phase.PAUSED
        before = game.session.progress()[0]
        time.sleep(.15)
        assert game.session.progress()[0] == before
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            game.taskMgr.step()
            if game._workspace_steps is None:
                break
        game.taskMgr.remove('drive-update')
        assert game._workspace_steps is None
        assert not game.scene.segment_builds
        assert set(game.session.render_segments()) == game.scene.segment_nodes.keys()
        assert game.session.phase == Phase.COUNTDOWN and game.session.countdown_ticks > 330
        if mode == GameMode.CAREER:
            assert game.session.highway.snapshot.career.elapsed == 0
    finally:
        game.close_game()
