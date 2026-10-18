"""过门插值、俯视包络、安全失败与独立成绩文件。"""

import json
from dataclasses import replace

import pytest

from slalom_lesson import GATES, SlalomLesson, SlalomScores, medal_for
from vehicle_config import CAR


def lesson(tmp_path, key="car-A", config=CAR):
    return SlalomLesson(8., SlalomScores(tmp_path/"scores.json", key), config)


def complete(run, speed=20.):
    run.update(88., speed, 80/speed)
    for distance, center in GATES:
        run.update(8+distance, speed, distance/speed, lateral=center)
    return run.snapshot


@pytest.mark.parametrize("speed,medal", [(20., "金"), (15., "银"), (11.2, "铜")])
def test_all_six_gates_and_interpolated_elapsed_save_only_success(tmp_path, speed, medal):
    result = complete(lesson(tmp_path), speed)
    assert result.finished and result.succeeded and result.gates == 6 and result.medal == medal
    assert result.run_seconds == pytest.approx(240/speed)
    assert len(result.errors) == len(result.clearances) == 6
    assert SlalomScores(tmp_path/"scores.json", "car-A").best == result.run_seconds
    assert SlalomScores(tmp_path/"scores.json", "other-hardware").best is None


def test_forward_crossing_interpolates_position_and_time_no_duplicate_reverse(tmp_path):
    run = lesson(tmp_path)
    run.update(78., 20., 3.5)
    run.update(98., 20., 4.5)
    assert run.snapshot.entry_time == 4.
    run.update(126., 20., 5.9, lateral=-1.9)
    run.update(130., 20., 6.1, lateral=-2.1)
    assert run.snapshot.gates == 1 and run.snapshot.errors == pytest.approx((0.,))
    run.update(126., -5., 6.2, lateral=-2.)
    run.update(130., 5., 6.3, lateral=-2.)
    assert run.snapshot.gates == 1


@pytest.mark.parametrize("kind", ["straight", "yaw", "wide", "slow", "collision", "reset", "outside", "timeout"])
def test_specific_invalid_actions_do_not_award_or_write(tmp_path, kind):
    config = replace(CAR, collision_half_width=2.01) if kind == "wide" else CAR
    run = lesson(tmp_path, config=config)
    run.update(88., 9. if kind == "slow" else 20., 4.)
    run.update(128., 20., 41. if kind == "timeout" else 6., lateral=7. if kind == "outside" else
               0. if kind == "straight" else -2., heading=90. if kind == "yaw" else 0.,
               collisions=int(kind == "collision"), reset=kind == "reset")
    result = run.snapshot
    assert result.finished and not result.succeeded and not result.medal and result.reason
    assert not (tmp_path/"scores.json").exists()
    assert run.update(400., 20., 20.) == result


def test_gate_edge_includes_body_width_and_boundary_is_inclusive(tmp_path):
    run = lesson(tmp_path)
    run.update(88., 20., 4.)
    run.update(128., 20., 6., lateral=-2.+2.-CAR.collision_half_width)
    assert run.snapshot.gates == 1 and run.snapshot.clearances[0] == pytest.approx(0.)


def test_fore_aft_body_center_offset_is_included_for_engineered_weight_distribution(tmp_path):
    run = lesson(tmp_path, config=replace(CAR, front_weight_share=.7))
    run.update(88., 20., 4.)
    run.update(128., 20., 6., lateral=-2., heading=30.)
    assert run.snapshot.errors[0] == pytest.approx(.22)
    assert not run.snapshot.succeeded and run.snapshot.clearances[0] < 0


def test_complete_but_too_slow_and_early_exit_cannot_save(tmp_path):
    run = lesson(tmp_path)
    run.update(88., 20., 4.)
    for index, (distance, center) in enumerate(GATES):
        run.update(8+distance, 10., 4+(index+1)*4.5, lateral=center)
    assert run.snapshot.finished and not run.snapshot.succeeded and "24秒" in run.snapshot.reason
    run = lesson(tmp_path)
    run.stop("提前结束")
    assert run.snapshot.finished and not run.snapshot.succeeded and not (tmp_path/"scores.json").exists()


def test_best_is_atomic_per_car_and_bad_files_and_write_failure_are_reported(tmp_path):
    path = tmp_path/"scores.json"
    a = SlalomScores(path, "a")
    a.record(17.)
    a.record(18.)
    b = SlalomScores(path, "b")
    b.record(14.)
    assert SlalomScores(path, "a").best == 17. and SlalomScores(path, "b").best == 14.
    path.write_text("broken", encoding="utf-8")
    assert SlalomScores(path, "a").notice
    blocked = tmp_path/"blocked"
    blocked.write_text("file", encoding="utf-8")
    scores = SlalomScores(blocked/"scores.json", "a")
    scores.record(13.)
    assert scores.notice and scores.best is None


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, 0, -1, 25])
def test_invalid_score_values_are_not_saved(tmp_path, value):
    with pytest.raises(ValueError):
        SlalomScores(tmp_path/"scores.json", "a").record(value)


@pytest.mark.parametrize("seconds,medal", [(15., "金"), (15.01, "银"), (18., "银"), (24., "铜"), (24.01, "")])
def test_frozen_medal_limits(seconds, medal):
    assert medal_for(seconds) == medal


def test_invalid_finite_score_document_is_not_accepted(tmp_path):
    path = tmp_path/"scores.json"
    path.write_text(json.dumps({"version": 1, "scores": {"a": -1}}), encoding="utf-8")
    assert SlalomScores(path, "a").best is None
