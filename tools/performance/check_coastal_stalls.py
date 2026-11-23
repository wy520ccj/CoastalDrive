"""单窗口滨海正常驾驶分项诊断；不改变120Hz、画面或会话消息顺序。"""

import argparse
import gc
import hashlib
import json
import multiprocessing
import os
import sys
import time
from functools import partial
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import current_thread

from check_coastal_modes import CoastalProbe

from session_clock import PRESENTATION_DELAY


def capture_authority(*arguments):
    """只在诊断子进程包裹原调用，保存时钟/GC与响应的共同墙钟时间。"""
    import session_process
    import simulation
    from session import Session
    from session_clock import SessionClock
    from simulation import Simulation

    interval = os.environ.get('COASTAL_STALL_SWITCH_INTERVAL')
    if interval is not None:
        sys.setswitchinterval(float(interval))
    events,steps,collections,started_gc = [],[],[],{}
    original_step = Simulation.step
    original_reply = session_process._reply
    original_output = session_process._output
    original_encode = session_process._encode_frame
    original_camera = Session.camera_position
    original_advance = simulation.advance_world
    step_details = {}

    def advance(*args, **kwargs):
        step_details['substeps'] = kwargs['substeps']
        return original_advance(*args,**kwargs)

    simulation.advance_world = advance
    if os.environ.get('COASTAL_STALL_YIELD')=='1':
        original_tick = SessionClock.tick

        def yielding_tick(clock):
            result = original_tick(clock)
            time.sleep(0)
            return result

        SessionClock.tick = yielding_tick

    def timed(name, action, *args, **kwargs):
        started,cpu = time.perf_counter(),time.thread_time()
        result = action(*args,**kwargs)
        events.append({'kind':name,'started_at':started,'wall_ms':(time.perf_counter()-started)*1000,
                       'thread_cpu_ms':(time.thread_time()-cpu)*1000,'thread':current_thread().name})
        return result

    def step(world, *args, **kwargs):
        started,cpu = time.perf_counter(),time.thread_time()
        refinement = world._collision_refinement_ticks
        result = original_step(world,*args,**kwargs)
        steps.append({'started_at':started,'wall_ms':(time.perf_counter()-started)*1000,
                      'thread_cpu_ms':(time.thread_time()-cpu)*1000,'tick':world._tick,
                      'substeps':step_details['substeps'],'refinement_before':refinement,
                      'refinement_after':world._collision_refinement_ticks,'impacts':len(world._impact_events)})
        return result

    def collected(phase, info):
        key = info['generation']
        if phase=='start':
            started_gc[key] = time.perf_counter()
        else:
            started = started_gc.pop(key)
            collections.append({'started_at':started,'wall_ms':(time.perf_counter()-started)*1000,
                                'generation':key,'thread':current_thread().name})

    Simulation.step = step
    session_process._reply = partial(timed,'reply',original_reply)
    session_process._output = partial(timed,'output',original_output)
    session_process._encode_frame = partial(timed,'encode',original_encode)
    Session.camera_position = lambda session,*args: timed('camera',original_camera,session,*args)
    gc.callbacks.append(collected)
    try:
        session_process._serve(*arguments)
    finally:
        gc.callbacks.remove(collected)
        report = {'pid':os.getpid(),'switch_interval':sys.getswitchinterval(),
                  'yield_between_ticks':os.environ.get('COASTAL_STALL_YIELD')=='1',
                  'events':events,'steps':steps,'python_gc':collections,
                  'source_modules':{name:{'path':sys.modules[name].__file__,
                      'sha256':hashlib.sha256(Path(sys.modules[name].__file__).read_bytes()).hexdigest()}
                      for name in ('simulation','tire_drivetrain','wheel_contact_kernels','mechanical_kernels',
                                   'session','session_clock','session_process')},
                  'scope':'原独立时钟/世界/编码和查询不变，仅包裹分项；分配记录会增加观测开销。'}
        output = Path(os.environ['COASTAL_STALL_CAPTURE'])/f'authority-{os.getpid()}.json'
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


