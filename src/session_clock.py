"""独立120Hz会话时钟；绘制只领取已完成快照，物理仍只有一个推进者。"""

import time
import traceback
from collections import deque
from dataclasses import replace
from itertools import pairwise
from threading import Event, Lock, RLock, Thread, current_thread

from simulation import FIXED_DT, interpolate, shift_snapshot

PRESENTATION_DELAY = 4*FIXED_DT


class SessionClock:
    def __init__(self, session):
        self.session = session
        self.stop_requested = Event()
        self.world_lock = RLock()
        session.simulation._query_lock = self.world_lock
        self.output_lock = Lock()
        self.thread = Thread(target=self.run,name='CoastalDrive physics',daemon=True)
        self.error = None
        self.previous = session.previous
        self.current = session.current
        self.history = deque((self.current,), maxlen=12)
        self.timeline_origin = time.perf_counter()-self.current.time-session.stepper.remainder
        self.timeline_dropped = session.stepper.dropped_time
        self.published_dropped = self.timeline_dropped
        self.timeline_phase = session.phase
        self.impacts = []
        self.segments = self.segment_indices()
        self.visible_segments = self.segments
        self.visible_origin = self.current.origin_y
        self.status = self.presentation_status()

    def presentation_status(self):
        session = self.session
        return (session.phase, session.countdown_ticks, session.stepper.dropped_time,
                session.race.snapshot, session.highway.snapshot, session.notice,
                session.simulation.collision_count, session.simulation.rebases,
                session.simulation.traffic_cycles, session.simulation.initialisation_ticks)

    def segment_indices(self):
        stream = self.session.simulation.stream
        return tuple(stream.segments) if stream is not None else ()

    def start(self):
        self.thread.start()

    def publish(self):
        with self.output_lock:
            latest = self.session.current
            discontinuity = (latest.contact_epoch != self.current.contact_epoch
                             or 'player_reset' in latest.events)
            if discontinuity:
                self.impacts.clear()
                self.history.clear()
            if self.timeline_phase != self.session.phase:
                self.timeline_origin = time.perf_counter()-latest.time-self.session.stepper.remainder
                self.timeline_dropped = self.session.stepper.dropped_time
                self.timeline_phase = self.session.phase
                self.history.clear()
            if latest.tick > self.current.tick:
                self.impacts.extend(latest.impacts)
            if not self.history or latest.tick > self.history[-1].tick:
                self.history.append(latest)
            self.previous,self.current = self.session.previous,latest
            self.published_dropped = self.session.stepper.dropped_time
            self.segments = self.segment_indices()
            self.status = self.presentation_status()

    def tick(self):
        if self.stop_requested.is_set():
            return
        with self.world_lock:
            self.session.tick()
            self.publish()

    def run(self):
        previous = time.perf_counter()
        with self.output_lock:
            self.timeline_origin = previous-self.current.time-self.session.stepper.remainder
        try:
            while not self.stop_requested.is_set():
                now = time.perf_counter()
                elapsed,previous = now-previous,now
                if self.session.phase.value == 'countdown':
                    with self.world_lock:
                        self.session.advance_countdown(elapsed)
                        self.publish()
                else:
                    self.session.stepper.advance(elapsed,self.tick)
                remaining = FIXED_DT-self.session.stepper.remainder-(time.perf_counter()-now)
                if remaining>0:
                    # Windows的Event超时受粗粒度调度影响；CPython sleep使用高分辨率等待计时器。
                    # 最长只等一个8.333ms拍，停止请求在下一拍立即检查。
                    time.sleep(remaining)
        except Exception as error:  # noqa: BLE001 - 独立时钟须向窗口传回原始失败
            error.add_note(traceback.format_exc())
            self.error = error
        finally:
            self.stop_requested.set()

    def frame(self, sampled_at=None):
        if self.error is not None:
            raise self.error
        with self.output_lock:
            current = self.current
            history = tuple(self.history)
            sampled_at = time.perf_counter() if sampled_at is None else sampled_at
            render_time = (sampled_at-self.timeline_origin
                           -(self.published_dropped-self.timeline_dropped)-PRESENTATION_DELAY)
            impacts = tuple(self.impacts)
            self.impacts.clear()
            self.visible_segments = self.segments
            self.visible_origin = current.origin_y
        # 沿固定仿真时间轴延迟四拍显示；涵盖计算和窗口流水线，避免反复撞上最新快照。
        # 保存追帧批次的真实快照，卡顿后仍按时间选相邻拍，缺少未来状态时停止外推。
        state = history[-1]
        if render_time <= history[0].time:
            state = history[0]
        else:
            for previous, latest in pairwise(history):
                if render_time <= latest.time:
                    state = interpolate(previous,latest,(render_time-previous.time)/FIXED_DT)
                    break
        if state.origin_y != current.origin_y:
            state = shift_snapshot(state,current.origin_y)
        visible_time = min(history[-1].time,max(history[0].time,render_time))
        return replace(state,time=visible_time,impacts=impacts,contacts=current.contacts)

    def stop(self):
        self.stop_requested.set()
        if current_thread() is self.thread:
            return False
        self.thread.join(5.)
        if self.thread.is_alive():
            raise RuntimeError('独立物理时钟未完成当前物理步，不能销毁其世界')
        self.session.simulation._query_lock = None
        return True
