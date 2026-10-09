"""独立120Hz会话时钟；绘制只领取已完成快照，物理仍只有一个推进者。"""

import time
import traceback
from dataclasses import replace
from threading import Event, Lock, RLock, Thread, current_thread

from simulation import FIXED_DT, interpolate


class SessionClock:
    def __init__(self, session):
        self.session = session
        self.stop_requested = Event()
        self.world_lock = RLock()
        session.simulation._query_lock = self.world_lock
        self.output_lock = Lock()
        self.thread = Thread(target=self.run,name='CoastalDrive physics',daemon=True)
        self.error = None
        self.completed_at = time.perf_counter()
        self.previous_completed_at = self.completed_at-FIXED_DT
        self.previous = session.previous
        self.current = session.current
        self.impacts = []
        self.segments = self.segment_indices()
        self.visible_segments = self.segments
        self.visible_origin = self.current.origin_y

    def segment_indices(self):
        stream = self.session.simulation.stream
        return tuple(stream.segments) if stream is not None else ()

    def start(self):
        self.thread.start()

    def publish(self):
        with self.output_lock:
            latest = self.session.current
            if latest.contact_epoch != self.current.contact_epoch:
                self.impacts.clear()
            if latest.tick > self.current.tick:
                self.impacts.extend(latest.impacts)
            self.previous,self.current = self.session.previous,latest
            self.previous_completed_at,self.completed_at = self.completed_at,time.perf_counter()
            self.segments = self.segment_indices()

    def tick(self):
        if self.stop_requested.is_set():
            return
        with self.world_lock:
            self.session.tick()
            self.publish()

    def run(self):
        previous = time.perf_counter()
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
                    self.stop_requested.wait(remaining)
        except Exception as error:  # noqa: BLE001 - 独立时钟须向窗口传回原始失败
            error.add_note(traceback.format_exc())
            self.error = error
        finally:
            self.stop_requested.set()

    def frame(self):
        if self.error is not None:
            raise self.error
        with self.output_lock:
            previous,current,completed = self.previous,self.current,self.completed_at
            duration = self.completed_at-self.previous_completed_at
            impacts = tuple(self.impacts)
            self.impacts.clear()
            self.visible_segments = self.segments
            self.visible_origin = current.origin_y
        # 只在两个真实已完成物理快照间插值；落后时取当前快照，不外推或制造进度。
        alpha = min(1.,max(0.,(time.perf_counter()-completed)/duration))
        state = interpolate(previous,current,alpha)
        return replace(state,impacts=impacts,contacts=current.contacts)

    def stop(self):
        self.stop_requested.set()
        if current_thread() is self.thread:
            return False
        self.thread.join(5.)
        if self.thread.is_alive():
            raise RuntimeError('独立物理时钟未完成当前物理步，不能销毁其世界')
        self.session.simulation._query_lock = None
        return True
