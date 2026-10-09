"""独立时钟的单一推进者、暂停重启、事件交付和真实错误清理。"""

import time
from dataclasses import replace
from threading import get_ident

import pytest

from impact_events import ImpactEvent
from session import Phase, Session
from session_clock import SessionClock
from simulation import FIXED_DT, Control


class RecordedController:
    def __init__(self):
        self.calls = []

    def sample(self, state, dt):
        self.calls.append((state.tick,dt,get_ident()))
        return Control(throttle=.3)


def await_ticks(session, target):
    deadline = time.monotonic()+10.
    while time.monotonic()<deadline:
        frame = session.frame(0.)
        if frame.tick>=target:
            return frame
        time.sleep(.001)
    raise AssertionError('真实独立时钟未在短测预算内推进')


def test_real_clock_matches_serial_physics_and_has_one_advancer_across_pause_restart():
    session = Session(seed=17,track='test',independent_clock=True)
    serial = Session(seed=17,track='test')
    controller = RecordedController()
    try:
        session.start(countdown=False)
        serial.start(countdown=False)
        session.set_controller(controller)
        await_ticks(session,8)
        clock = session._clock
        session.pause()
        stopped = session.current
        assert not clock.thread.is_alive()
        assert session._clock is None and session.phase==Phase.PAUSED
        assert all(dt==FIXED_DT for _tick,dt,_thread in controller.calls)
        assert {thread for _tick,_dt,thread in controller.calls}=={clock.thread.ident}
        assert [tick for tick,_dt,_thread in controller.calls]==list(range(stopped.tick))
        for _ in range(stopped.tick):
            serial.simulation.step(Control(throttle=.3))
        assert serial.simulation.snapshot()==stopped
        for _ in range(3):
            assert session.frame(1.)==stopped
        session.resume()
        await_ticks(session,stopped.tick+4)
        restarted = session._clock
        assert restarted is not clock
        session.finish()
        assert not restarted.thread.is_alive()
        assert session.phase==Phase.RESULTS and session._clock is None
        session.menu()
        assert session.simulation._query_lock is None
    finally:
        session.close()
        serial.close()


def test_completed_snapshots_interpolate_without_extrapolation_and_events_deliver_once(monkeypatch):
    session = Session(track='test')
    session.start(countdown=False)
    now = [1.]
    monkeypatch.setattr('session_clock.time.perf_counter',lambda:now[0])
    clock = SessionClock(session)
    try:
        session.tick()
        previous = session.current
        session.tick()
        current = session.current
        event = ImpactEvent(current.contact_epoch,current.tick,0,(12,),'hard_solid',200,190,2,1,
                            (0,2,0),(0,-1,0),'front',1)
        session.current = replace(current,impacts=(event,))
        clock.previous_completed_at,clock.completed_at = .97,1.
        clock.publish()
        clock.previous,clock.current = previous,session.current
        clock.previous_completed_at,clock.completed_at = .97,1.
        now[0] = 1.015
        frame = clock.frame()
        for first,last,value in zip(previous.player.position,current.player.position,frame.player.position):
            assert value==pytest.approx((first+last)/2,abs=1e-12)
        assert frame.impacts==(event,)
        assert clock.frame().impacts==()
        now[0] = 2.
        assert clock.frame().player.position==current.player.position
    finally:
        session.simulation._query_lock = None
        session.close()


def test_clock_failure_reaches_window_and_close_releases_world():
    class FailingController:
        def sample(self, state, dt):
            raise ArithmeticError('保存的真实求解失败')

    session = Session(track='test',independent_clock=True)
    session.start(countdown=False)
    session.set_controller(FailingController())
    try:
        with pytest.raises(ArithmeticError,match='保存的真实求解失败'):
            await_ticks(session,1)
        clock = session._clock
    finally:
        session.close()
    assert not clock.thread.is_alive()
    assert session.simulation.closed and session.simulation._query_lock is None
