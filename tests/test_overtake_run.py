"""安全超车的身份、全车间距、连续轨迹和成绩边界。"""

import math
from unittest.mock import patch

import pytest

from overtake_run import OvertakeRun, body, swept_close
from race import BestTimes, GameMode
from simulation import Snapshot
from vehicle_config import CAR
from vehicle_state import CarState


def state(y, others, *, x=0., origin=0., collisions=0, heading=0., speed=20.):
    return Snapshot(0, 0., CarState((x, y, .5), heading=heading, velocity=(0., speed, 0.), speed=speed),
                    tuple(others), (), origin, collisions)


def car(y, *, x=4.5, generation=0, active=True):
    return CarState((x, y, .5), velocity=(0., 15., 0.), speed=15., generation=generation, active=active)


def run(tmp_path, initial=None, variant='car-a'):
    initial = state(0., (car(25.),)) if initial is None else initial
    return OvertakeRun(initial, CAR, BestTimes(tmp_path/'best.json'), variant)


def pass_one(item, *, slot=0, start=0., now=1., generation=0):
    for offset, seconds in ((-25., now), (-5., now+1), (0., now+2), (5., now+3), (25., now+4)):
        others = [car(start+500., generation=99) for _ in range(slot)] + [car(start, generation=generation)]
        result = item.update(state(start+offset, others), seconds)
    return result


def test_safe_complete_and_restore_whole_times(tmp_path):
    item = run(tmp_path)
    first = pass_one(item)
    assert first.passes == 1 and not first.finished and first.pass_clearances[0] == pytest.approx(2.4)
    result = pass_one(item, slot=1, start=100., now=10.)
    assert result.succeeded and result.medal == '金' and result.pass_ids == ((0, 0), (1, 0))
    assert result.pass_times == (5., 14.) and result.new_best
    restored = run(tmp_path)
    assert restored.snapshot.best_seconds == 14. and restored.snapshot.reference_times == (5., 14.)
    assert run(tmp_path, variant='car-b').snapshot.best_seconds is None
    frozen = item.snapshot
    assert item.update(state(5000., (), collisions=1), 100.) == frozen


@pytest.mark.parametrize('where,x,other_y,reason', [
    (0., 0., 12., '间距不足'), (0., 1.5, 0., '间距不足'),
    (0., 6., 100., '驶离'), (0., 0., 100., '逆向'),
])
def test_specific_failures(tmp_path, where, x, other_y, reason):
    item = run(tmp_path, state(where, (car(other_y, x=0.),)))
    result = item.update(state(where, (car(other_y, x=0.),), x=x, speed=-1. if reason == '逆向' else 20.), 1.)
    assert result.finished and not result.succeeded and reason in result.reason
    assert not (tmp_path/'best.json').exists()


def test_cut_in_sweep_and_exact_spacing(tmp_path):
    item = run(tmp_path, state(0., (car(0., x=-4.5),)))
    result = item.update(state(0., (car(0., x=4.5),)), .01)
    assert result.finished and '间距不足' in result.reason
    assert swept_close((-10., 0.), (10., 0.), 3., 14.)
    assert not swept_close((3., -30.), (3., 30.), 3., 14.)
    own = body(state(0., ()).player, CAR)
    other = body(car(0.), CAR)
    width = own[2]+other[2]+1.
    exact = run(tmp_path, state(0., (car(0., x=width),)))
    assert not exact.update(state(0., (car(0., x=width),)), 1.).finished


def test_recycle_disappear_reverse_repeat_do_not_earn(tmp_path):
    item = run(tmp_path)
    pass_one(item)
    assert item.snapshot.passes == 1
    pass_one(item, now=10.)
    assert item.snapshot.passes == 1
    item.update(state(20., (car(0., generation=1),)), 20.)
    assert item.snapshot.passes == 1
    item.update(state(25., (car(0., active=False),)), 21.)
    item.update(state(30., (car(0.),)), 22.)
    assert item.snapshot.passes == 1
    reverse = item.update(state(29., (car(0.),), speed=-2.), 23.)
    assert not reverse.succeeded and '逆向' in reverse.reason


def test_origin_shift_does_not_create_pass(tmp_path):
    item = run(tmp_path, state(3900., (car(3920.),)))
    before = item.update(state(3901., (car(3920.),)), 1.)
    after = item.update(state(-99., (car(-80.),), origin=4000.), 2.)
    assert after.distance == before.distance and after.passes == 0 and not after.finished


