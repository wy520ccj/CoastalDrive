"""定点刹停的规则、真实物理与隔离成绩。"""

import json
import time
from dataclasses import replace

import pytest

from braking_lesson import BrakingLesson, BrakingScores, medal_for
from driving_modes import DrivingMode
from race import BestTimes, GameMode
from session import Phase, Session
from simulation import FIXED_DT


def lesson(tmp_path, key="car-a"):
    return BrakingLesson(8., BrakingScores(tmp_path / "stops.json", key))


def cross(item, kph=90):
    item.update(107., kph/3.6, kph/3.6, 5., FIXED_DT)
    return item.update(109., kph/3.6, kph/3.6, 5.+FIXED_DT, FIXED_DT)


def hold(item, distance=170.):
    for i in range(120):
        item.update(8.+distance, 0., 0., 10.+i*FIXED_DT, FIXED_DT)
    return item.snapshot


@pytest.mark.parametrize("error,medal", [(0., "金"), (2., "金"), (2.001, "银"), (5., "银"),
                                        (5.001, "铜"), (10., "铜"), (10.001, "")])
def test_medal_boundaries_are_parking_error_targets(error, medal):
    assert medal_for(error) == medal


def test_speed_gate_interpolates_forward_crossing_and_does_not_recross(tmp_path):
    item = lesson(tmp_path)
    item.update(107., 20., 20., 5., FIXED_DT)
    state = item.update(109., 30., 30., 5.+FIXED_DT, FIXED_DT)
    assert state.entry_kph == 90
    item.update(100., -10., 10., 6., FIXED_DT)
    item.update(110., 40., 40., 7., FIXED_DT)
    assert item.snapshot.entry_kph == 90
    assert not item.snapshot.finished


def test_gate_speed_below_target_fails_and_reverse_cannot_create_entry(tmp_path):
    item = lesson(tmp_path)
    item.update(-30., -30., 30., 1., FIXED_DT)
    assert item.snapshot.entry_kph is None
    cross(item, 79.)
    assert item.snapshot.finished and not item.snapshot.succeeded
    assert "先加速" in item.snapshot.reason


def test_stop_requires_one_second_and_motion_clears_hold(tmp_path):
    item = lesson(tmp_path)
    cross(item)
    for _ in range(119):
        item.update(178., 0., 0., 10., FIXED_DT)
    assert not item.snapshot.finished
    item.update(178., .2, .2, 10., FIXED_DT)
    assert item.snapshot.hold_seconds == 0
    result = hold(item, 171.5)
    assert result.finished and result.succeeded and result.medal == "金"
    assert result.error_m == 1.5 and result.best_error == 1.5
    assert BrakingScores(tmp_path/"stops.json", "car-a").best == 1.5
    assert BrakingScores(tmp_path/"stops.json", "car-b").best is None
    before = result
    item.update(500., 30., 30., 30., FIXED_DT, reset=True)
    assert item.snapshot == before


@pytest.mark.parametrize("condition,reason", [({"collisions": 1}, "碰撞"), ({"reset": True}, "复位"),
                                             ({"progress": 188.1}, "驶过"), ({"elapsed": 30.1}, "超时"),
                                             ({"lateral": 6.501}, "驶离")])
def test_failed_attempts_never_save_progress(tmp_path, condition, reason):
    item = lesson(tmp_path)
    cross(item)
    args = {"progress": 150., "forward_speed": 10., "speed": 10., "elapsed": 10., "dt": FIXED_DT}
    args.update(condition)
    result = item.update(**args)
    assert result.finished and not result.succeeded and reason in result.reason
    assert not (tmp_path/"stops.json").exists()


def test_early_stop_and_unqualified_wait_fail_without_medal(tmp_path):
    item = lesson(tmp_path)
    cross(item)
    assert not hold(item, 140.).succeeded
    assert "过早" in item.snapshot.reason and item.snapshot.error_m == -30
    pending = lesson(tmp_path)
    hold(pending, 0.)
    assert not pending.snapshot.finished and pending.snapshot.entry_kph is None


def test_scores_keep_better_result_and_handle_corrupt_and_unwritable_files(tmp_path):
    path = tmp_path/"scores.json"
    path.write_text("broken", encoding="utf-8")
    scores = BrakingScores(path, "a")
    assert scores.best is None and "未能读取" in scores.notice
    scores.record(0.)
    scores.record(5.)
    assert BrakingScores(path, "a").best == 0.
    with pytest.raises(ValueError):
        scores.record(float("nan"))
    blocker = tmp_path/"blocked"
    blocker.write_text("file", encoding="utf-8")
    broken = BrakingLesson(8., BrakingScores(blocker/"scores.json", "a"))
    cross(broken)
    assert hold(broken).succeeded and "未保存" in broken.snapshot.save_notice
    assert blocker.read_text(encoding="utf-8") == "file"


