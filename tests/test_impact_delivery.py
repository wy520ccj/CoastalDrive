import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from highway_segments import REBASE_DISTANCE
from impact_events import ImpactEvent
from session import Session
from simulation import FIXED_DT


def event(epoch, tick):
    return ImpactEvent(epoch, tick, 0, (12,), "hard_solid", 200, 190, 2, 1,
                       (0, 2, 0), (0, -1, 0), "front", 1)


def test_render_frame_collects_all_physics_ticks_once_and_does_not_interpolate_events():
    session = Session(track="test")
    session.start(seed=7, countdown=False, track="test")
    session._skip_frame = False
    original_step = session.simulation.step

    def step_with_impact(control, dt=FIXED_DT):
        original_step(control, dt)
        snapshot = session.simulation.snapshot()
        session.simulation._impact_events = (event(snapshot.contact_epoch, snapshot.tick),)

    session.simulation.step = step_with_impact
    try:
        frame = session.frame(8 * FIXED_DT)
        assert [impact.tick for impact in frame.impacts] == list(range(1, 9))
        assert [impact.event_id for impact in frame.impacts] == [
            f"{frame.contact_epoch}:{tick}:0" for tick in range(1, 9)
        ]
        assert session.frame(0).impacts == ()
        assert session.frame(FIXED_DT * 0.25).impacts == ()
    finally:
        session.close()


def test_epoch_change_discards_prior_frame_events_and_reset_clears_contact_history():
    session = Session(track="test")
    session.start(seed=9, countdown=False, track="test")
    session._skip_frame = False
    original_step = session.simulation.step
    calls = 0

    def step_with_reset(control, dt=FIXED_DT):
        nonlocal calls
        original_step(control, dt)
        calls += 1
        snapshot = session.simulation.snapshot()
        if calls == 1:
            session.simulation._impact_events = (event(snapshot.contact_epoch, snapshot.tick),)
        else:
            session.simulation.reset_player()

    session.simulation.step = step_with_reset
    try:
        frame = session.frame(2 * FIXED_DT)
        assert frame.impacts == ()
        before = frame.contact_epoch
        session.simulation.impact_tracker.update((), session.simulation.snapshot().tick + 1, before)
        old_epoch = session.simulation.contact_epoch
        session.simulation.reset_player()
        assert session.simulation.contact_epoch != old_epoch
        assert session.simulation.snapshot().impacts == ()
        assert session.simulation.snapshot().contacts == ()
        old_epoch = session.simulation.contact_epoch
        session.simulation.reset(seed=10)
        assert session.simulation.contact_epoch != old_epoch
        assert session.simulation.snapshot().impacts == ()
        assert session.simulation.snapshot().contacts == ()
    finally:
        session.close()


def test_rebase_preserves_contact_epoch():
    session = Session(track="endless")
    try:
        epoch = session.simulation.contact_epoch
        session.simulation.player.shift(REBASE_DISTANCE * 2)
        session.simulation._rebase()
        assert session.simulation.contact_epoch == epoch
    finally:
        session.close()
