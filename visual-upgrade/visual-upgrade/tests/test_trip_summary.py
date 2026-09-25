from types import SimpleNamespace

import pytest

from race import GameMode
from session import Phase, Session, TripSummary
from simulation import FIXED_DT


def state(x, y):
    return SimpleNamespace(player=SimpleNamespace(position=(x, y, 0)))


def test_trip_summary_counts_horizontal_distance_and_skips_reset_jump():
    trip = TripSummary()
    trip.update(state(0, 0), state(3, 4), FIXED_DT)
    trip.update(state(3, 4), state(30, 40), FIXED_DT, reset=True)
    trip.update(state(30, 40), state(33, 44), FIXED_DT)
    assert trip.elapsed == pytest.approx(3 * FIXED_DT)
    assert trip.distance == pytest.approx(10)


def test_session_trip_summary_runs_only_during_coastal_free_drive():
    session = Session()
    try:
        session.start(countdown=False, mode=GameMode.FREE_DRIVE)
        session.tick()
        assert session.trip_summary.elapsed == pytest.approx(FIXED_DT)
        distance = session.trip_summary.distance
        session.pause()
        session.tick()
        assert session.trip_summary.elapsed == pytest.approx(FIXED_DT)
        assert session.trip_summary.distance == pytest.approx(distance)
        session.phase = Phase.RESULTS
        session.tick()
        assert session.trip_summary.elapsed == pytest.approx(FIXED_DT)
    finally:
        session.close()


def test_trip_summary_is_hidden_from_non_coastal_modes():
    session = Session(track="endless")
    try:
        session.start(countdown=False, mode=GameMode.FREE_DRIVE)
        session.tick()
        assert session.trip_summary.elapsed == 0
        assert session.trip_summary.distance == 0
    finally:
        session.close()
