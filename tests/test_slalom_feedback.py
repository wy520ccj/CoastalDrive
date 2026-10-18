"""逐门时间、完整最佳、旧成绩兼容和读写失败；规则直接消费完成步。"""

import json
from pathlib import Path

import pytest

from road_comparison import TrialScores
from slalom_lesson import GATES, SlalomLesson, SlalomScores
from ui.slalom_feedback import gate_columns, gate_feedback, result_feedback
from vehicle_config import CAR


def times(seconds):
    return tuple(seconds*index/6 for index in range(1, 7))


def finish(run, speed=20.):
    run.update(80., speed, 80/speed)
    for distance, center in GATES:
        run.update(distance, speed, distance/speed, lateral=center)
    return run.snapshot


def lesson(path, key="car", speed=20.):
    run = SlalomLesson(0., SlalomScores(path, key), CAR)
    return run, finish(run, speed)


def test_first_best_writes_complete_run_and_retry_freezes_that_whole_reference(tmp_path):
    path = tmp_path/"scores.json"
    _, first = lesson(path)
    assert first.gate_times == (2., 4., 6., 8., 10., 12.) and first.new_best
    stored = SlalomScores(path, "car")
    assert stored.best_run["gate_times"] == list(first.gate_times)
    assert stored.best_run["clearances"] == list(first.clearances)
    run = SlalomLesson(0., stored, CAR)
    assert run.snapshot.reference_times == first.gate_times
    latest = SlalomScores(path, "car")
    latest.record(11., gate_times=times(11.), clearances=(.5,)*6)
    slower = finish(run, 18.)
    assert slower.reference_times == first.gate_times and not slower.new_best
    assert SlalomScores(path, "car").best == 11.
    columns = gate_columns(slower)
    assert f"{slower.gate_times[-1]-12.:+.3f}" in columns[2]


def test_legacy_total_survives_and_next_improvement_adds_details_per_group(tmp_path):
    path = tmp_path/"scores.json"
    path.write_text(json.dumps({"version": 1, "scores": {"car": 17., "other": 15.}}), encoding="utf-8")
    initial = SlalomScores(path, "car")
    assert initial.best == 17. and initial.best_run is None
    _, result = lesson(path)
    assert not result.reference_times and result.new_best
    assert SlalomScores(path, "other").best == 15. and SlalomScores(path, "other").best_run is None
    assert SlalomScores(path, "car").best_run["gate_times"] == list(result.gate_times)


@pytest.mark.parametrize("bad", [None, {}, {"seconds": 12., "gate_times": [2., 4.], "clearances": [.5]*6},
    {"seconds": 12., "gate_times": [2., 4., 6., 8., 10., 11.], "clearances": [.5]*6},
    {"seconds": 12., "gate_times": [2., 4., 6., 8., 10., 12.], "clearances": [-.1]*6}])
def test_bad_detail_does_not_destroy_numeric_best_or_other_groups(tmp_path, bad):
    path = tmp_path/"scores.json"
    good = {"seconds": 15., "gate_times": times(15.), "clearances": [.6]*6}
    document = {"version": 1, "scores": {"car": 12., "other": 15.}, "runs": {"car": bad, "other": good, "unrelated": "keep"}}
    path.write_text(json.dumps(document), encoding="utf-8")
    broken = SlalomScores(path, "car")
    assert broken.best == 12. and broken.best_run is None and broken.notice
    assert SlalomScores(path, "other").best_run["gate_times"] == list(times(15.))
    assert not broken.record(13., gate_times=times(13.), clearances=(.7,)*6)
    assert broken.record(11., gate_times=times(11.), clearances=(.7,)*6)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["runs"]["unrelated"] == "keep" and saved["scores"]["other"] == 15.


def test_bad_runs_container_keeps_numeric_best_and_legacy_update_clears_stale_detail(tmp_path):
    path = tmp_path/"scores.json"
    path.write_text(json.dumps({"version": 1, "scores": {"car": 14.}, "runs": "bad"}), encoding="utf-8")
    score = SlalomScores(path, "car")
    assert score.best == 14. and score.best_run is None and score.notice
    score.record(13., gate_times=times(13.), clearances=(.5,)*6)
    assert score.best_run is not None
    score.record(12.)
    assert SlalomScores(path, "car").best == 12. and SlalomScores(path, "car").best_run is None


