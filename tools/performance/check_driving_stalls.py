"""正常驾驶的逐帧主线程分项；定位长帧，不启用GPU查询或全局剖析。"""

import argparse
import gc
import json
import multiprocessing
import os
import sys
import time
from functools import partial
from pathlib import Path
from threading import current_thread
from typing import ClassVar

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/environment'))

import check_interactive_local_drive
from check_interactive_local_drive import DrivingProbe, check

from session import Phase


def capture_serve(*args):
    import session_process
    from simulation import Simulation

    events, slow_steps, started_gc = [], [], {}
    original = Simulation.step

    def collected(phase, info):
        generation = info['generation']
        if phase == 'start':
            started_gc[generation] = time.perf_counter()
        else:
            started = started_gc.pop(generation)
            events.append({'started_at': started, 'wall_ms': (time.perf_counter()-started)*1000,
                           'generation': generation, 'thread': current_thread().name})

    def step(world, *values, **kwargs):
        wall, cpu = time.perf_counter(), time.thread_time()
        result = original(world, *values, **kwargs)
        elapsed = time.perf_counter()-wall
        if elapsed > .012:
            slow_steps.append({'started_at': wall, 'wall_ms': elapsed*1000,
                               'thread_cpu_ms': (time.thread_time()-cpu)*1000, 'tick': world._tick})
        return result

    gc.callbacks.append(collected)
    Simulation.step = step
    try:
        session_process._serve(*args)
    finally:
        gc.callbacks.remove(collected)
        output = Path(os.environ['COASTAL_STALL_CAPTURE'])
        (output/'authority-pauses.json').write_text(json.dumps({
            'scope': '权威进程GC及超过12ms的原Simulation.step；只诊断，不作原生吞吐Gate。',
            'gc': events, 'slow_steps': slow_steps}, ensure_ascii=False), encoding='utf-8')


