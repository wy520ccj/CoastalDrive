"""高速验车带的边界与旧练习隔离；这里的轨迹是规则夹具。"""

import pytest

from slalom_lesson import GATES, SlalomLesson, SlalomScores, medal_for
from vehicle_config import CAR


def course(tmp_path):
    run = SlalomLesson(8., SlalomScores(tmp_path/'scores.json', 'fast'), CAR, fast=True)
    run.update(87., 75/3.6, 4.)
    run.update(88., 75/3.6, 4.05)
    return run


@pytest.mark.parametrize('kph', [69.9, 80.1, 0., -10.])
def test_speed_band_rejects_between_gates_before_next_gate(tmp_path, kph):
    run = course(tmp_path)
    run.update(98., kph/3.6, 4.5)
    assert run.snapshot.finished and not run.snapshot.succeeded
    assert run.snapshot.zone_error_at == 90. and not run.snapshot.gate_times
    assert not (tmp_path/'scores.json').exists()


@pytest.mark.parametrize('kph', [70., 80.])
def test_band_limits_are_inclusive(tmp_path, kph):
    run = course(tmp_path)
    run.update(98., kph/3.6, 4.5)
    assert not run.snapshot.finished
    assert run.snapshot.zone_min_kph >= 70. and run.snapshot.zone_max_kph <= 80.


def test_stopping_or_reversing_inside_band_fails(tmp_path):
    run = course(tmp_path)
    run.update(88., 0., 4.1)
    assert run.snapshot.finished and '未向前' in run.snapshot.reason


def test_entry_interpolates_and_jump_across_whole_band_cannot_skip_speed(tmp_path):
    run = SlalomLesson(8., SlalomScores(tmp_path/'scores.json', 'fast'), CAR, fast=True)
    run.update(87., 75/3.6, 4.)
    run.update(408., 60/3.6, 17.)
    assert run.snapshot.finished and run.snapshot.zone_error_at == 320.
    assert not run.snapshot.succeeded and not (tmp_path/'scores.json').exists()


def test_complete_same_gates_with_separate_best_and_frozen_finish(tmp_path):
    run = course(tmp_path)
    for index, (distance, center) in enumerate(GATES):
        run.update(8.+distance, 75/3.6, 4.05+(index+1)*1.9, lateral=center)
    result = run.snapshot
    assert result.succeeded and result.fast and result.medal == '金'
    assert result.zone_min_kph == pytest.approx(75.) and result.zone_max_kph == pytest.approx(75.)
    assert SlalomScores(tmp_path/'scores.json', 'ordinary').best is None
    assert SlalomScores(tmp_path/'scores.json', 'fast').best == result.run_seconds
    assert run.update(500., 0., 30.) == result


def test_fast_medals_do_not_change_original_thresholds():
    assert [medal_for(s, fast=True) for s in (11.5, 12.5, 14., 14.01)] == ['金', '银', '铜', '']
    assert [medal_for(s) for s in (15., 18., 24., 24.01)] == ['金', '银', '铜', '']


def test_fast_countdown_does_not_show_old_entry_speed():
    from ui.slalom_feedback import driving_feedback
    assert '70–80' in driving_feedback(None, fast=True)[0]
    assert '40km/h' in driving_feedback(None)[0]