class CoastalStallProbe(CoastalProbe):
    graphics_counts = False

    def __init__(self, output, **options):
        self.timings = {}
        self.snapshot_frame = {}
        self.measured_session = None
        self.gc_started = {}
        self.gc_events = []
        self.resource_changes = []
        self.last_resources = None
        gc.callbacks.append(self.record_gc)
        super().__init__(output,**options)

    def record_gc(self, phase, info):
        key = info['generation']
        if phase=='start':
            self.gc_started[key] = time.perf_counter()
        else:
            started = self.gc_started.pop(key)
            elapsed = (time.perf_counter()-started)*1000
            if elapsed>.1:
                self.gc_events.append({'started_at':started,'wall_ms':elapsed,
                                       'generation':key,'thread':current_thread().name})

    def measure(self, name, action, *args, **kwargs):
        wall,cpu = time.perf_counter(),time.thread_time()
        result = action(*args,**kwargs)
        self.timings[name] = {'wall_ms':(time.perf_counter()-wall)*1000,
                             'thread_cpu_ms':(time.thread_time()-cpu)*1000}
        if name=='snapshot_roundtrip':
            output = self.session.output
            requested = kwargs['sampled_at']-output.timeline_origin-(output.dropped_time-output.dropped_epoch)-PRESENTATION_DELAY
            self.snapshot_frame = {'requested_time':requested,'visible_time':result.time,
                                   'latest_time':self.session.history[-1].time,
                                   'underflow':requested>self.session.history[-1].time+1e-6}
        return result

    def update(self, task):
        self.timings = {}
        if self.session is not self.measured_session:
            self.measured_session = self.session
            self.session.frame = partial(self.measure,'snapshot_roundtrip',self.session.frame)
            self.session.camera_position = partial(self.measure,'camera_roundtrip',self.session.camera_position)
        return self.measure('update',super().update,task)

    def apply_scene(self, *args):
        return self.measure('apply_scene',super().apply_scene,*args)

    def _ShowBase__igLoop(self, task):
        return self.measure('renderFrame',super()._ShowBase__igLoop,task)

    def _ShowBase__garbageCollectStates(self, task):
        return self.measure('state_collection',super()._ShowBase__garbageCollectStates,task)

    def attach_phases(self):
        if not self.probe_rows or 'phases' in self.probe_rows[-1]:
            return
        row = self.probe_rows[-1]
        row.update(phases=dict(self.timings),finished_at=time.perf_counter(),
                   authority_backlog_ms=self.session.stepper.backlog_time*1000,
                   presentation=dict(self.snapshot_frame))
        if not self.graphics_counts:
            return
        objects = self.win.getGsg().getPreparedObjects()
        counts = [objects.getNumPreparedShaders(),objects.getNumPreparedTextures(),
                  objects.getNumPreparedVertexBuffers(),objects.getNumPreparedIndexBuffers()]
        if counts!=self.last_resources:
            self.resource_changes.append({'mode':row['mode'],'progress_m':row['progress_m'],
                                          'finished_at':row['finished_at'],'counts':counts})
            self.last_resources = counts

    def check_frame(self, task):
        result = super().check_frame(task)
        self.attach_phases()
        return result

    def write_report(self, completed):
        self.attach_phases()
        super().write_report(completed)
        report = {'scope':'单实例正常独立120Hz/默认Draw；分项计时有观测成本，不作为正式性能Gate。',
                  'main_python_gc':self.gc_events,'resource_changes':self.resource_changes,
                  'resource_order':['shaders','textures','vertex_buffers','index_buffers'],
                  'limits':'renderFrame含原生工作和等待；thread_cpu只属于主线程，Windows计时粒度较粗。',
                  'slow_frames':[row for row in self.probe_rows if row['wall_frame_ms']>25
                                 and not row['after_capture']]}
        (self.probe_output/'phases.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--authority',action='store_true')
    parser.add_argument('--graphics-counts',action='store_true')
    parser.add_argument('--switch-interval',type=float)
    parser.add_argument('--blocking-baseline',action='store_true',help='仅诊断：使用本轮保存的旧frame函数')
    parser.add_argument('--yield-between-ticks',action='store_true',help='仅诊断：物理完成步之间交还线程执行机会')
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    os.environ['COASTAL_STALL_CAPTURE'] = str(output)
    if arguments.yield_between_ticks:
        if not arguments.authority:
            parser.error('完成步交还线程试验须与--authority一起使用')
        os.environ['COASTAL_STALL_YIELD'] = '1'
    if arguments.switch_interval is not None:
        if not arguments.authority or not 0<arguments.switch_interval<.1:
            parser.error('切换间隔须与--authority一起使用，范围(0,.1)秒')
        os.environ['COASTAL_STALL_SWITCH_INTERVAL'] = str(arguments.switch_interval)
    if arguments.authority:
        import session_process

        session_process._serve = capture_authority
    if arguments.blocking_baseline:
        import session_process

        baseline = Path(__file__).resolve().parents[2]/'logs/visual-extend-20261028/session-process-before-covered-frame.py'
        spec = spec_from_file_location('coastal_frame_baseline',baseline)
        module = module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        session_process.SessionProcess.frame = module.SessionProcess.frame
    CoastalStallProbe.graphics_counts = arguments.graphics_counts
    source_root = Path(__file__).resolve().parents[2]
    files = ['src/session_process.py','src/session_clock.py','src/simulation.py',
             'tools/performance/check_coastal_stalls.py']
    manifest = {'arguments':vars(arguments)|{'output':str(output)},
                'source_sha256':{name:hashlib.sha256((source_root/name).read_bytes()).hexdigest() for name in files}}
    (output/'source-at-start.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    app = CoastalStallProbe(output)
    try:
        app.run()
    finally:
        if not (output/'summary.json').is_file():
            app.write_report(False)
        gc.callbacks.remove(app.record_gc)
        app.close_game()
