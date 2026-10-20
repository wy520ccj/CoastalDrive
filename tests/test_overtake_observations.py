"""近车读数与原扫掠事件；坐标夹具不写入物理世界。"""

from dataclasses import replace

import pytest

from overtake_run import END_GAP, SIDE_GAP, OvertakeRun, body
from race import BestTimes
from simulation import Snapshot
from ui.overtake_feedback import result_feedback, traffic_feedback
from vehicle_config import CAR
from vehicle_state import CarState


def state(others=(), *, y=0., speed=20., origin=0.):
    return Snapshot(0, 0., CarState((0., y, .5), velocity=(0., speed, 0.), speed=speed),
                    tuple(others), (), origin, 0)


def car(y, x=0., *, speed=15., **values):
    return CarState((x, y, .5), velocity=(0., speed, 0.), speed=speed, **values)


def run(tmp_path, initial):
    return OvertakeRun(initial, CAR, BestTimes(tmp_path/'best.json'), 'observations')


def test_front_clearance_trend_and_cosmetic_warning_do_not_fail(tmp_path):
    current = state((car(30.),))
    item = run(tmp_path, current)
    first = item.update(current, 1.)
    reading = first.traffic_reading
    expected = 30.-body(current.player, CAR)[3]-body(current.traffic[0], CAR)[3]
    assert reading.kind == 'front' and reading.end_m == pytest.approx(expected)
    assert reading.closing_kph == 18 and not reading.warning
    result = item.update(state((car(30.),), y=10.), 2.)
    assert result.traffic_reading.warning and not result.finished
    assert result.traffic_reading.seconds_to_limit == pytest.approx((expected-10.-END_GAP)/5.)
    assert '匀速' in traffic_feedback(result)[0]
    assert current == state((car(30.),)) and not (tmp_path/'best.json').exists()


@pytest.mark.parametrize('y,kind', [(0., 'parallel'), (10., 'approach'), (-10., 'clear')])
def test_parallel_and_pull_away_readings_and_safe_boundary(tmp_path, y, kind):
    current = state((car(y, 3.2),))
    item = run(tmp_path, current)
    result = item.update(current, 1.)
    reading = result.traffic_reading
    assert reading.kind == kind and reading.warning and not result.finished
    assert reading.side_m == pytest.approx(1.1)
    if kind == 'clear':
        assert '后方' in traffic_feedback(result)[0] and '计数' not in traffic_feedback(result)[0]
    assert result.passes == 0


def test_readings_ignore_far_adjacent_reverse_and_inactive_and_refresh_identity(tmp_path):
    ignored = (car(150.), car(50., 4.5), car(25., speed=-3.), car(25., heading=90.), car(25., active=False))
    item = run(tmp_path, state(ignored))
    result = item.update(state(ignored), 1.)
    assert result.traffic_reading is None and not result.finished
    assert '观察' in traffic_feedback(result)[0]
    result = item.update(state((car(30., generation=3),)), 2.)
    assert result.traffic_reading.identity == (0, 3)
    result = item.update(state((car(30., generation=4, speed=25.),)), 3.)
    assert result.traffic_reading.identity == (0, 4) and result.traffic_reading.seconds_to_limit is None
    assert '拉开' in traffic_feedback(result)[0]
    assert item.update(state(()), 4.).traffic_reading is None


def test_cross_tick_cut_across_has_real_trigger_even_when_endpoint_safe(tmp_path):
    initial = state((car(0., -4.5),))
    item = run(tmp_path, initial)
    result = item.update(state((car(0., 4.5),)), .01)
    assert result.finished and not result.succeeded and '侧距2.40' in result.reason
    event = result.incident
    assert event.between_ticks and 0. < event.seconds < .01
    assert event.side_m < SIDE_GAP and event.end_m < END_GAP and event.kind == 'parallel'
    assert '拍间触发' in result_feedback(result)[1] and '保守包络' in result_feedback(result)[1]
    assert '1m侧距' in result_feedback(result)[1]
    assert item.update(state(()), 10.) is result


@pytest.mark.parametrize('y,kind', [(12., 'front'), (-12., 'clear'), (0., 'parallel')])
def test_incident_advice_and_new_generation_current_tick(tmp_path, y, kind):
    item = run(tmp_path, state(()))
    result = item.update(state((car(y, generation=1),)), 1.)
    assert result.incident.kind == kind and not result.incident.between_ticks
    assert result.incident.seconds == 1. and result.incident.identity == (0, 1)
    assert result.incident.end_m < END_GAP and result.incident.side_m < SIDE_GAP
    assert result_feedback(result)[1].count('下次') == 1


def test_origin_shift_does_not_change_front_reading_and_exact_boundary_has_no_incident(tmp_path):
    item = run(tmp_path, state((car(3920.),), y=3900.))
    before = item.update(state((car(3920.),), y=3901.), 1.)
    after = item.update(state((car(-80.),), y=-99., origin=4000.), 2.)
    assert before.traffic_reading == after.traffic_reading and before.distance == after.distance
    width = CAR.collision_half_width*2+SIDE_GAP
    item = run(tmp_path/'boundary', state((car(0., width),)))
    assert not item.update(state((car(0., width),)), 1.).finished
    assert item.snapshot.incident is None


def test_swept_event_uses_original_conservative_yawed_extent(tmp_path):
    other = car(20., heading=40.)
    item = run(tmp_path, state((other,)))
    result = item.update(state((replace(other, heading=0., position=(0., 13., .5)),)), 1.)
    assert result.finished and result.incident.side_m < SIDE_GAP and result.incident.end_m < END_GAP