@pytest.mark.parametrize("payload", [{"version": True, "scores": {}},
                                    {"version": 1, "scores": {"a": True}},
                                    {"version": 1, "scores": {"a": float("nan")}}])
def test_invalid_history_values_remain_unattributed(tmp_path, payload):
    path = tmp_path/"scores.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    scores = BrakingScores(path, "a")
    assert scores.best is None and scores.notice


def test_session_enforces_closed_straight_course_and_preserves_hardware(tmp_path):
    session = Session(track="endless", scores=BestTimes(tmp_path/"scores.json"))
    config = session.vehicle_config
    try:
        session.road_shape = "hills"
        with pytest.raises(ValueError, match="直线"):
            session.start(mode=GameMode.BRAKING_LESSON, track="endless")
        session.road_shape = "straight"
        session.start(countdown=False, mode=GameMode.BRAKING_LESSON, track="endless")
        assert not session.simulation.npcs and session.vehicle_config is config
        initial = session.highway.snapshot.braking
        session.pause()
        session.frame(5.)
        assert session.highway.snapshot.braking == initial
        session.resume()
        session.reset_player()
        assert session.phase == Phase.RESULTS and not session.highway.snapshot.succeeded
        session.start(countdown=False)
        assert session.highway.snapshot.running and session.highway.snapshot.braking.entry_kph is None
        session.start(countdown=False, mode=GameMode.DISTANCE_CHALLENGE)
        assert len(session.simulation.npcs) == 12 and session.highway.snapshot.braking is None
    finally:
        session.close()


def test_full_config_changes_isolate_braking_scores(tmp_path):
    session = Session(track="endless", scores=BestTimes(tmp_path/"scores.json"))
    try:
        first = session.score_variant()
        session.set_vehicle_config(replace(DrivingMode.GAME.vehicle_config, front_brake_share=.7))
        assert session.score_variant() != first
    finally:
        session.close()


def test_actual_keyboard_drive_can_earn_medal_without_teleport(tmp_path):
    session = Session(track="endless", scores=BestTimes(tmp_path/"scores.json"))
    try:
        session.start(countdown=False, mode=GameMode.BRAKING_LESSON, track="endless")
        initial = session.current.player.position
        session.keyboard.press("w")
        braking = False
        for _ in range(3601):
            if session.highway.snapshot.braking.position >= 128.:
                session.keyboard.release("w")
                braking = True
            if braking and session.current.player.speed > .3:
                session.keyboard.press("s")
            elif braking:
                session.keyboard.release("s")
            session.tick()
            if session.phase == Phase.RESULTS:
                break
        result = session.highway.snapshot.braking
        assert result.succeeded, result
        assert result.entry_kph >= 80 and abs(result.error_m) <= 10
        assert session.current.collisions == 0 and initial[1] == 8.
        assert json.loads((tmp_path/"braking-best.json").read_text(encoding="utf-8"))["scores"]
    finally:
        session.close()


@pytest.mark.parametrize("brake_at,reason", [(100., "过早"), (145., "驶过")])
def test_actual_keyboard_early_and_late_braking_fail(tmp_path, brake_at, reason):
    session = Session(track="endless", scores=BestTimes(tmp_path/"scores.json"))
    try:
        session.start(countdown=False, mode=GameMode.BRAKING_LESSON, track="endless")
        session.keyboard.press("w")
        braking = False
        for _ in range(3601):
            if session.highway.snapshot.braking.position >= brake_at:
                braking = True
                session.keyboard.release("w")
            if braking:
                if session.current.player.speed > .3:
                    session.keyboard.press("s")
                else:
                    session.keyboard.release("s")
            session.tick()
            if session.phase == Phase.RESULTS:
                break
        assert not session.highway.snapshot.succeeded
        assert reason in session.highway.snapshot.reason
        assert not (tmp_path/"braking-best.json").exists()
    finally:
        session.close()


def test_independent_session_delivers_actual_braking_result_and_restarts(tmp_path):
    from session_process import SessionProcess

    session = SessionProcess(track="endless", driving_mode=DrivingMode.GAME,
        scores=BestTimes(tmp_path/"scores.json"))
    try:
        session.start(countdown=False, mode=GameMode.BRAKING_LESSON, track="endless")
        session.keyboard.press("w")
        braking = False
        deadline = time.monotonic() + 45.
        while time.monotonic() < deadline:
            if session.highway.snapshot.braking.position >= 128.:
                braking = True
                session.keyboard.release("w")
            if braking:
                if session.current.player.speed > .8:
                    session.keyboard.press("s")
                else:
                    session.keyboard.release("s")
            time.sleep(.01)
            session.frame(0.)
            if session.phase == Phase.RESULTS:
                break
        result = session.highway.snapshot.braking
        assert result.succeeded, result
        assert not session.current.traffic and session.current.collisions == 0
        session.start(countdown=False)
        assert session.highway.snapshot.braking.best_error == result.best_error
        assert session.highway.snapshot.braking.entry_kph is None
    finally:
        session.close()
