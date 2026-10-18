"""门线规则轨迹、整圈最佳一致性与旧/损坏记录边界。"""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from coastal_map import map_length, point_at
from race import BestTimes, GameMode, RaceTracker
from tracks import COASTAL_CIRCUIT, Circuit
from ui.race_feedback import result_columns, sector_times, split_feedback


def state_at(distance, speed=100.):
    point = point_at(distance)
    return SimpleNamespace(player=SimpleNamespace(position=(point.x, point.y, point.z+.42), speed=speed))


def lap(race, segment_dt=(.1,)*5):
    race.begin()
    for index in range(1, 1002):
        race.update(state_at(map_length()*index/1000), segment_dt[min(4, (index-1)//200)])
    return race.snapshot


def test_crossing_records_fractional_simulation_time(tmp_path):
    def point(distance):
        return SimpleNamespace(x=0., y=distance, z=0., heading=0.)

    circuit = Circuit("straight-fixture", 100., 4., 5., point,
                      lambda x, y: (point(y), abs(x), y), (20., 40.))
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(tmp_path/"scores.json"), circuit)
    race.begin()
    race.update(SimpleNamespace(player=SimpleNamespace(position=(0., 19., .42), speed=20.)), 1.)
    race.update(SimpleNamespace(player=SimpleNamespace(position=(0., 23., .42), speed=5.)), .8)
    assert not race.snapshot.invalidated
    assert race.snapshot.elapsed == 1.8
    assert race.snapshot.splits == pytest.approx((1.2,))


def test_only_faster_complete_lap_replaces_whole_reference(tmp_path):
    scores = BestTimes(tmp_path/"scores.json")
    race = RaceTracker(GameMode.TIME_TRIAL, scores)
    original = lap(race)
    assert original.new_best and len(original.splits) == 5
    assert sum(sector_times(original.splits)) == original.last_lap
    assert scores.get_splits(GameMode.TIME_TRIAL, race.score_id, 5) == original.splits
    race.start()
    slower = lap(race, (.08, .12, .12, .12, .12))
    assert not slower.new_best and slower.reference_splits == original.splits
    assert sector_times(slower.splits)[0] < sector_times(original.splits)[0]
    assert BestTimes(scores.path).get_splits(GameMode.TIME_TRIAL, race.score_id, 5) == original.splits
    race.start()
    faster = lap(race, (.08,)*5)
    assert faster.new_best and faster.reference_splits == original.splits
    assert BestTimes(scores.path).get_splits(GameMode.TIME_TRIAL, race.score_id, 5) == faster.splits
    assert result_columns(faster)[2].splitlines()[1].startswith("-")
    assert faster.reference_splits != faster.splits


def test_reverse_recross_reset_and_restart_do_not_farm_sectors(tmp_path):
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(tmp_path/"scores.json"))
    race.begin()
    for index in range(1, 211):
        race.update(state_at(map_length()*index/1000), .1)
    splits = race.snapshot.splits
    for index in range(209, 180, -1):
        race.update(state_at(map_length()*index/1000, speed=-100.), .1)
    for index in range(181, 221):
        race.update(state_at(map_length()*index/1000), .1)
    assert not race.snapshot.invalidated and race.snapshot.splits == splits
    race.reset_player()
    for index in range(221, 1002):
        race.update(state_at(map_length()*index/1000), .1)
    assert race.snapshot.invalidated and not race.scores.path.exists()
    assert all(value == "—" for value in result_columns(race.snapshot)[2].splitlines()[1:])
    race.start()
    assert not race.snapshot.splits and not race.snapshot.reference_splits


def test_legacy_totals_survive_without_invented_splits(tmp_path):
    path = tmp_path/"scores.json"
    path.write_text(json.dumps({"coastal-v2:time_trial": 50., "other:time_trial": 70.}), encoding="utf-8")
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(path))
    assert race.snapshot.reference_lap == 50. and race.snapshot.reference_splits == ()
    assert "暂无" in split_feedback(race.snapshot)
    slower = lap(race)
    assert not slower.new_best
    assert json.loads(path.read_text(encoding="utf-8")) == {"coastal-v2:time_trial": 50., "other:time_trial": 70.}
    race.start()
    improved = lap(race, (.04,)*5)
    assert improved.new_best
    assert BestTimes(path).get(GameMode.TIME_TRIAL, "other") == 70.
    assert len(BestTimes(path).get_splits(GameMode.TIME_TRIAL, COASTAL_CIRCUIT.score_id, 5)) == 5


@pytest.mark.parametrize("broken", [None, [10., 9., 50.], [10., True, 50.],
                                    [10., float("nan"), 50.], [10., 20., 49.]])
def test_broken_split_keeps_valid_total_and_gives_notice(tmp_path, broken):
    path = tmp_path/"scores.json"
    key = "coastal-v2:time_trial"
    path.write_text(json.dumps({key: 50., "_splits_v1": {key: broken}}), encoding="utf-8")
    scores = BestTimes(path)
    assert scores.get(GameMode.TIME_TRIAL) == 50.
    assert scores.get_splits(GameMode.TIME_TRIAL, "coastal-v2", 5) == ()
    assert scores.notice


def test_bad_file_or_write_failure_remains_playable(tmp_path):
    path = tmp_path/"scores.json"
    path.write_text("broken JSON", encoding="utf-8")
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(path))
    assert race.snapshot.score_notice
    blocked = tmp_path/"directory"
    blocked.mkdir()
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(blocked))
    result = lap(race)
    assert result.finished and not result.invalidated and result.save_error


def test_unknown_split_count_and_invalid_input_rejected(tmp_path):
    scores = BestTimes(tmp_path/"scores.json")
    scores.record(GameMode.TIME_TRIAL, 50., splits=(10., 50.))
    assert scores.get_splits(GameMode.TIME_TRIAL, "coastal-v2", 5) == () and scores.notice
    with pytest.raises(ValueError):
        scores.record(GameMode.TIME_TRIAL, 40., splits=(20., 10., 40.))


def test_result_and_hud_keep_real_sector_and_cumulative_deltas_distinct(tmp_path):
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(tmp_path/"scores.json"))
    state = replace(race.snapshot, splits=(11., 19.), reference_splits=(10., 20., 30., 40., 50.))
    message = split_feedback(state)
    assert "第2段  8.000 s" in message and "Δ -2.000" in message and "累计差 -1.000" in message
    assert "本圈无效" in split_feedback(replace(state, invalidated=True))
