"""限速带完成步/边界插值、逆向停留及旧路线隔离。"""

import pytest

from race import BestTimes, GameMode
from sprint_routes import VALLEY_BRAKING_VERSION
from sprint_run import SprintRun
from ui.sprint_feedback import (
    driving_feedback,
    result_columns,
    result_feedback,
    valley_braking_feedback,
)
from vehicle_config import CAR


def run(tmp_path):
    return SprintRun(8., GameMode.VALLEY_PACE, BestTimes(tmp_path/'best.json'), 'hardware-A', CAR)


def update(item, distance, kph, seconds):
    return item.update(8+distance, seconds, lateral=0., heading=0., forward_speed=kph/3.6)


def enter(item):
    update(item, 250., 75., 15.)
    update(item, 390., 42., 24.)
    return update(item, 400., 42., 25.)


def test_accelerate_slow_hold_then_accelerate_again_saves_complete_valid_best(tmp_path):
    item = run(tmp_path)
    assert '测速门250m · ≥60km/h' in driving_feedback(item.snapshot)[1]
    update(item, 250., 75., 15.)
    assert '距限速带150m · 入带35–50km/h' in driving_feedback(item.snapshot)[1]
    update(item, 390., 42., 24.)
    assert update(item, 400., 42., 25.).gates == 2
    assert '限速35–50 · 42.0km/h · 出口250m' in driving_feedback(item.snapshot)[1]
    update(item, 500., 43., 34.)
    state = update(item, 650., 41., 47.)
    assert state.gates == 3 and state.zone_min_kph == 41. and state.zone_max_kph == 43.
    assert '出口0m' in driving_feedback(state)[1]
    update(item, 660., 55., 48.)
    assert '重新加速' in driving_feedback(item.snapshot)[1]
    state = update(item, 1000., 90., 65.)
    assert state.succeeded and state.medal == '金' and state.new_best
    assert state.gate_kph == (75., 42., 41., 90.)
    assert '限速带实测 41.00–43.00' in result_feedback(state)[1]
    assert '75.0' in result_columns(state)[2]
    restored = run(tmp_path).snapshot
    assert restored.best_seconds == 65. and restored.reference_times == state.gate_times


def test_budget_braking_gate_enforces_speed_and_keeps_speed_zone_limits(tmp_path):
    def budget_run():
        return SprintRun(8., GameMode.VALLEY_PACE, BestTimes(tmp_path/'best.json'), 'hardware-A', CAR,
                         record_scores=False, rules_version=VALLEY_BRAKING_VERSION)

    item = budget_run()
    assert '测速门375m · ≥80km/h' in driving_feedback(item.snapshot)[1]
    too_slow = update(item, 375., 79.99, 20.)
    assert too_slow.finished and not too_slow.succeeded and '375米门至少80' in too_slow.reason
    item = budget_run()
    assert update(item, 375., 80., 20.).gates == 1
    assert '距限速带25m' in driving_feedback(item.snapshot)[1]
    assert update(item, 400., 50., 22.).gates == 2
    update(item, 650., 35., 45.)
    assert update(item, 1000., 80., 62.).succeeded
    over = budget_run()
    update(over, 375., 85., 20.)
    assert '超过50' in update(over, 400., 50.01, 22.).reason
    assert not (tmp_path/'best.json').exists()


@pytest.mark.parametrize('entry, hint', [(45., ''), (52., '过测速门后尽快加大制动')])
def test_budget_braking_feedback_uses_only_window_and_reports_failed_entry(tmp_path, entry, hint):
    item = SprintRun(8., GameMode.VALLEY_PACE, BestTimes(tmp_path/'best.json'), 'hardware-A', CAR,
                     record_scores=False, rules_version=VALLEY_BRAKING_VERSION)
    item.update(378., 18., lateral=0., heading=0., forward_speed=90./3.6, brake_request=0.)
    item.update(388., 20., lateral=0., heading=0., forward_speed=82./3.6, brake_request=1.)
    state = item.update(408., 22., lateral=0., heading=0., forward_speed=entry/3.6, brake_request=.25)
    assert state.braking_request == pytest.approx(.5)
    assert state.zone_entry_kph == pytest.approx(entry)
    assert state.finished is bool(hint)
    if not state.finished:
        state = item.update(658., 45., lateral=0., heading=0., forward_speed=42./3.6, brake_request=0.)
        assert state.braking_request == pytest.approx(.5)
    labels, actual_hint = valley_braking_feedback(state)
    assert labels[:3] == ('测速 86.0km/h', '平均踏板 50%', f'入带 {entry:.1f}km/h')
    assert actual_hint == hint


@pytest.mark.parametrize('kph,kind', [(34.999, '低于35'), (50.001, '超过50'), (0., '低于35'), (-20., '低于35')])
def test_speed_violation_freezes_specific_position_and_never_saves(tmp_path, kph, kind):
    item = run(tmp_path)
    enter(item)
    state = update(item, 500., kph, 35.)
    assert state.finished and not state.succeeded and state.zone_error_at == 500.
    assert kind in state.reason and '500.0米' in state.reason
    assert not (tmp_path/'best.json').exists()
    assert update(item, 1000., 90., 65.) == state


@pytest.mark.parametrize('kph', [35., 50.])
def test_limits_are_inclusive_and_first_gate_still_requires_sixty(tmp_path, kph):
    item = run(tmp_path)
    update(item, 250., 60., 15.)
    update(item, 399., kph, 24.)
    update(item, 400., kph, 25.)
    update(item, 650., kph, 47.)
    assert update(item, 1000., 90., 65.).succeeded
    slower = run(tmp_path)
    state = update(slower, 250., 59.999, 15.)
    assert not state.succeeded and '测速门' in state.reason
    assert state.best_seconds == 65. and not state.new_best


def test_zone_entry_uses_interpolated_boundary_not_outside_speed(tmp_path):
    item = run(tmp_path)
    update(item, 250., 75., 15.)
    update(item, 390., 60., 24.)
    # 400米边界50，带内端点40；390米处60不属于限速带。
    state = update(item, 410., 40., 26.)
    assert not state.finished and state.zone_max_kph == 50.
    update(item, 640., 40., 46.)
    # 650米边界50，区外660米60不能被计为带内超速。
    state = update(item, 660., 60., 48.)
    assert not state.finished and state.zone_max_kph == 50.


def test_entire_zone_cannot_be_skipped_by_large_step(tmp_path):
    item = run(tmp_path)
    update(item, 250., 75., 15.)
    update(item, 390., 80., 24.)
    state = update(item, 700., 80., 48.)
    assert state.finished and '超过50' in state.reason and state.zone_error_at == 400.


def test_stationary_or_backwards_inside_zone_does_not_evade_speed_check(tmp_path):
    item = run(tmp_path)
    enter(item)
    state = update(item, 400., 0., 26.)
    assert state.finished and not state.succeeded
    backwards = run(tmp_path)
    enter(backwards)
    update(backwards, 500., 42., 35.)
    state = update(backwards, 480., -10., 36.)
    assert state.finished and not state.succeeded


def test_old_two_routes_keep_their_original_no_speed_restriction(tmp_path):
    for mode, length in ((GameMode.BEND_SPRINT, 1800.), (GameMode.RIDGE_SPRINT, 1400.)):
        item = SprintRun(8., mode, BestTimes(tmp_path/'best.json'), 'hardware-A', CAR)
        for distance in item.route.gates:
            update(item, distance, 130., 65.*distance/length)
        assert item.snapshot.succeeded and item.snapshot.zone_min_kph is None
