import json
from types import SimpleNamespace

import pytest

from coastal_map import map_length, point_at
from race import BestTimes, GameMode, RaceTracker


def state_at(distance, speed=20):
    point = point_at(distance)
    return SimpleNamespace(
        player=SimpleNamespace(position=(point.x, point.y, point.z), speed=speed)
    )


def run_one_lap(race):
    race.begin()
    for step in range(1, 101):
        race.update(state_at(map_length() * step / 100), 0.5)


def test_valid_lap_records_time_and_best(tmp_path):
    scores = BestTimes(tmp_path / "scores.json")
    race = RaceTracker(GameMode.TIME_TRIAL, scores)
    run_one_lap(race)
    result = race.snapshot
    assert result.finished and result.last_lap is not None
    assert not result.invalidated
    assert result.checkpoints == 4
    assert result.elapsed == pytest.approx(result.last_lap)
    assert scores.get(GameMode.TIME_TRIAL) == pytest.approx(result.last_lap)
    assert json.loads((tmp_path / "scores.json").read_text())["coastal-v2:time_trial"] > 0


def test_reverse_and_recross_a_checkpoint_keeps_lap_valid(tmp_path):
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(tmp_path / "scores.json"))
    race.begin()
    for step in range(1, 22):
        race.update(state_at(map_length() * 0.21 * step / 21, speed=30), 0.1)
    for step in range(1, 4):
        race.update(state_at(map_length() * (0.21 - 0.005 * step)), 0.1)
    assert not race.snapshot.invalidated
    assert race.snapshot.checkpoints == 1
    for step in range(196, 1002):
        race.update(state_at(map_length() * step / 1000), 0.1)
    assert race.snapshot.finished and not race.snapshot.invalidated
    assert race.snapshot.checkpoints == 4


def test_large_progress_jump_cannot_skip_checkpoints(tmp_path):
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(tmp_path / "scores.json"))
    race.begin()
    race.update(state_at(map_length() * 0.81, speed=0), 1 / 120)
    assert race.snapshot.invalidated
    assert race.snapshot.invalid_reason == "路线进度异常"


def test_reset_invalidates_current_attempt(tmp_path):
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(tmp_path / "scores.json"))
    race.begin()
    race.reset_player()
    assert race.snapshot.invalidated
    assert race.snapshot.invalid_reason == "车辆复位"


def test_free_drive_does_not_write_a_time(tmp_path):
    path = tmp_path / "scores.json"
    race = RaceTracker(GameMode.FREE_DRIVE, BestTimes(path))
    race.begin()
    run_one_lap(race)
    assert not path.exists()
    assert race.snapshot.mode == GameMode.FREE_DRIVE