class StallProbe(DrivingProbe):
    instances: ClassVar[list] = []
    warm_graphics: ClassVar[bool] = False
    graphics_counts: ClassVar[bool] = False

    def __init__(self, *args, **kwargs):
        self.stall_timings = {}
        self.stall_previous_segments = set()
        self.stall_pauses = []
        self.stall_phase = None
        self.stall_roundtrips = False
        self.stall_warmed = []
        self.stall_gc_started = {}
        self.stall_gc_events = []
        self.stall_graphics_changes = []
        self.stall_previous_graphics = None
        super().__init__(*args, **kwargs)
        self.instances.append(self)
        gc.callbacks.append(self.record_gc)

    def record_gc(self, phase, info):
        generation = info['generation']
        if phase == 'start':
            self.stall_gc_started[generation] = time.perf_counter()
        else:
            started = self.stall_gc_started.pop(generation)
            self.stall_gc_events.append({'started_at': started,
                'wall_ms': (time.perf_counter()-started)*1000,
                'generation': generation, 'thread': current_thread().name})

    def measure(self, name, action, *args, **kwargs):
        wall, cpu = time.perf_counter(), time.thread_time()
        result = action(*args, **kwargs)
        self.stall_timings[name] = {'wall_ms': (time.perf_counter()-wall)*1000,
                                    'thread_cpu_ms': (time.thread_time()-cpu)*1000}
        return result

    def update(self, task):
        self.stall_timings = {}
        return self.measure('update', super().update, task)

    def _ShowBase__igLoop(self, task):
        return self.measure('renderFrame', super()._ShowBase__igLoop, task)

    def _ShowBase__garbageCollectStates(self, task):
        return self.measure('state_collection', super()._ShowBase__garbageCollectStates, task)

    def record_frame(self):
        if not self.probe_frames or 'main_phases' in self.probe_frames[-1]:
            return
        segments = set(self.scene.segment_nodes)
        self.probe_frames[-1].update(main_phases=dict(self.stall_timings),
                                    finished_at=time.perf_counter(),
                                    newly_visible_segments=sorted(segments-self.stall_previous_segments),
                                    removed_segments=sorted(self.stall_previous_segments-segments),
                                    stream_phase=self.scene.segment_work['phase'])
        self.stall_previous_segments = segments
        if self.graphics_counts:
            started = time.perf_counter()
            prepared = self.win.getGsg().getPreparedObjects()
            counts = {'shaders': prepared.getNumPreparedShaders(),
                      'textures': prepared.getNumPreparedTextures(),
                      'vertex_buffers': prepared.getNumPreparedVertexBuffers(),
                      'index_buffers': prepared.getNumPreparedIndexBuffers()}
            self.probe_frames[-1]['graphics_observation_ms'] = (time.perf_counter()-started)*1000
            if counts != self.stall_previous_graphics:
                self.stall_graphics_changes.append({'frame': self.probe_frames[-1]['render_frame'],
                    'distance_m': self.probe_frames[-1]['progress_m'], 'counts': counts})
                self.stall_previous_graphics = counts

    def probe_frame(self, task):
        if self.probe_driver and not self.stall_roundtrips:
            self.session.frame = partial(self.measure, 'snapshot_roundtrip', self.session.frame)
            self.session.camera_position = partial(self.measure, 'camera_roundtrip', self.session.camera_position)
            self.stall_roundtrips = True
        if self.session is not None and self.session.phase != self.stall_phase:
            if self.session.phase == Phase.PAUSED or self.stall_phase == Phase.PAUSED:
                self.stall_pauses.append({'wall_s': time.perf_counter()-self.probe_started,
                                          'phase': self.session.phase.value})
            self.stall_phase = self.session.phase
        result = super().probe_frame(task)
        self.record_frame()
        return result

    def probe_finish(self):
        self.record_frame()
        super().probe_finish()
        (self.probe_output/'phase-scope.json').write_text(json.dumps({
            'scope': '正常独立120Hz/默认Draw主线程逐帧分项，CPU为本线程且Windows计时较粗；不含Draw/物理线程，不把renderFrame等待归为GPU或CPU。',
            'pause_events': self.stall_pauses, 'end_distance': self.probe_end_distance,
            'warm_graphics': self.warm_graphics, 'warmed_batches': self.stall_warmed,
            'main_python_gc': self.stall_gc_events,
            'graphics_changes': self.stall_graphics_changes,
            'limits': '轻量诊断仍有开销；整机帧耗不等于完整物理吞吐Gate。'},
            ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--end-distance', type=int, choices=(270, 450, 900), default=450)
    parser.add_argument('--warm-graphics', action='store_true', help='仅诊断提前逐批准备原远树GPU资源')
    parser.add_argument('--gc-rate', type=float, help='仅诊断原生状态缓存每帧回收比例')
    parser.add_argument('--graphics-counts', action='store_true', help='仅观察已准备的显卡资源数量变化，不等待上传或查询GPU耗时')
    args = parser.parse_args()
    import local_kcd_drive

    import session_process

    os.environ['COASTAL_STALL_CAPTURE'] = str(args.output.resolve())
    session_process._serve = capture_serve
    original_batches = local_kcd_drive.tree_batch_steps
    if args.warm_graphics:
        def warmed_batches(root, kit):
            for phase in original_batches(root, kit):
                if phase == 'local-far-tree-batch':
                    app = StallProbe.instances[-1]
                    for batch in root.findAllMatches('**/local-far-tree-batch-*'):
                        if not batch.hasPythonTag('probe-graphics-warmed'):
                            batch.prepareScene(app.win.getGsg())
                            batch.setPythonTag('probe-graphics-warmed', True)
                            app.stall_warmed.append({'node': batch.getName(), 'queued_at': time.perf_counter()})
                yield phase

        local_kcd_drive.tree_batch_steps = warmed_batches
    StallProbe.warm_graphics = args.warm_graphics
    StallProbe.graphics_counts = args.graphics_counts
    check_interactive_local_drive.DrivingProbe = StallProbe
    try:
        check(args.output.resolve(), False, False, end_distance=args.end_distance,
              gc_rate=args.gc_rate, trace_state_cache=True)
    finally:
        local_kcd_drive.tree_batch_steps = original_batches
        for app in StallProbe.instances:
            gc.callbacks.remove(app.record_gc)
        if StallProbe.instances and not (args.output/'summary.json').exists():
            app = StallProbe.instances[-1]
            (args.output/'partial-phases.json').write_text(json.dumps({
                'completed': False, 'frames': app.probe_frames, 'pause_events': app.stall_pauses,
                'scope': '未完成目标距离，部分帧/暂停原样保留，不能冒称正常性能通过。'},
                ensure_ascii=False), encoding='utf-8')
