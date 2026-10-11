"""独立时钟的单一推进者、暂停重启、事件交付和真实错误清理。"""

import time
from dataclasses import replace
from threading import get_ident

import pytest

from impact_events import ImpactEvent
from session import Phase, Session
from session_clock import PRESENTATION_DELAY, SessionClock
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
        with clock.world_lock:
            session.tick()
        previous = session.current
        clock.publish()
        with clock.world_lock:
            session.tick()
        current = session.current
        event = ImpactEvent(current.contact_epoch,current.tick,0,(12,),'hard_solid',200,190,2,1,
                            (0,2,0),(0,-1,0),'front',1)
        session.current = replace(current,impacts=(event,))
        clock.publish()
        now[0] = 1.+PRESENTATION_DELAY+1.5*FIXED_DT
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


def test_irregular_completion_and_catchup_keep_fixed_presentation_speed(monkeypatch):
    """相同真实轨迹不应因计算耗时变化而让整个相机画面加速、减速。"""
    session = Session(track='test')
    session.start(countdown=False)
    now = [1.]
    monkeypatch.setattr('session_clock.time.perf_counter',lambda:now[0])
    clock = SessionClock(session)
    base = session.current
    try:
        for tick, completion in ((1, .015), (2, .019), (3, .041), (4, .043), (5, .044)):
            now[0] = 1.+completion
            session.previous = session.current
            session.current = replace(base,tick=tick,time=tick*FIXED_DT,
                player=replace(base.player,position=(0.,20*tick*FIXED_DT,.55)))
            clock.publish()
        for elapsed in (.044, .047, .051, .055):
            # 同一帧的执行点晚了5ms，仍使用该帧共同起点，不能改变显示位置。
            now[0] = 1.+elapsed+.005
            frame = clock.frame(1.+elapsed)
            assert frame.player.position[1] == pytest.approx(20*(elapsed-PRESENTATION_DELAY),abs=1e-12)
        now[0] = 2.
        assert clock.frame().player.position == session.current.player.position
        assert len(clock.history) <= 12
    finally:
        session.simulation._query_lock = None
        session.close()


def test_rebased_history_uses_latest_origin_and_reset_cannot_blend_old_position(monkeypatch):
    session = Session(track='test')
    session.start(countdown=False)
    now = [1.]
    monkeypatch.setattr('session_clock.time.perf_counter',lambda:now[0])
    clock = SessionClock(session)
    base = session.current
    try:
        for tick in range(1,5):
            origin = 2000. if tick >= 3 else 0.
            session.previous = session.current
            session.current = replace(base,tick=tick,time=tick*FIXED_DT,origin_y=origin,
                player=replace(base.player,position=(0.,20*tick*FIXED_DT-origin,.55)))
            clock.publish()
        now[0] = 1.+PRESENTATION_DELAY+1.5*FIXED_DT
        frame = clock.frame()
        assert frame.origin_y == 2000.
        assert frame.player.position[1]+frame.origin_y == pytest.approx(20*1.5*FIXED_DT,abs=1e-12)
        session.previous = session.current
        session.current = replace(session.current,tick=5,time=5*FIXED_DT,events=('player_reset',),
                                  player=replace(base.player,position=(3.,45.,.55)))
        clock.publish()
        assert len(clock.history) == 1
        assert clock.frame().player.position == (3.,45.,.55)
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
