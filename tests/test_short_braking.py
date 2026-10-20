"""短距验车只读完成步；入门、直行、停车与原精度成绩分别计分。"""

from dataclasses import asdict, replace
from unittest.mock import patch

import pytest

from braking_lesson import BrakingScores
from short_braking import ShortBraking, medal_for
from tire_tuning import install, install_brakes, previous_path, restore
from vehicle_workspace import WorkspaceVehicle
from workshop import build_config


def lesson(tmp_path):
    return ShortBraking(8., BrakingScores(tmp_path/'short.json', 'car', maximum=42))


def enter(run, kph=83.):
    run.update(107., kph/3.6, kph/3.6, 4., .01)
    return run.update(108., kph/3.6, kph/3.6, 4.05, .05)


@pytest.mark.parametrize('kph,passed', [(79.99, False), (80., True), (85., True), (85.01, False)])
def test_entry_speed_limits_inclusive(tmp_path, kph, passed):
    run = lesson(tmp_path)
    result = enter(run, kph)
    assert (not result.finished) == passed
    assert not (tmp_path/'short.json').exists()


@pytest.mark.parametrize('distance,medal', [(33., '金'), (36., '银'), (42., '铜')])
def test_distance_medals_and_one_second_hold(tmp_path, distance, medal):
    run = lesson(tmp_path)
    enter(run)
    assert not run.update(108.+distance, .1, .1, 8., .5).finished
    result = run.update(108.+distance, 0., 0., 8.5, .5)
    assert result.succeeded and result.medal == medal and result.error_m is None
    assert result.stopping_m == distance and result.best_distance == distance
    assert run.update(200., 10., 10., 10., .1) == result


def test_maximum_progress_cannot_be_shortened_by_low_speed_reversal(tmp_path):
    run = lesson(tmp_path)
    enter(run)
    run.update(145., 1., 1., 7., .1)
    result = run.update(140., -.1, .1, 8., 1.)
    assert result.succeeded and result.stopping_m == 37. and result.medal == '铜'


@pytest.mark.parametrize('extra', [{'collisions': 1}, {'reset': True}, {'lateral': 1.01}, {'heading': 5.01}])
def test_invalid_drive_does_not_save(tmp_path, extra):
    run = lesson(tmp_path)
    enter(run)
    result = run.update(130., 1., 1., 8., .1, **extra)
    assert result.finished and not result.succeeded and not (tmp_path/'short.json').exists()


def test_distance_limit_reverse_and_timeout_fail_without_award(tmp_path):
    for position, speed, elapsed in ((150.1, 1., 8.), (135., -.16, 8.), (135., 1., 30.01)):
        run = lesson(tmp_path)
        enter(run)
        result = run.update(position, speed, abs(speed), elapsed, .1)
        assert result.finished and not result.succeeded and result.medal == ''
    assert not (tmp_path/'short.json').exists()


def test_best_distance_is_independent_and_save_failure_keeps_old_best(tmp_path):
    path = tmp_path/'short.json'
    run = lesson(tmp_path)
    enter(run)
    run.update(145., 0., 0., 8., 1.)
    old = path.read_bytes()
    run = lesson(tmp_path)
    enter(run)
    with patch('pathlib.Path.replace', side_effect=OSError('只读')):
        result = run.update(140., 0., 0., 8., 1.)
    assert result.succeeded and result.best_distance == 37. and result.save_notice
    assert path.read_bytes() == old
    assert BrakingScores(tmp_path/'ordinary.json', 'car').best is None
    assert [medal_for(x) for x in (33., 36., 42., 42.01)] == ['金', '银', '铜', '']


def test_brake_install_changes_only_share_and_restores_through_tire_chain(tmp_path):
    path = tmp_path/'vehicle.json'
    original = WorkspaceVehicle('reference-rwd', build_config(0, False))
    first = install_brakes(original, 2, path)
    changed = asdict(first.config)
    changed['front_brake_share'] = original.config.front_brake_share
    assert changed == asdict(original.config) and first.config.brake_torque == original.config.brake_torque
    assert install_brakes(first, 2, path) is first
    second = install(first, 0, path)
    assert restore(second, path) == first and restore(first, path) == original
    legacy = replace(first, parameter_metadata={'tire_tuning_previous': previous_path(first, path).name})
    assert restore(legacy, path) == original
