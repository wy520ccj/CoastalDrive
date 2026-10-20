"""巡回只累计当前配方的完整站序；结果夹具不冒充实际驾驶。"""

import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from driving_tour import LEGS, DrivingTour, overall_medal, points
from highway_run import HighwayResult
from overtake_routes import OVERTAKE_ROUTES
from overtake_run import OvertakeResult
from sprint_routes import SPRINT_ROUTES
from sprint_run import SprintResult


def result(mode, medal='金', *, seconds=None):
    targets = SPRINT_ROUTES[mode].targets if mode in SPRINT_ROUTES else tuple(time for _, time in OVERTAKE_ROUTES[mode].targets)
    seconds = seconds if seconds is not None else targets[('金', '银', '铜').index(medal)]
    stage = (SprintResult(mode.value, 0., seconds=seconds, finished=True, succeeded=True) if mode in SPRINT_ROUTES else
             OvertakeResult(0., seconds=seconds, finished=True, succeeded=True, route_id=mode.value))
    return HighwayResult(finished=True, succeeded=True, sprint=stage if mode in SPRINT_ROUTES else None,
                         overtake=stage if mode not in SPRINT_ROUTES else None)


def complete(tour, medals=('金', '金', '金')):
    for mode, medal in zip(LEGS, medals, strict=True):
        tour.accept(mode, tour.variant, result(mode, medal))


def test_whole_attempt_best_and_restart_restore_without_mixing(tmp_path):
    path = tmp_path/'tour.json'
    tour = DrivingTour(path, 'car-a')
    complete(tour)
    assert points(tour.current) == 9 and overall_medal(tour.current) == '金' and tour.new_best
    first = tour.best
    tour.restart()
    assert tour.current == () and tour.best == first
    complete(tour, ('铜', '铜', '铜'))
    assert overall_medal(tour.current) == '铜' and not tour.new_best and tour.best == first
    loaded = DrivingTour(path, 'car-a')
    assert loaded.current == tour.current and loaded.best == first
    loaded.restart()
    for mode in LEGS:
        loaded.accept(mode, 'car-a', result(mode, seconds=result(mode).sprint.seconds-.5 if mode in SPRINT_ROUTES else 100.))
    assert loaded.new_best and loaded.best == loaded.current and loaded.best != first


@pytest.mark.parametrize('medals,award', [(('铜', '铜', '铜'), '铜'), (('金', '铜', '铜'), '铜'),
                                        (('银', '银', '银'), '银'), (('金', '银', '银'), '银'),
                                        (('金', '金', '银'), '金')])
def test_overall_points_require_all_three_legs(tmp_path, medals, award):
    tour = DrivingTour(tmp_path/'tour.json', 'a')
    for index, mode in enumerate(LEGS):
        tour.accept(mode, 'a', result(mode, medals[index]))
        assert overall_medal(tour.current) == (award if index == 2 else '')


def test_retries_unfinished_without_medal_wrong_order_and_config_do_not_advance(tmp_path):
    path = tmp_path/'tour.json'
    tour = DrivingTour(path, 'a')
    assert '未通过' in tour.accept(LEGS[0], 'a', HighwayResult())
    assert '铜牌' in tour.accept(LEGS[0], 'a', result(LEGS[0], seconds=106.))
    assert '改变' in tour.accept(LEGS[0], 'b', result(LEGS[0]))
    assert not path.exists() and not tour.current
    with pytest.raises(ValueError):
        tour.accept(LEGS[1], 'a', result(LEGS[1]))
    tour.accept(LEGS[0], 'a', result(LEGS[0]))
    saved = path.read_bytes()
    with pytest.raises(ValueError):
        tour.accept(LEGS[0], 'a', result(LEGS[0]))
    assert path.read_bytes() == saved
    assert '未通过' in tour.accept(LEGS[1], 'a', replace(result(LEGS[1]), collisions=1))
    assert len(tour.current) == 1 and path.read_bytes() == saved


def test_hardware_groups_and_partial_restart_are_independent(tmp_path):
    path = tmp_path/'tour.json'
    first = DrivingTour(path, 'a')
    first.accept(LEGS[0], 'a', result(LEGS[0]))
    second = DrivingTour(path, 'b')
    assert second.current == ()
    complete(second)
    restored = DrivingTour(path, 'a')
    assert restored.current == first.current and not restored.best
    restored.restart()
    assert DrivingTour(path, 'b').best == second.best


def test_atomic_failure_keeps_disk_and_saved_best_but_allows_memory_progress(tmp_path):
    path = tmp_path/'tour.json'
    tour = DrivingTour(path, 'a')
    tour.accept(LEGS[0], 'a', result(LEGS[0]))
    original = path.read_bytes()
    with patch('pathlib.Path.replace', side_effect=OSError('只读')):
        tour.accept(LEGS[1], 'a', result(LEGS[1]))
        tour.accept(LEGS[2], 'a', result(LEGS[2]))
    assert len(tour.current) == 3 and not tour.best and not tour.new_best and '未保存' in tour.notice
    assert path.read_bytes() == original and len(DrivingTour(path, 'a').current) == 1


def test_bad_file_not_overwritten_and_bad_current_keeps_valid_best(tmp_path):
    path = tmp_path/'bad.json'
    path.write_text('{', encoding='utf-8')
    broken = DrivingTour(path, 'a')
    broken.accept(LEGS[0], 'a', result(LEGS[0]))
    assert broken.notice and path.read_text(encoding='utf-8') == '{'
    target = tmp_path/'tour.json'
    tour = DrivingTour(target, 'a')
    complete(tour)
    document = json.loads(target.read_text(encoding='utf-8'))
    document['groups']['a']['current'][0]['seconds'] = True
    target.write_text(json.dumps(document), encoding='utf-8')
    loaded = DrivingTour(target, 'a')
    assert not loaded.current and loaded.best == tour.best and loaded.notice