def test_unrelated_nonfinite_detail_does_not_crash_finish_or_replace_file(tmp_path):
    path = tmp_path/"scores.json"
    path.write_text(json.dumps({"version": 1, "scores": {"other": 15.},
                               "runs": {"other": {"gate_times": [float("nan")]}}}), encoding="utf-8")
    before = path.read_bytes()
    _, result = lesson(path)
    assert result.succeeded and not result.new_best and result.save_notice
    assert path.read_bytes() == before and SlalomScores(path, "other").best == 15.


@pytest.mark.parametrize("gate_times,clearances", [((), (.5,)*6), (times(12.), ()),
    ((2., 4., 6., 8., 10., 11.), (.5,)*6), ((2., 4., 6., 6., 10., 12.), (.5,)*6),
    ((False, 4., 6., 8., 10., 12.), (.5,)*6), (times(12.), (True, .5, .5, .5, .5, .5)),
    (times(12.), (-.1,)*6), ((2., 4., 6., float("nan"), 10., 12.), (.5,)*6)])
def test_incomplete_or_nonfinite_success_detail_is_rejected(tmp_path, gate_times, clearances):
    with pytest.raises(ValueError):
        SlalomScores(tmp_path/"scores.json", "car").record(12., gate_times=gate_times, clearances=clearances)
    assert not (tmp_path/"scores.json").exists()


def test_failed_atomic_replace_keeps_prior_file_reference_and_no_new_best(tmp_path, monkeypatch):
    path = tmp_path/"scores.json"
    lesson(path, speed=15.)
    raw = path.read_bytes()
    original_replace = Path.replace
    def failed_replace(self, target):
        if self == path.with_suffix(".tmp"):
            raise OSError("测试原子提交失败")
        return original_replace(self, target)
    monkeypatch.setattr(Path, "replace", failed_replace)
    _, result = lesson(path)
    assert result.succeeded and not result.new_best and result.save_notice
    assert result.best_seconds == 16. and path.read_bytes() == raw
    assert "个人新最佳" not in result_feedback(result)[0]


def test_interpolated_attempt_time_reverse_and_failure_are_not_fake_success(tmp_path):
    run = SlalomLesson(0., SlalomScores(tmp_path/"scores.json", "car"), CAR)
    run.update(70., 20., 3.5)
    run.update(90., 20., 4.5)
    run.update(126., 20., 6.3, lateral=-2.)
    assert run.snapshot.gate_times == pytest.approx((2.,))
    first = run.snapshot.gate_times
    run.update(115., -5., 6.4, lateral=-2.)
    run.update(130., 5., 6.6, lateral=-2.)
    assert run.snapshot.gate_times == first
    run.update(170., 20., 8.6, lateral=-2.)
    result = run.snapshot
    assert result.finished and result.gates == 1 and len(result.gate_times) == 2
    assert result.gate_times[1] > result.gate_times[0] and result.clearances[-1] < 0
    assert "2右漏" in gate_columns(result)[0] and "3左 · 未到达" in gate_columns(result)[0]
    assert "不更新个人最佳" in gate_feedback(result) and not result.new_best
    assert not (tmp_path/"scores.json").exists()


def test_virtual_trial_observes_gate_times_without_awarding_personal_best():
    scores = TrialScores()
    result = finish(SlalomLesson(0., scores, CAR))
    assert result.succeeded and result.gate_times[-1] == result.run_seconds
    assert not result.new_best and not result.reference_times and scores.best_run is None


def test_slow_complete_run_retains_six_observations_but_no_pb_delta(tmp_path):
    path = tmp_path/"scores.json"
    _, old = lesson(path)
    run = SlalomLesson(0., SlalomScores(path, "car"), CAR)
    run.update(80., 20., 4.)
    for index, (distance, center) in enumerate(GATES):
        run.update(distance, 10., 4.+(index+1)*4.5, lateral=center)
    assert len(run.snapshot.gate_times) == 6 and not run.snapshot.succeeded
    assert SlalomScores(path, "car").best == old.run_seconds
    assert all(line.endswith(" / —") for line in gate_columns(run.snapshot)[2].splitlines()[1:])
