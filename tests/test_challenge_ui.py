"""预算面板实际回调、费用/输入状态及同车赛事往返。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from career_run import CareerResult
from challenge_build import BuildDraft
from challenge_catalog import CAREER_CHALLENGES, ROAD_CHALLENGES, SPRINT_CHALLENGES, course_gates
from challenge_presets import road_presets
from challenge_run import ChallengeStatus, EnergySplit
from controls import ConstantController
from fuel import FuelState
from race import GameMode
from road_test_driver import TRIAL_POLICIES, RoadTestDriver
from session import Phase
from trial_references import TrialReferences
from ui.challenge_layout import field_values, formatted, read_value
from ui.garage_layout import ORANGE
from vehicle_designs import vehicle_design
from vehicle_state import Control
from vehicle_workspace import WorkspaceVehicle


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, load_initial_scene=False, output=tmp_path/'game',
        workspace_vehicle=WorkspaceVehicle('reference-rwd', vehicle_design('reference-rwd').config))
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    yield game
    game.close_game()


def test_menu_opens_fixed_original_parameter_editor_and_prices_follow_real_draft(app):
    mode = GameMode.BEND_SPRINT
    original = app.workspace_vehicle
    app.start_sprint(mode)
    panel = app.career_panel
    assert app.session.phase == Phase.MENU and panel.page == 'challenge'
    assert set(panel.challenge_entries) == {'power', 'mass', 'drag', 'final_drive'}
    app.challenge_action('challenge-value', ('power', '110'))
    assert app.budget_drafts[mode] == BuildDraft(power=1.1)
    assert '2250' in panel.challenge_readouts['budget'].getText()
    assert panel.challenge_entries['power'].get() == '110'
    app.challenge_action('challenge-value', ('power', '300'))
    assert app.budget_drafts[mode].power == 1.1
    assert '范围' in panel.challenge_readouts['notice'].getText()
    assert app.workspace_vehicle == original


def test_road_reference_builds_replace_draft_and_feed_normal_start(app):
    mode = GameMode.BEND_SPRINT
    spec = SPRINT_CHALLENGES[mode]
    app.start_sprint(mode)
    panel = app.career_panel

    def choose(index):
        args = ['challenge-preset', index]
        panel.select(next(i for i, button in enumerate(panel.buttons) if button['extraArgs'] == args))
        panel.key('enter')
        assert panel.buttons[panel.selected]['extraArgs'] == args

    app.challenge_action('challenge-value', ('power', '110'))
    choose(0)
    assert app.budget_drafts[mode] == BuildDraft(front_tire=1.3)
    assert app.budget_tab == 1 and panel.challenge_entries['front_tire'].get() == '65'
    assert panel.challenge_readouts['used'].getText() == '2000'
    assert panel.challenge_readouts['preset-title'].getText() == '参考方案 · 实跑 92.2 s / 19.44 L/100km'
    assert tuple(panel.challenge_readouts['preset:0'].getColor()) == pytest.approx(ORANGE, abs=.001)
    app.challenge_action('challenge-step', ('front_tire', -1))
    assert tuple(panel.challenge_readouts['preset:0'].getColor()) != pytest.approx(ORANGE, abs=.001)
    assert panel.challenge_readouts['preset-title'].getText() == '参考方案'
    choose(2)
    assert app.budget_drafts[mode] == BuildDraft()
    assert panel.challenge_readouts['preset-title'].getText() == '参考方案 · 实跑 93.9 s / 19.29 L/100km'
    choose(1)
    draft = BuildDraft(mass=.96, drag=.95)
    assert app.budget_drafts[mode] == draft
    assert app.budget_tab == 0 and panel.challenge_entries['mass'].get() == '1152'
    assert panel.challenge_readouts['used'].getText() == '4780'
    assert panel.challenge_readouts['preset-title'].getText() == '参考方案 · 实跑 93.8 s / 18.95 L/100km'
    assert app.budget_plans.load(spec) == BuildDraft()
    app.challenge_action('challenge-start')
    assert app.session.phase == Phase.COUNTDOWN
    assert app.session.vehicle_config == spec.configuration(draft)
    assert app.budget_plans.load(spec) == draft


def test_reference_builds_only_match_their_supported_road_geometry():
    for mode, costs in ((GameMode.BEND_SPRINT, (2000, 4780, 0)),
                        (GameMode.VALLEY_PACE, (1840, 4780, 0)),
                        (GameMode.RIDGE_SPRINT, (2000, 3500, 0)),
                        (GameMode.TIME_TRIAL, (2000, 4780, 0)), (GameMode.SAFE_OVERTAKE, (0, 4780, 3940)),
                        (GameMode.HILL_TRAFFIC, (3940, 4780, 5000))):
        spec = ROAD_CHALLENGES[mode]
        if mode == GameMode.RIDGE_SPRINT:
            v4 = road_presets(replace(spec, road_shape='budget-ridge-suspension'))
            assert tuple(draft.cost for _, draft, _ in v4) == (0, 2000, 4780)
            assert all(draft.springs == 1. for _, draft, _ in v4)
            spec = replace(spec, road_shape='budget-ridge-long-waves')
        choices = road_presets(spec)
        assert tuple(draft.cost for _, draft, _ in choices) == costs
        for _, draft, _ in choices:
            assert (spec.configuration(draft) == spec.base_config) == (not draft.changed())
    assert not road_presets(ROAD_CHALLENGES[GameMode.DISTANCE_CHALLENGE])


def test_career_sprint_presets_fit_each_budget_and_specialists_remain_manual():
    for event, spec in CAREER_CHALLENGES.items():
        choices = road_presets(spec)
        if spec.assessment == 'road':
            assert len(choices) == (2 if event == 'first-drive' else 3) and spec.id in TRIAL_POLICIES
            for _, draft, _ in choices:
                assert draft.cost <= spec.budget
                spec.configuration(draft)
        else:
            assert not choices and event not in TRIAL_POLICIES


def test_career_automatic_trial_uses_event_setup_without_saving_progress(app):
    event = 'first-drive'
    spec = CAREER_CHALLENGES[event]
    panel = app.career_panel
    app.start_career_event(event)
    for args in (['challenge-preset', 1], ['challenge-auto']):
        button = next(button for button in panel.buttons if button['extraArgs'][:len(args)] == args)
        button['command'](*button['extraArgs'])
    assert app.session.mode == GameMode.CAREER and app.session.career_event_id == event
    assert app.session.vehicle_config == spec.configuration(BuildDraft(final_drive=1.075))
    assert isinstance(app.session.controller, RoadTestDriver)
    assert app.session.controller.policy['target_kph'] == 80.
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    app.session.tick()
    assert app.session.last_control.throttle > 0.
    app.session.finish()
    app.refresh_panel()
    assert panel.page == 'challenge-result' and app.career_award is None
    assert not app.session.highway.snapshot.engineering.result.official
    assert not app.career_progress.path.exists() and not app.budget_plans.path.exists()
    app.challenge_action('challenge-adjust')
    app.challenge_action('challenge-start')
    assert app.session.controller is app.session.keyboard
    assert app.budget_plans.load(spec) == BuildDraft(final_drive=1.075)


def test_automatic_tour_trial_leaves_draft_unsaved_and_can_return_to_player_driving(app):
    app.open_driving_tour()
    app.start_tour_leg()
    mode = app.budget_mode
    spec = ROAD_CHALLENGES[mode]
    panel = app.career_panel
    panel.challenge_entries['power'].enterText('110')
    auto = next(button for button in panel.buttons if button['extraArgs'][0] == 'challenge-auto')
    auto['command'](*auto['extraArgs'])
    assert app.budget_auto and not app.tour_active and not app.tour_pending
    assert app.session.challenge_build == BuildDraft(power=1.1)
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    for _ in range(18):
        app.session.tick()
    assert app.session.last_control.throttle > 0 and app.session.current.player.speed > 0.
    app.session.finish()
    app._shown_phase = None
    app.refresh_panel()
    assert not app.session.highway.snapshot.engineering.result.official
    assert not app.tour_store.current and app.budget_plans.load(spec) == BuildDraft()
    app.challenge_action('challenge-retry')
    assert app.budget_auto and app.session.controller is not app.session.keyboard
    app.session.pause()
    app._shown_phase = None
    app.refresh_panel()
    app.challenge_action('challenge-adjust')
    assert not app.budget_auto and panel.page == 'challenge'
    app.challenge_action('challenge-start')
    assert app.tour_active and app.session.controller is app.session.keyboard
    assert app.budget_plans.load(spec) == BuildDraft(power=1.1)


def test_automatic_comparison_keeps_other_build_across_retries(app):
    mode = GameMode.BEND_SPRINT
    spec = SPRINT_CHALLENGES[mode]
    first = BuildDraft(front_tire=1.3)
    second = BuildDraft(mass=.96, drag=.95)
    panel = app.career_panel

    def show(draft, seconds, litres, *, valid=True):
        result = spec.evaluate(draft, seconds, litres, valid=valid)
        result = replace(result, official=False, medal='', next_target=None,
                         notice='自动试车 · 已完成，不计成绩')
        splits = ()
        if valid:
            splits = tuple(EnergySplit(gate, seconds*gate/spec.distance_m, litres*gate/spec.distance_m)
                           for gate in course_gates(mode)[:-1])+(EnergySplit(spec.distance_m, seconds, litres),)
        status = ChallengeStatus(spec.id, spec.name, spec.budget, result.cost, seconds, spec.distance_m,
                                 litres, result.consumption, splits, result)
        app.show_budget_result(status)
        return status

    app.start_sprint(mode)
    app.budget_drafts[mode] = first
    app.career_panel.update_challenge(first)
    app.challenge_action('challenge-auto')
    first_status = show(first, 92., .35)
    assert panel.challenge_result_data[1].reference_result is None
    assert app.auto_trial_saved
    app.auto_trials = TrialReferences(app.auto_trials.folder)
    app.challenge_action('challenge-adjust')
    app.budget_drafts[mode] = second
    app.career_panel.update_challenge(second)
    app.challenge_action('challenge-auto')
    show(second, 25., .05, valid=False)
    app.challenge_action('challenge-retry')
    assert app.auto_trial_reference.result == first_status.result
    second_status = show(second, 94., .34)
    app.show_budget_result(second_status)
    assert panel.challenge_result_data[1].reference_result == first_status.result
    app.auto_trials = TrialReferences(app.auto_trials.folder)
    app.challenge_action('challenge-retry')
    assert app.auto_trial_reference.result == first_status.result
    show(second, 94., .34)
    texts = {label.getText() for label in panel.labels}
    assert {'前轮响应', '较对照  +2.0 s · -0.56 L/100km', '路段 · 括号较对照', '23.5 (+0.5)'} <= texts
    restore = next(button for button in panel.buttons if button['extraArgs'] == ['challenge-apply-reference', first])
    restore['command'](*restore['extraArgs'])
    assert app.budget_drafts[mode] == first and app.budget_plans.load(spec) == BuildDraft()


def test_typed_parameter_is_used_when_starting_without_enter(app):
    mode = GameMode.BEND_SPRINT
    app.start_sprint(mode)
    entry = app.career_panel.challenge_entries['power']
    entry['focus'] = 1
    entry.enterText('110')
    app.challenge_action('challenge-start')
    assert app.budget_drafts[mode] == BuildDraft(power=1.1)
    assert app.session.vehicle_config == SPRINT_CHALLENGES[mode].configuration(BuildDraft(power=1.1))


def test_invalid_typed_parameter_cannot_start_save_or_disappear_on_tab_change(app):
    mode = GameMode.BEND_SPRINT
    app.start_sprint(mode)
    panel = app.career_panel
    panel.challenge_entries['power'].enterText('121')
    for action, value in (('challenge-start', None), ('challenge-save', None), ('challenge-tab', 1)):
        app.challenge_action(action, value)
        assert app.session.phase == Phase.MENU and panel.page == 'challenge'
        assert app.budget_drafts[mode] == BuildDraft()
        assert panel.challenge_entries['power'].get() == '121'
        assert '范围' in panel.challenge_readouts['notice'].getText()
        assert not app.budget_plans.path.exists()
    panel.challenge_sliders['power']['value'] = 110
    app.taskMgr.step()
    assert app.budget_drafts[mode] == BuildDraft(power=1.1)
    assert panel.challenge_entries['power'].get() == '110'


def test_numeric_shortcut_replaces_whole_value_and_escape_keeps_committed_draft(app):
    app.start_sprint(GameMode.BEND_SPRINT)
    panel = app.career_panel
    entry = panel.challenge_entries['power']
    entry['focus'] = 1
    app.messenger.send('control-a')
    app.messenger.send('control-a-up')
    assert entry.get() == '' and entry['focus']
    assert app.budget_drafts[GameMode.BEND_SPRINT] == BuildDraft()
    entry.enterText('110')
    panel.key('enter')
    assert app.budget_drafts[GameMode.BEND_SPRINT] == BuildDraft(power=1.1)
    entry['focus'] = 1
    app.messenger.send('control-a')
    app.messenger.send('control-a-up')
    panel.key('escape')
    assert entry.get() == '110' and not entry['focus']
    assert panel.page == 'challenge'


def test_pending_numbers_survive_resize_save_together_and_steps_use_typed_value(app):
    mode = GameMode.BEND_SPRINT
    app.start_sprint(mode)
    panel = app.career_panel
    panel.challenge_entries['power'].enterText('110')
    panel.challenge_entries['mass'].enterText(str(SPRINT_CHALLENGES[mode].base_config.mass*.96))
    panel.resize(4/3)
    assert panel.challenge_entries['power'].get() == '110'
    app.challenge_action('challenge-step', ('power', 1))
    expected = BuildDraft(power=1.105, mass=.96)
    assert app.budget_drafts[mode] == expected
    app.challenge_action('challenge-save')
    assert app.budget_plans.load(SPRINT_CHALLENGES[mode]) == expected
    entry = panel.challenge_entries['power']
    entry['focus'] = 1
    entry.enterText('bad')
    panel.key('enter')
    assert entry['focus'] and entry.get() == 'bad'
    assert '数字' in panel.challenge_readouts['notice'].getText()
    panel.key('escape')
    assert not entry['focus'] and entry.get() == '110.5'
    assert app.budget_drafts[mode] == expected


def test_coastal_menu_budget_start_pause_retry_and_return_keep_original_vehicle(app):
    original, config = app.workspace_vehicle, app.session.vehicle_config
    app.back_to_menu()
    app.main_menu.actions[0]()
    assert app.career_panel.page == 'challenge' and app.budget_mode == GameMode.TIME_TRIAL
    choice = next(button for button in app.career_panel.buttons if button['extraArgs'] == ['challenge-preset', 0])
    choice['command'](*choice['extraArgs'])
    draft = BuildDraft(front_tire=1.3, brake_share=.65, antiroll_share=.4)
    app.challenge_action('challenge-start')
    assert app.session.simulation.track == 'coastal' and app.session.mode == GameMode.TIME_TRIAL
    assert app.session.challenge_spec == ROAD_CHALLENGES[GameMode.TIME_TRIAL]
    assert app.session.vehicle_config == app.session.challenge_spec.configuration(draft)
    app.session.pause()
    app._shown_phase = None
    app.refresh_panel()
    assert app.career_panel.page == 'challenge-pause'
    app.challenge_action('challenge-retry')
    assert app.session.mode == GameMode.TIME_TRIAL and app.session.simulation.track == 'coastal'
    assert app.session.challenge_build == draft
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    app.session.tick()
    lap, highway = app.session.race.snapshot, app.session.highway.snapshot
    gates = course_gates(GameMode.TIME_TRIAL)[:-1]
    splits = tuple(EnergySplit(distance, 10.*index, .03*index) for index, distance in enumerate(gates, 1))
    reference = tuple(replace(split, seconds=split.seconds*1.1) for split in splits)
    highway = replace(highway, engineering=replace(highway.engineering, splits=splits, reference_splits=reference))
    app.hud.update(app.session.current, replace(lap, checkpoints=4), highway,
                   track='coastal', countdown='', notice='')
    hud = app.hud.coastal
    assert '分段 4 / 5' in hud.checkpoints.getText()
    assert '检查点已齐，驶过终点线' in hud.notice.getText() and '本段 -1.0s' in hud.notice.getText()
    app.session.reset_player()
    invalid_lap = app.session.race.snapshot
    assert invalid_lap.invalidated and invalid_lap.invalid_reason == '车辆复位'
    app.hud.update(app.session.current, invalid_lap, highway, track='coastal', countdown='', notice='')
    assert hud.cumulative.getText() == '本圈无效' and hud.goal.getText() == '车辆复位'
    assert hud.notice_frame.isHidden()
    app.session.finish()
    app._shown_phase = None
    app.refresh_panel()
    labels = [label.getText() for label in app.career_panel.labels]
    assert app.career_panel.page == 'challenge-result' and '检查点' in labels and '车辆复位' in labels
    app.challenge_action('challenge-adjust')
    assert app.career_panel.page == 'challenge'
    assert app.workspace_vehicle == original and app.session.vehicle_config == config
    app.challenge_action('challenge-back')
    assert app.career_panel.root.isHidden() and not app.main_menu.home.isHidden()


def test_tabs_free_setup_single_reset_keyboard_and_overbudget_trial_label(app):
    mode = GameMode.BEND_SPRINT
    app.start_sprint(mode)
    app.challenge_action('challenge-value', ('power', '120'))
    assert app.career_panel.challenge_readouts['start']['text'] == '试验驾驶'
    assert '超出 1000' in app.career_panel.challenge_readouts['budget'].getText()
    app.challenge_action('challenge-tab', 2)
    app.challenge_action('challenge-value', ('brake_share', '70'))
    assert app.budget_drafts[mode].cost == 6000
    entry = app.career_panel.challenge_entries['brake_share']
    entry['focus'] = 1
    app.career_panel.key('arrow_down')
    assert app.budget_drafts[mode].brake_share == .69
    app.career_panel.key('escape')
    assert app.career_panel.page == 'challenge' and not entry['focus']
    app.challenge_action('challenge-reset', 'power')
    assert app.budget_drafts[mode].power == 1. and app.budget_drafts[mode].cost == 0
    app.challenge_action('challenge-reset', None)
    assert app.budget_drafts[mode] == BuildDraft()


def test_save_load_start_authoritative_hardware_then_adjust_restores_original(app):
    mode = GameMode.BEND_SPRINT
    original, config = app.workspace_vehicle, app.session.vehicle_config
    app.start_sprint(mode)
    app.challenge_action('challenge-value', ('power', '110'))
    app.challenge_action('challenge-save')
    assert app.budget_plans.load(SPRINT_CHALLENGES[mode]) == BuildDraft(power=1.1)
    app.challenge_action('challenge-start')
    assert app.budget_active and app.session.mode == mode
    assert app.session.vehicle_config == SPRINT_CHALLENGES[mode].configuration(BuildDraft(power=1.1))
    # 本测试只推进真实短启动；不据此声称完成路线或获得奖牌。
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    app.session.set_controller(ConstantController(Control(throttle=.3)))
    for _ in range(8):
        app.session.tick()
    app.session.finish()
    app._shown_phase = None
    app.refresh_panel()
    assert app.career_panel.page == 'challenge-result'
    assert not app.session.highway.snapshot.engineering.result.official
    app.challenge_action('challenge-adjust')
    assert app.career_panel.page == 'challenge' and app.budget_drafts[mode].power == 1.1
    assert app.workspace_vehicle == original and app.session.vehicle_config == config


@pytest.mark.parametrize('seconds, medal, time_delta', [(92.7, '金', '-0.7'), (96.1, '银', '+2.7')])
def test_result_table_uses_same_run_metrics_and_marks_missing_grade_honestly(app, seconds, medal, time_delta):
    mode = GameMode.BEND_SPRINT
    app.start_sprint(mode)
    graded = SPRINT_CHALLENGES[mode]
    gold = graded.evaluate(BuildDraft(front_tire=1.3), seconds, .3501)
    graded_status = ChallengeStatus(graded.id, graded.name, graded.budget, gold.cost, gold.seconds, graded.distance_m,
                                    gold.litres, gold.consumption, (), gold,
                                    record_updates=(('完赛', 'economy'), (medal, 'economy')))
    app.career_panel.show_challenge_result(app.career_progress, graded, graded_status)
    assert all('较最快完赛' not in label.getText() for label in app.career_panel.labels)
    fastest = graded.evaluate(BuildDraft(), 93.4, .3393)
    app.career_panel.show_challenge_result(app.career_progress, graded, replace(graded_status, reference_result=fastest))
    texts = '\n'.join(label.getText() for label in app.career_panel.labels)
    assert medal+'牌完成' in texts and '金牌目标' in texts
    assert f'新{medal}牌纪录 · 最省油' in texts
    assert f'较最快完赛  {time_delta} s · +0.6 L/100km' in texts
    if medal == '银':
        assert '用时需缩短0.5秒' in texts
    spec = replace(SPRINT_CHALLENGES[mode], targets=(), provisional=False)
    result = spec.evaluate(BuildDraft(power=1.1), 60., .126)
    status = ChallengeStatus(spec.id, spec.name, spec.budget, result.cost, 60., spec.distance_m,
                             .126, result.consumption,
                             (EnergySplit(spec.distance_m, 60., .126),), result,
                             record_updates=(('完赛', 'cheapest'),))
    app.career_panel.show_challenge_result(app.career_progress, spec, status)
    texts = '\n'.join(label.getText() for label in app.career_panel.labels)
    assert '试跑完成' in texts and '目标待标定' in texts and '2250' in texts
    assert '新个人纪录 · 最低费用' in texts
    assert '金牌完成' not in texts
    reference = spec.evaluate(BuildDraft(), 64., .144)
    app.career_panel.show_challenge_result(app.career_progress, spec,
                                         replace(status, reference_result=reference))
    texts = '\n'.join(label.getText() for label in app.career_panel.labels)
    assert '最快完赛' in texts and '64.0' in texts and '8.0' in texts
    assert '目标待标定' not in texts and '金牌完成' not in texts
    app.career_panel.resize(4/3)
    assert app.career_panel.page == 'challenge-result'


def test_result_restores_frozen_reference_build_without_saving_or_starting(app):
    mode = GameMode.BEND_SPRINT
    spec = SPRINT_CHALLENGES[mode]
    original = app.workspace_vehicle
    app.start_sprint(mode)
    reference_draft = BuildDraft(front_tire=1.3, brake_share=.65, antiroll_share=.4)
    reference = spec.evaluate(reference_draft, 92.15, .34985)
    current = BuildDraft(mass=.96, drag=.95)
    app.budget_drafts[mode] = current
    app.career_panel.update_challenge(current)
    app.challenge_action('challenge-start')
    app.session.challenge_scores().record(reference)
    app.challenge_action('challenge-retry')
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    assert app.session.engineering.reference_result == reference
    app.session.finish()
    app._shown_phase = None
    app.refresh_panel()
    panel = app.career_panel
    assert panel.page == 'challenge-result'
    args = ['challenge-apply-reference', reference_draft]
    panel.select(next(index for index, button in enumerate(panel.buttons) if button['extraArgs'] == args))
    panel.key('enter')
    assert app.session.phase == Phase.MENU and panel.page == 'challenge'
    assert app.budget_drafts[mode] == reference_draft and app.workspace_vehicle == original
    assert panel.challenge_readouts['notice'].getText() == '已套用对照方案'
    assert app.budget_plans.load(spec) == current
    app.challenge_action('challenge-start')
    assert app.session.vehicle_config == spec.configuration(reference_draft)
    assert app.budget_plans.load(spec) == reference_draft


def test_valley_result_compares_each_segment_and_keeps_partial_runs_unranked(app):
    mode = GameMode.VALLEY_PACE
    app.start_sprint(mode)
    spec = SPRINT_CHALLENGES[mode]
    reference_splits = (EnergySplit(375., 12., .050), EnergySplit(400., 20., .070),
                        EnergySplit(650., 43., .120), EnergySplit(1000., 60., .200))
    splits = (EnergySplit(375., 11., .055), EnergySplit(400., 19.5, .069),
              EnergySplit(650., 42., .1115), EnergySplit(1000., 59., .200))
    reference = spec.evaluate(BuildDraft(), 60., .200)
    result = spec.evaluate(BuildDraft(brakes=1.25), 59., .200)
    status = ChallengeStatus(spec.id, spec.name, spec.budget, result.cost, result.seconds, spec.distance_m,
                             result.litres, result.consumption, splits, result,
                             reference_splits=reference_splits, reference_result=reference)
    panel = app.career_panel
    panel.show_challenge_result(app.career_progress, spec, status)
    labels = {label.getText() for label in panel.labels}
    assert {'减速区', '限速带', '本段用时 / s', '本段 L/100km', '8.5 (+0.5)', '56.0 (-24.0)',
            '22.5 (-0.5)', '17.0 (-3.0)'} <= labels

    failed = spec.evaluate(result.build, 23., .080, valid=False, reason='限速带超速')
    panel.show_challenge_result(app.career_progress, spec, replace(status, result=failed, splits=splits[:2]))
    labels = {label.getText() for label in panel.labels}
    assert {'限速带超速', '减速区', '8.5', '56.0'} <= labels
    assert not {'限速带', '8.5 (+0.5)', '56.0 (-24.0)'} & labels


def test_career_specialist_results_use_parking_position_and_actual_gate_outcomes(app):
    cases = (
        (CareerResult('parking', 0., position=206., finished=True, succeeded=True), 6.,
         {'停过 6.0 米 · 同速可稍提前制动', '停车区中心', '206.0'}),
        (CareerResult('parking', 0., position=194., finished=True, succeeded=True), 6.,
         {'停早 6.0 米 · 同速可稍推迟制动', '停车区中心', '194.0'}),
        (CareerResult('slalom', 0., position=420., finished=True, succeeded=True,
                      passed=(True, False, True, True, True)), 4,
         {'第 2 门先松油，车身摆正后再通过', '漏门', '第5门', '420'}),
        (CareerResult('slalom', 0., position=290., finished=True, passed=(True, False, True)), 2,
         {'驶离赛道', '漏门', '未到达', '第5门'}),
    )
    panel = app.career_panel
    for run, metric, expected in cases:
        spec = CAREER_CHALLENGES[run.event_id]
        result = spec.evaluate(BuildDraft(), 28., .07, valid=run.succeeded, reason='驶离赛道', metric_value=metric)
        status = ChallengeStatus(spec.id, spec.name, spec.budget, result.cost, result.seconds, run.position,
                                 result.litres, result.consumption, (), result)
        app.session.highway.snapshot = replace(app.session.highway.snapshot, career=run)
        panel.show_challenge_result(app.career_progress, spec, status)
        assert expected <= {label.getText() for label in panel.labels}


def test_new_step_buttons_slider_and_reset_keep_quote_and_configuration_in_sync(app):
    mode = GameMode.BEND_SPRINT
    app.start_sprint(mode)
    app.challenge_action('challenge-tab', 1)
    panel = app.career_panel
    plus = next(button for button in panel.buttons
                if button['extraArgs'] == ['challenge-step', ('front_tire', 1)])
    plus['command'](*plus['extraArgs'])
    assert panel.challenge_entries['front_tire'].get() == '50.5'
    assert app.budget_drafts[mode].front_tire == 1.01
    panel.challenge_sliders['front_tire']['value'] = 57.5
    app.taskMgr.step()
    assert app.budget_drafts[mode].front_tire == 1.15
    assert panel.challenge_entries['front_tire'].get() == '57.5'
    assert panel.challenge_readouts['cost:front_tire'].getText() == '750'
    app.challenge_action('challenge-reset', 'front_tire')
    assert panel.challenge_entries['front_tire'].get() == '50'
    assert app.budget_drafts[mode].cost == 0


def test_displayed_endpoint_roundtrips_to_real_physical_limits():
    spec = SPRINT_CHALLENGES[GameMode.BEND_SPRINT]
    for key in ('drag', 'mass', 'final_drive', 'power', 'front_tire', 'brake_share'):
        _, _, low, high, _ = field_values(spec, BuildDraft(), key)
        for endpoint in (low, high):
            value = read_value(spec, BuildDraft(), key, formatted(key, endpoint))
            changed = replace(BuildDraft(), **{key: value})
            spec.configuration(changed)
    # 实际试玩发现两套不同报价均显示0.652；应能看出具体参数差别。
    stock = spec.base_config.drag_coefficient*spec.base_config.frontal_area
    exact = BuildDraft(mass=.96, drag=read_value(spec, BuildDraft(), 'drag', '.652'))
    approximate = BuildDraft(mass=.96, drag=round(.652/.686, 10))
    assert exact.cost == 4740 and approximate.cost == 4760
    assert formatted('drag', exact.drag*stock) != formatted('drag', approximate.drag*stock)


def test_budget_hud_uses_real_allowance_handles_missing_sensor_and_restores_coastal_layout(app):
    from challenge_rules import MedalTarget
    from race import RaceSnapshot

    spec = SPRINT_CHALLENGES[GameMode.BEND_SPRINT]
    status = ChallengeStatus(spec.id, spec.name, spec.budget, 3750, 42.73, 1200., .0816, 6.8,
        (EnergySplit(450., 14., .0324), EnergySplit(900., 29., .0657)),
        targets=(MedalTarget('铜', 90., 10.), MedalTarget('银', 75., 8.2), MedalTarget('金', 65., 7.)),
        distance_m=1800., reference_splits=(EnergySplit(450., 14., .0324), EnergySplit(900., 30., .0639)))
    app.hud.resize(app.getAspectRatio())
    road = replace(app.session.highway.snapshot, engineering=status)
    app.hud.update(app.session.current, app.session.race.snapshot, road,
                   track='endless', countdown='', notice='')
    view = app.hud.coastal
    assert '6.8 L/100km' in view.sector.getText()
    assert '22.3s' in view.goal.getText() and '0.044L' in view.goal.getText()
    assert '本段 -1.0s' in view.notice.getText()
    assert app.hud.status_frame.isHidden() and not view.root.isHidden()
    used_gold = replace(road, engineering=replace(status, litres=.13))
    app.hud.update(app.session.current, app.session.race.snapshot, used_gold,
                   track='endless', countdown='', notice='')
    assert '银牌目标' in view.cumulative.getText() and '0.018L' in view.goal.getText()
    used_all = replace(road, engineering=replace(status, seconds=90.1))
    app.hud.update(app.session.current, app.session.race.snapshot, used_all,
                   track='endless', countdown='', notice='')
    assert '已超出铜牌目标' in view.cumulative.getText()
    missing = replace(road, engineering=replace(status, litres=None, consumption=None))
    app.hud.update(app.session.current, app.session.race.snapshot, missing,
                   track='endless', countdown='', notice='')
    assert '缺失' in view.cumulative.getText() and '—' in view.sector.getText()
    app.hud.update(app.session.current, RaceSnapshot(mode=GameMode.TIME_TRIAL),
                   replace(road, engineering=None), track='coastal', countdown='', notice='')
    assert not view._challenge_active and '滨海计时' in view.title.getText()
    assert view.status['frameSize'][2] == -276


def test_reference_lab_stages_same_build_and_isolates_save_from_original_vehicle(app):
    mode = GameMode.BEND_SPRINT
    app.start_sprint(mode)
    app.session.set_esc_enabled(False)
    original, config = app.workspace_vehicle, app.session.vehicle_config
    original.save(app.workspace_path)
    original_bytes = app.workspace_path.read_bytes()
    app.challenge_action('challenge-value', ('power', '110'))
    draft = app.budget_drafts[mode]
    app.challenge_action('challenge-lab')
    for _ in range(60):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == 'lab' and app.lab.engineered_config == SPRINT_CHALLENGES[mode].configuration(draft)
    assert app.lab.workspace_path != app.workspace_path
    assert app.workspace_path.read_bytes() == original_bytes
    changed = replace(app.lab.workspace_vehicle,
                      config=replace(app.lab.workspace_vehicle.config, mass=900.))
    changed.save(app.lab.workspace_path)
    app.lab.workspace_vehicle, app.lab.next_drive = changed, True
    app.lab.back_to_game()
    for _ in range(60):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == 'game' and app.session.mode == mode
    assert app.workspace_vehicle == original and app.budget_drafts[mode] == draft
    assert app.session.vehicle_config.mass == SPRINT_CHALLENGES[mode].base_config.mass
    app.back_to_menu()
    assert app.session.vehicle_config == config and app.workspace_path.read_bytes() == original_bytes


def test_specialist_editor_opens_first_allowed_group_and_pause_resumes_same_world(app):
    mode = GameMode.FAST_SLALOM
    app.open_budget_challenge(mode)
    assert app.budget_tab == 1 and 'front_tire' in app.career_panel.challenge_entries
    app.challenge_action('challenge-start')
    current, simulation = app.session.current, app.session.simulation
    app.session.pause()
    app._shown_phase = None
    app.refresh_panel()
    assert app.career_panel.page == 'challenge-pause'
    app.career_panel.resize(4/3)
    assert app.career_panel.page == 'challenge-pause'
    app.career_panel.key('escape')
    assert app.session.phase == Phase.COUNTDOWN and app.session.current == current
    assert app.session.simulation is simulation
    app.session.pause()
    app._shown_phase = None
    app.refresh_panel()
    app.challenge_action('challenge-adjust')
    assert app.session.phase == Phase.MENU and app.career_panel.page == 'challenge'


def test_budget_career_save_failure_has_real_retry_without_minting_credits(app, monkeypatch):
    # 合成已完成结果只验证保存失败交互，不作为真人成绩或标定样本。
    app.start_career_event('parking')
    app.challenge_action('challenge-start')
    spec = CAREER_CHALLENGES['parking']
    result = spec.evaluate(BuildDraft(), 20., .05, metric_value=3.)
    status = ChallengeStatus(spec.id, spec.name, spec.budget, 0, 20., 200., .05,
                             result.consumption, (), result, assessment=spec.assessment)
    app.session.highway.snapshot = replace(app.session.highway.snapshot, engineering=status)
    app.session.phase = Phase.RESULTS
    save = app.career_progress.save

    def fail(*args, **kwargs):
        app.career_progress.notice = '生涯进度未保存：测试文件访问失败。'
        return False

    monkeypatch.setattr(app.career_progress, 'save', fail)
    app._shown_phase = None
    app.refresh_panel()
    assert not app.career_award['saved'] and app.career_progress.stars == 0
    retry = next(button for button in app.career_panel.buttons if button['extraArgs'][0] == 'save')
    assert any('未保存' in label.getText() for label in app.career_panel.labels)
    assert not any(button['extraArgs'][0] in ('brief', 'garage-new') for button in app.career_panel.buttons)
    monkeypatch.setattr(app.career_progress, 'save', save)
    retry['command'](*retry['extraArgs'])
    assert app.career_award['saved'] and app.career_progress.stars == 3
    assert app.career_progress.credits == 0
    assert not any(button['extraArgs'][0] == 'save' for button in app.career_panel.buttons)
    labels = {label.getText() for label in app.career_panel.labels}
    assert {'新解锁', '赛事 · 穿过海风', '车辆 · Lotus Elise / BMW 1M Coupé'} <= labels

    panel, original = app.career_panel, app.workspace_vehicle
    new_car = next(button for button in panel.buttons if button['extraArgs'] == ['garage-new', 'club-coupe'])
    new_car['command'](*new_car['extraArgs'])
    assert panel.page == 'garage' and app.career_preview.design_id == 'club-coupe'
    assert app.workspace_vehicle == original and app.session.phase == Phase.MENU
    app.career_action('garage-back')
    assert panel.page == 'brief' and panel.event_id == 'parking'

    app.show_budget_result(status)
    event = next(button for button in panel.buttons if button['extraArgs'] == ['brief', 'slalom'])
    event['command'](*event['extraArgs'])
    assert panel.page == 'brief' and panel.event_id == 'slalom'
    assert app.session.phase == Phase.MENU and app.career_progress.stars == 3


def test_budget_result_retries_same_completed_score_without_driving_again(app, monkeypatch):
    app.start_sprint(GameMode.BEND_SPRINT)
    app.challenge_action('challenge-start')
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    run = app.session.engineering

    def fail(document):
        raise OSError('测试只读')

    with monkeypatch.context() as patch:
        patch.setattr(run.scores, '_write', fail)
        run.sample(FuelState(litres=run.window.start_litres+.34), run.spec.distance_m, 92.,
                   passed=len(run.gates), finished=True, succeeded=True)
        app.session.highway.snapshot = replace(app.session.highway.snapshot, engineering=run.snapshot)
        app.session.phase = Phase.RESULTS
        app.show_budget_result(run.snapshot)
        retry = next(button for button in app.career_panel.buttons if button['extraArgs'][0] == 'challenge-save-score')
        retry['command'](*retry['extraArgs'])
        assert run.snapshot.score_pending and not run.scores.path.exists()
    before, tick = run.snapshot, app.session.current.tick
    retry = next(button for button in app.career_panel.buttons if button['extraArgs'][0] == 'challenge-save-score')
    retry['command'](*retry['extraArgs'])
    after = app.session.highway.snapshot.engineering
    assert not after.score_pending and after.record_updates and run.scores.path.is_file()
    assert after.result == before.result and after.splits == before.splits and app.session.current.tick == tick
    assert not any(button['extraArgs'][0] == 'challenge-save-score' for button in app.career_panel.buttons)
