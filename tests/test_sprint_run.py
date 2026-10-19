"""短途门序、道路标架、完整最佳和失败保存边界。"""

from dataclasses import replace

import pytest

from race import BestTimes, GameMode
from sprint_routes import SPRINT_ROUTES
from sprint_run import SprintRun
from traffic import Road
from ui.sprint_feedback import driving_feedback, result_columns, result_feedback
from vehicle_config import CAR


def run(path, mode=GameMode.BEND_SPRINT, variant='car-A', config=CAR):
    return SprintRun(8., mode, BestTimes(path), variant, config)


def finish(item, seconds):
    for distance in item.route.gates:
        item.update(8+distance, seconds*distance/item.route.gates[-1], lateral=0., heading=0.)
    return item.snapshot


@pytest.mark.parametrize('mode', SPRINT_ROUTES)
def test_routes_really_differ_in_geometry_length_and_profile(mode):
    route = SPRINT_ROUTES[mode]
    road = Road('endless', seed=route.seed, shape=route.shape)
    samples = [road.sample_lateral(distance, 0.) for distance in (0., 250., 500., 750., 1000., 1250.)]
    assert max(abs(point.x) for point in samples) >= 60.
    assert max(abs(point.heading) for point in samples) > 10.
    heights = [point.z for point in samples]
    assert (max(heights)-min(heights) > 10.) == (mode == GameMode.RIDGE_SPRINT)
    assert route.gates[-1] > 1000. and len(route.gates) == 4


@pytest.mark.parametrize('mode', SPRINT_ROUTES)
def test_medal_boundaries_and_slow_complete_still_record_valid_result(tmp_path, mode):
    route = SPRINT_ROUTES[mode]
    for index, (seconds, medal) in enumerate(zip((*route.targets, route.targets[-1]+.01), ('金', '银', '铜', ''), strict=True)):
        result = finish(run(tmp_path/f'{index}.json', mode), seconds)
        assert result.succeeded and result.medal == medal and result.new_best
        assert result.gates == 4 and result.gate_times[-1] == seconds
        assert route.medal_for(seconds+.001) != medal if medal else not route.medal_for(seconds)


def test_forward_gate_interpolation_reverse_no_duplicate_and_frozen_full_reference(tmp_path):
    path = tmp_path/'best.json'
    original = finish(run(path), 80.)
    item = run(path)
    item.update(448., 19.5, lateral=-1., heading=0.)
    state = item.update(468., 20.5, lateral=1., heading=0.)
    assert state.gates == 1 and state.gate_times == (20.,)
    assert state.clearances[0] == pytest.approx(6.5-CAR.collision_half_width)
    item.update(440., 21., lateral=0., heading=0.)
    item.update(470., 22., lateral=0., heading=0.)
    assert item.snapshot.gates == 1
    finish(item, 90.)
    assert item.snapshot.reference_times == original.gate_times
    assert item.snapshot.best_seconds == 80. and not item.snapshot.new_best
    assert BestTimes(path).get(GameMode.BEND_SPRINT, item.score_id) == 80.
    assert 'ΔPB' in driving_feedback(item.snapshot)[1]
    assert '+10.000' in result_columns(item.snapshot)[2]


@pytest.mark.parametrize('condition,reason', [({'collisions': 1}, '碰撞'), ({'reset': True}, '复位'),
    ({'lateral': 6.501}, '驶离'), ({'elapsed': 180.01}, '超时'), ({'lateral': 5.8}, '错过')])
def test_failed_attempt_cannot_update_best_or_recover_into_valid_run(tmp_path, condition, reason):
    path = tmp_path/'best.json'
    item = run(path)
    args = {'progress': 458., 'elapsed': 20., 'lateral': 0., 'heading': 0.}
    args.update(condition)
    state = item.update(**args)
    assert state.finished and not state.succeeded and reason in state.reason
    assert not path.exists() and not state.new_best
    assert item.update(2000., 100., lateral=0., heading=0.) == state


def test_angled_body_and_shifted_center_must_fit_at_gate(tmp_path):
    item = run(tmp_path/'best.json', config=replace(CAR, front_weight_share=.7))
    item.update(457., 20., lateral=5., heading=35.)
    item.update(459., 21., lateral=5., heading=35.)
    assert item.snapshot.finished and not item.snapshot.succeeded and item.snapshot.clearances[0] < 0


def test_finish_crossing_just_before_time_limit_survives_later_completed_tick(tmp_path):
    item = run(tmp_path/'best.json')
    for distance in item.route.gates[:-1]:
        item.update(8+distance, distance/10., lateral=0., heading=0.)
    item.update(1807., 179.98, lateral=0., heading=0.)
    state = item.update(1809., 180.01, lateral=0., heading=0.)
    assert state.succeeded and state.seconds == pytest.approx(179.995) and not state.medal


def test_hardware_and_route_groups_cannot_share_best_and_cancellation_never_saves(tmp_path):
    path = tmp_path/'best.json'
    finish(run(path), 80.)
    assert run(path, variant='car-B').snapshot.best_seconds is None
    assert run(path, mode=GameMode.RIDGE_SPRINT).snapshot.best_seconds is None
    item = run(path)
    item.stop('提前结束')
    assert not item.snapshot.succeeded and item.snapshot.best_seconds == 80.
    assert '提前结束' in result_feedback(item.snapshot)[0]


def test_failed_atomic_write_preserves_old_total_and_segments(tmp_path, monkeypatch):
    path = tmp_path/'best.json'
    finish(run(path), 90.)
    previous = path.read_bytes()
    item = run(path)
    def failed_save():
        item.scores.error = '成绩未保存'
        return False
    monkeypatch.setattr(item.scores, '_save', failed_save)
    state = finish(item, 80.)
    assert state.succeeded and state.medal == '金' and not state.new_best and state.best_seconds == 90.
    assert state.save_notice and path.read_bytes() == previous
    assert item.scores.get_splits(item.mode, item.score_id, 4)[-1] == 90.