@pytest.mark.parametrize('flag,reason', [('collision', '碰撞'), ('reset', '复位'), ('distance', '2公里'), ('time', '150秒')])
def test_limits_precede_award(tmp_path, flag, reason):
    item = run(tmp_path)
    result = item.update(state(2001. if flag == 'distance' else 1., (), collisions=int(flag == 'collision')),
                         151. if flag == 'time' else 1., reset=flag == 'reset')
    assert result.finished and not result.succeeded and reason in result.reason
    assert not (tmp_path/'best.json').exists()


@pytest.mark.parametrize('gap_offset, previous_time, succeeded, reason', [
    (-.2, 30., True, '安全超越2辆'),
    (.2, 30., False, '仅安全超越1/2辆'),
    (-.2, 149.995, True, '安全超越2辆'),
    (.2, 149.995, False, '仅安全超越1/2辆'),
    (-.2, 149.998, False, '超过150秒'),
])
def test_budget_overtake_respects_order_inside_finish_tick(tmp_path, gap_offset, previous_time, succeeded, reason):
    item = OvertakeRun(state(0., (car(25.),)), CAR, BestTimes(tmp_path/'best.json'), 'budget', record_scores=False)
    assert pass_one(item).passes == 1
    finish = item.route.distance
    other = finish-2*CAR.collision_half_length-10.+gap_offset
    others = car(5000.), car(other)
    item.update(state(other-25., others), 20.)
    item.update(state(other, others), 21.)
    item.update(state(finish-.5, others), previous_time)
    result = item.update(state(finish+.5, others), previous_time+1/120)
    assert result.finished and result.succeeded is succeeded and reason in result.reason
    assert result.passes == (2 if succeeded else 1)
    if succeeded:
        assert result.pass_times[-1] == pytest.approx(previous_time+(.5+gap_offset)/120)
        assert result.pass_times[-1] <= min(previous_time+.5/120, item.route.seconds)
    assert not (tmp_path/'best.json').exists()


def test_full_body_yaw_and_atomic_save_failure(tmp_path):
    own = state(0., (), heading=30.).player
    assert body(own, CAR)[2] > CAR.collision_half_width
    item = run(tmp_path)
    pass_one(item)
    with patch('pathlib.Path.replace', side_effect=OSError('只读')):
        result = pass_one(item, slot=1, start=100., now=10.)
    assert result.succeeded and not result.new_best and result.best_seconds is None and result.save_notice
    assert not (tmp_path/'best.json').exists()


def test_slow_or_failed_run_preserves_saved_best(tmp_path):
    first = run(tmp_path)
    pass_one(first)
    pass_one(first, slot=1, start=100., now=10.)
    saved = (tmp_path/'best.json').read_bytes()
    slower = run(tmp_path)
    pass_one(slower)
    result = pass_one(slower, slot=1, start=100., now=100.)
    assert result.succeeded and result.medal == '银' and not result.new_best and result.best_seconds == 14.
    assert (tmp_path/'best.json').read_bytes() == saved
    corrupt = tmp_path/'corrupt.json'
    corrupt.write_text('{', encoding='utf-8')
    scores = BestTimes(corrupt)
    assert scores.notice and scores.get(GameMode.SAFE_OVERTAKE, first.score_id) is None
    assert math.isfinite(result.pass_clearances[0])


def test_simultaneous_passes_preserve_real_tie_without_invalid_split_save(tmp_path):
    others = (car(0., x=-4.5), car(0.))
    item = run(tmp_path, state(-25., others))
    for seconds, distance in enumerate((-25., -5., 0., 5., 25.), 1):
        result = item.update(state(distance, others), float(seconds))
    assert result.succeeded and result.passes == 2 and result.pass_times == (5., 5.)
    assert result.new_best and result.best_seconds == 5.
    restored = run(tmp_path)
    assert restored.snapshot.best_seconds == 5. and restored.snapshot.reference_times == ()


def test_opposite_direction_vehicle_does_not_count(tmp_path):
    other = CarState((4.5, 0., .5), heading=180., velocity=(0., -15., 0.), speed=15.)
    item = run(tmp_path, state(-25., (other,)))
    for seconds, distance in enumerate((-25., -5., 0., 5., 25.), 1):
        result = item.update(state(distance, (other,)), float(seconds))
    assert result.passes == 0 and not result.finished
