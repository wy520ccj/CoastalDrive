"""滨海玩法目标、有效圈边界与保存失败的整次参考一致性。"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_race_splits import lap

from coastal_medals import driving_goal, medal_for, menu_goal, next_goal, result_goal, result_medal
from race import BestTimes, GameMode, RaceSnapshot, RaceTracker


@pytest.mark.parametrize("seconds,award", [(54.999, "金"), (55., "金"), (55.001, "银"), (65., "银"),
                                        (65.001, "铜"), (80., "铜"), (80.001, ""), (120., "")])
def test_medal_limits_are_inclusive_and_do_not_invalidate_slower_valid_laps(seconds, award):
    assert medal_for(seconds) == award


@pytest.mark.parametrize("seconds", [None, 0, -1., True, "50", float("inf"), float("nan")])
def test_unusable_times_do_not_earn_medals(seconds):
    assert not medal_for(seconds)


def test_targets_advance_from_saved_best_without_an_extra_progress_file(tmp_path):
    scores = BestTimes(tmp_path/"best.json")
    assert next_goal(None) == ("铜牌", 80.)
    for seconds, target in ((81., ("铜牌", 80.)), (80., ("银牌", 65.)), (65., ("金牌", 55.)), (55., ("个人最佳", 55.))):
        scores.record(GameMode.TIME_TRIAL, seconds, "current")
        best = BestTimes(scores.path).get(GameMode.TIME_TRIAL, "current")
        assert next_goal(best) == target
        assert not (tmp_path/"progress.json").exists()
    assert "金牌 · 个人最佳 <55s" == menu_goal(55.)
    assert next_goal(scores.get(GameMode.TIME_TRIAL, "different-hardware")) == ("铜牌", 80.)


@pytest.mark.parametrize("change,track", [({"finished": False}, "coastal"), ({"invalidated": True}, "coastal"),
    ({"mode": GameMode.FREE_DRIVE}, "coastal"), ({}, "test"), ({}, "endless")])
def test_unfinished_invalid_free_or_other_track_does_not_award(change, track):
    race = replace(RaceSnapshot(mode=GameMode.TIME_TRIAL, finished=True, last_lap=50.), **change)
    assert result_medal(race, track) == ""


def test_live_target_uses_departure_reference_and_can_offer_a_lower_medal_after_deadline():
    race = RaceSnapshot(mode=GameMode.TIME_TRIAL, reference_lap=70., best_lap=60., elapsed=60.)
    assert "目标 银牌 · 还剩5.0s" in driving_goal(race)
    assert "仍可争铜牌" in driving_goal(replace(race, elapsed=66.))
    assert "完成本圈再挑战" in driving_goal(replace(race, elapsed=81.))
    assert "本圈无效" in driving_goal(replace(race, invalidated=True))
    assert "还差5.000s" in result_goal(replace(race, finished=True, last_lap=70., best_lap=70.))


def test_failed_faster_save_keeps_total_splits_ghost_and_other_groups_in_memory_and_disk(tmp_path, monkeypatch):
    path = tmp_path/"best.json"
    scores = BestTimes(path)
    scores.record(GameMode.TIME_TRIAL, 70., splits=(10., 20., 30., 40., 70.))
    scores.record(GameMode.TIME_TRIAL, 60., "other", splits=(20., 60.))
    scores.attach_ghost(GameMode.TIME_TRIAL, "coastal-v2", 70., (10., 20., 30., 40., 70.), "a"*64)
    before = path.read_bytes()
    original = Path.replace
    def fail(self, target):
        if self == path.with_suffix(".tmp"):
            raise OSError("测试原子保存失败")
        return original(self, target)
    monkeypatch.setattr(Path, "replace", fail)
    race = RaceTracker(GameMode.TIME_TRIAL, scores)
    result = lap(race, (.05,)*5)
    assert result.finished and not result.invalidated and result.save_error and not result.new_best
    assert result_medal(result, "coastal") == "金" and result.best_lap == 70.
    assert path.read_bytes() == before and scores.get(GameMode.TIME_TRIAL) == 70.
    assert scores.get_splits(GameMode.TIME_TRIAL, "coastal-v2", 5) == (10., 20., 30., 40., 70.)
    assert scores.ghost_digest(GameMode.TIME_TRIAL, "coastal-v2") == "a"*64
    assert scores.get(GameMode.TIME_TRIAL, "other") == 60.
    race.start()
    assert race.snapshot.reference_lap == 70. and race.snapshot.reference_splits[-1] == 70.
    scores.record(GameMode.TIME_TRIAL, 90.)
    assert not scores.error


def test_failed_first_save_does_not_create_an_in_memory_best(tmp_path):
    blocked = tmp_path/"best.json"
    blocked.mkdir()
    scores = BestTimes(blocked)
    race = RaceTracker(GameMode.TIME_TRIAL, scores)
    result = lap(race, (.05,)*5)
    assert result.save_error and result.best_lap is None and not result.new_best
    assert next_goal(scores.get(GameMode.TIME_TRIAL)) == ("铜牌", 80.)


def test_legacy_numeric_best_keeps_other_records_without_inventing_awards_or_splits(tmp_path):
    path = tmp_path/"best.json"
    path.write_text(json.dumps({"legacy:time_trial": 50., "current:time_trial": 70.}), encoding="utf-8")
    original = path.read_bytes()
    scores = BestTimes(path)
    assert "铜牌" in menu_goal(scores.get(GameMode.TIME_TRIAL, "current"))
    assert scores.get_splits(GameMode.TIME_TRIAL, "current", 5) == ()
    assert path.read_bytes() == original and scores.get(GameMode.TIME_TRIAL, "legacy") == 50.
