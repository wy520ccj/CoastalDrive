"""真实曲线的只读规则输入；这些坐标夹具不写入物理车辆。"""

import math
from dataclasses import replace

import pytest

from overtake_routes import OVERTAKE_ROUTES
from overtake_run import OvertakeRun
from race import BestTimes, GameMode
from simulation import Snapshot
from traffic import Road
from vehicle_config import CAR
from vehicle_state import CarState

MODE = GameMode.HILL_TRAFFIC


def car(road, distance, lateral=0., *, speed=20., generation=0, relative_heading=0.):
    point = road.sample_lateral(distance, lateral)
    heading, grade = math.radians(point.heading), math.radians(point.grade)
    return CarState((point.x, point.y, point.z+.5), heading=point.heading+relative_heading, speed=speed,
        velocity=(-speed*math.sin(heading)*math.cos(grade), speed*math.cos(heading)*math.cos(grade), speed*math.sin(grade)),
        generation=generation)


def state(road, distance, traffic=(), *, lateral=0., speed=20., collisions=0, relative_heading=0.):
    return Snapshot(0, 0., car(road, distance, lateral, speed=speed, relative_heading=relative_heading),
                    tuple(traffic), (), road.origin_y, collisions)


def setup(tmp_path, road=None, start=8.):
    road = road or Road('endless', seed=23, shape='hills')
    run = OvertakeRun(state(road, start), CAR, BestTimes(tmp_path/'best.json'), 'car-a', mode=MODE, road=road)
    return road, run


def passes(road, run):
    for index, center in enumerate((240., 340., 440.)):
        traffic = tuple(car(road, center+500., 4.5, generation=99) for _ in range(index))+(car(road, center, 4.5),)
        for step, offset in enumerate((-25., -3., 0., 3., 25.)):
            result = run.update(state(road, center+offset, traffic), 1.+index*10+step)
    return result


def test_three_passes_still_require_safe_finish_and_freeze_whole_best(tmp_path):
    road, run = setup(tmp_path)
    before = passes(road, run)
    assert before.passes == 3 and not before.finished and not (tmp_path/'best.json').exists()
    result = run.update(state(road, 2408.), 100.)
    assert result.succeeded and result.medal == '金' and result.new_best and result.passes == 3
    assert len(result.pass_times) == 3 and len(result.pass_clearances) == 3
    _, restored = setup(tmp_path)
    assert restored.snapshot.best_seconds == 100. and restored.snapshot.reference_times == (*result.pass_times, 100.)
    straight = OvertakeRun(state(road, 8.), CAR, BestTimes(tmp_path/'best.json'), 'car-a')
    assert straight.snapshot.best_seconds is None


@pytest.mark.parametrize('failure,reason', [('collision', '碰撞'), ('spacing', '间距不足'), ('reset', '复位')])
def test_failure_after_third_pass_has_priority_over_finish(tmp_path, failure, reason):
    road, run = setup(tmp_path)
    passes(road, run)
    traffic = (car(road, 2408., .5),) if failure == 'spacing' else ()
    result = run.update(state(road, 2408., traffic, collisions=int(failure == 'collision')), 100., reset=failure == 'reset')
    assert result.finished and not result.succeeded and reason in result.reason and result.passes == 3
    assert not (tmp_path/'best.json').exists()


def test_road_local_coordinates_not_world_x_y_and_heading(tmp_path):
    road, run = setup(tmp_path, start=380.)
    current = state(road, 400., (car(road, 430., 0.),))
    assert abs(current.player.position[0]) > 40.
    before = current
    result = run.update(current, 1.)
    assert not result.finished and result.distance == pytest.approx(20., abs=1e-4)
    assert current == before and run.snapshot.route_id == MODE.value
    # 世界X很接近，俯视沿路坐标仍须按完整车身检查跟车10米。
    result = run.update(state(road, 420., (car(road, 430., 0.),)), 2.)
    assert result.finished and '间距不足' in result.reason


def test_relative_heading_and_forward_velocity_on_curve(tmp_path):
    road, run = setup(tmp_path, start=200.)
    assert not run.update(state(road, 201.), 1.).finished
    reversed_state = state(road, 202., speed=-2.)
    result = run.update(reversed_state, 2.)
    assert '逆向' in result.reason
    _, run = setup(tmp_path/'heading', road, start=200.)
    assert '逆向' in run.update(state(road, 201., relative_heading=60.), 1.).reason


def test_curve_origin_shift_is_only_a_coordinate_change(tmp_path):
    road, run = setup(tmp_path, start=2050.)
    before = run.update(state(road, 2051., (car(road, 2080., 4.5),)), 1.)
    road.origin_y = 2000.
    shifted = state(road, 2051., (car(road, 2080., 4.5),))
    after = run.update(shifted, 2.)
    assert after.distance == pytest.approx(before.distance, abs=1e-6) and not after.finished and after.passes == 0


def test_finish_short_of_passes_and_timeout_do_not_save(tmp_path):
    road, run = setup(tmp_path)
    result = run.update(state(road, 2408.), 100.)
    assert not result.succeeded and '0/3' in result.reason
    _, run = setup(tmp_path, road)
    result = run.update(state(road, 100.), 181.)
    assert not result.succeeded and '180秒' in result.reason and not (tmp_path/'best.json').exists()
    with pytest.raises(ValueError, match='道路'):
        OvertakeRun(state(road, 8.), CAR, BestTimes(tmp_path/'best.json'), 'car-a', mode=MODE)


def test_hill_route_metadata_and_count_remains_three(tmp_path):
    road, run = setup(tmp_path)
    passes(road, run)
    for step, offset in enumerate((-25., -3., 0., 3., 25.)):
        result = run.update(state(road, 700.+offset, (car(road, 700., 4.5, generation=1),)), 40.+step)
    assert result.passes == 3 and not result.finished
    route = OVERTAKE_ROUTES[MODE]
    assert route.seed == 23 and route.shape == 'hills' and route.finish_at_end
    assert '跑完2.4公里' in route.rules
    # 原始状态是世界姿态，不通过改写heading蒙混过门。
    assert replace(state(road, 200.).player).heading != 0.
