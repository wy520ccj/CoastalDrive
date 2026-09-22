import pytest

from race import GameMode
from session import Phase, Session
from simulation import Control, Simulation
from tracks import TrackId, get_track


def test_track_catalog_keeps_map_and_lane_rules_separate():
    coastal = get_track(TrackId.COASTAL_LOOP)
    highway = get_track(TrackId.HIGHWAY_PREVIEW)
    assert coastal.closed and len(coastal.lanes) == 2
    assert not highway.closed and len(highway.lanes) == 3
    assert [lane.center for lane in highway.lanes] == [-4.5, 0.0, 4.5]
    assert [(lane.left, lane.right) for lane in highway.lanes] == [(None, 1), (0, 2), (1, None)]


def test_time_trial_timer_starts_after_countdown():
    session = Session(4)
    try:
        session.start(mode=GameMode.TIME_TRIAL, countdown=True)
        for _ in range(120):
            session.tick()
        assert session.phase == Phase.COUNTDOWN
        assert session.race.snapshot.elapsed == 0
        for _ in range(240):
            session.tick()
        assert session.phase == Phase.DRIVING
        assert session.race.snapshot.elapsed == 0
        for _ in range(12):
            session.tick()
        assert session.race.snapshot.elapsed == pytest.approx(12 / 120)
    finally:
        session.close()


def test_session_can_switch_to_seeded_highway_and_back():
    session = Session(8)
    try:
        session.start(mode=GameMode.FREE_DRIVE, countdown=False, track="highway")
        first = session.current.traffic
        assert session.track.id == TrackId.HIGHWAY_PREVIEW
        assert session.current.player.position[0] == 0
        assert len(first) == 8
        session.start(mode=GameMode.TIME_TRIAL, countdown=False, track="coastal")
        assert session.track.id == TrackId.COASTAL_LOOP
        assert session.current.player.position[:2] == (95.0, 0.0)
    finally:
        session.close()


def test_highway_traffic_is_repeatable_and_uses_lanes():
    first = Simulation(12, track="highway")
    second = Simulation(12, track="highway")
    try:
        assert first.snapshot().traffic == second.snapshot().traffic
        for _ in range(120):
            first.step(Control(throttle=0.3))
            second.step(Control(throttle=0.3))
        assert first.snapshot().traffic == second.snapshot().traffic
        assert all(
            min(abs(car.position[0] - lane) for lane in (-4.5, 0, 4.5)) < 0.4
            for car in first.snapshot().traffic
        )
    finally:
        first.close()
        second.close()
