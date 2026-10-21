"""固定路线窗口短测，记录尾延迟、窗口状态和测量期间丢时。"""

import argparse
import ctypes
import gc
import importlib
import json
import os
import subprocess
import sys
import time
from collections import Counter, deque
from ctypes import wintypes
from functools import partial, wraps
from itertools import pairwise
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


def audited_worker(output, connection):
    """启动阶段记录工作进程实际模块，不在采样段插入计时或文件操作。"""
    import physics_workers

    modules = {name: importlib.import_module(name).__file__ for name in (
        'physics_workers','tire_drivetrain','vehicle_tires','vehicle_suspension',
        'suspension_contacts','triangle_support','vehicle_tire_step')}
    (Path(output)/f'worker-source-{os.getpid()}.json').write_text(json.dumps(modules), encoding='utf-8')
    physics_workers._worker_loop(connection)


def physics_progress(session):
    """从权威状态取进度；隔离原型必须覆写为后端即时采样，不能使用显示缓存。"""
    from session_process import SessionProcess

    if isinstance(session,SessionProcess):
        return session.progress()
    return session.current.tick, session.stepper.dropped_time, time.perf_counter()


def traced_authority(output, *arguments):
    """诊断实际权威进程；分项包含调用，不能将嵌套耗时相加。"""
    import session_process
    import tire_drivetrain
    import world_step
    from npc_physics import TrafficVehicle
    from race import BestTimes
    from session import Session
    from simulation import Simulation
    from streamed_road import StreamedRoad
    from tire_drivetrain import DrivetrainInput
    from vehicle import Vehicle
    from vehicle_tire_step import TireAdvanceInput

    records = {}
    gc_started = {}
    gc_pauses = []

    def collect(phase, info):
        generation = info['generation']
        if phase == 'start':
            gc_started[generation] = time.perf_counter(), time.thread_time()
        else:
            started, cpu_started = gc_started.pop(generation)
            gc_pauses.append({'started_at':started, 'generation':generation,
                              'wall_ms':(time.perf_counter()-started)*1000,
                              'cpu_ms':(time.thread_time()-cpu_started)*1000,
                              'collected':info['collected']})

    gc.callbacks.append(collect)

    def timed(name, function):
        @wraps(function)
        def call(*args, **kwargs):
            wall, cpu = time.perf_counter(), time.thread_time()
            try:
                return function(*args, **kwargs)
            finally:
                duration = time.perf_counter()-wall, time.thread_time()-cpu
                record = records.setdefault(name, {'count': 0, 'wall': 0., 'cpu': 0.,
                                                   'samples': deque(maxlen=8192), 'slow_calls': deque(maxlen=16),
                                                   'wall_max':0.})
                record['count'] += 1
                record['wall'] += duration[0]
                record['wall_max'] = max(record['wall_max'], duration[0])
                record['cpu'] += duration[1]
                record['samples'].append(duration[0])
                if duration[0] >= .020:
                    record['slow_calls'].append({'started_at': wall, 'wall_ms': duration[0]*1000,
                                                 'cpu_ms': duration[1]*1000})
        return call

    for owner, attribute, name in (
        (Session, 'tick', 'session-tick'), (Simulation, 'step', 'simulation-step'),
        (Simulation, '_drive_traffic', 'traffic-decision'),
        (Simulation, '_update_stream', 'physics-stream-update'),
        (StreamedRoad, 'add', 'physics-road-attach'),
        (Simulation, 'snapshot', 'snapshot'),
        (world_step, 'advance_world', 'advance-world'),
        (TireAdvanceInput, 'solve', 'complete-solve'),
        (DrivetrainInput, 'solve', 'serial-drivetrain-solve'),
        (TrafficVehicle, 'prepare_command', 'npc-command'),
        (TrafficVehicle, 'physics_stages', 'npc-force'),
        (TrafficVehicle, 'after_step', 'npc-observation'),
        (Vehicle, 'after_step', 'player-observation'),
        (Simulation, '_read_impact_contacts', 'impact-observation'),
        (Simulation, '_count_player_collisions', 'collision-count'),
        (tire_drivetrain, 'joint_solve', 'native-joint-solve'),
        (Session, 'camera_position', 'camera-query'),
        (BestTimes, 'record', 'score-file-update'),
    ):
        setattr(owner, attribute, timed(name, getattr(owner, attribute)))
    # Simulation在导入时绑定函数，诊断覆写须指向同一个计时入口。
    import simulation
    simulation.advance_world = world_step.advance_world
    try:
        session_process._serve(*arguments)
    finally:
        gc.callbacks.remove(collect)
        result = {}
        for name, record in records.items():
            values = sorted(record['samples'])
            result[name] = {'count': record['count'],
                'wall_mean_ms': record['wall']/record['count']*1000,
                'cpu_mean_ms': record['cpu']/record['count']*1000,
                'wall_max_ms':record['wall_max']*1000,
                'wall_p95_ms': values[int((len(values)-1)*.95)]*1000,
                'wall_p99_ms': values[int((len(values)-1)*.99)]*1000}
            result[name]['slow_calls'] = list(record['slow_calls'])
        (Path(output)/'authority-timing.json').write_text(json.dumps(result), encoding='utf-8')
        (Path(output)/'authority-gc.json').write_text(json.dumps(gc_pauses), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shape", choices=("straight", "curves", "hills"), default="hills")
    parser.add_argument("--seconds", type=float, default=45)
    parser.add_argument('--extended', action='store_true', help='显式延长到60秒以上、最多300秒；默认仍为短测')
    parser.add_argument("--baseline-compute", action="store_true")
    parser.add_argument("--pipeline", choices=("single", "draw", "cull-draw"), default="draw")
    parser.add_argument('--vsync', choices=('on', 'off'), default='on', help='只在诊断进程改变垂直同步，正式入口保持开启')
    parser.add_argument("--track", choices=("coastal", "endless"), default="endless")
    parser.add_argument("--vehicle-design")
    parser.add_argument("--driving-mode", choices=("game", "simulation"), default="game")
    parser.add_argument('--game-mode', choices=('free_drive', 'time_trial', 'distance_challenge'))
    parser.add_argument('--results-seconds', type=float, default=0., help='完赛后继续绘制结算；物理吞吐只取驾驶采样区间')
    parser.add_argument('--audio', action='store_true', help='隔离设置/成绩，启用正式OpenAL驾驶声音和电台')
    parser.add_argument("--source", type=Path, default=ROOT / "src")
    parser.add_argument("--trace-streaming", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--independent-clock", action="store_true")
    parser.add_argument("--steering", type=float, default=0., help="车尾运动画面复核用恒定转向")
    parser.add_argument("--gc-rate",type=float,help="Panda状态缓存分批回收诊断")
    parser.add_argument("--switch-interval",type=float,help="Python物理/绘制线程切换间隔诊断")
    parser.add_argument("--trace-phases",action="store_true",help="以各调用线程CPU时间记录真实阶段；诊断用")
    parser.add_argument('--physics-workers',type=int,help='显式数值进程数，默认沿用游戏设置')
    parser.add_argument('--traffic-count',type=int,help='固定实测交通车辆数，模型沿用所选驾驶模式')
    parser.add_argument('--trace-draw-poses',action='store_true',help='记录实际Draw线程的车身/相机变换')
    args = parser.parse_args()
    if args.extended and not 60 < args.seconds <= 300:
        parser.error('延长窗口须在60秒以上、300秒以内')
    if not args.extended and not 30 <= args.seconds <= 60:
        parser.error("短测限于30–60秒")
    if not -1.<=args.steering<=1.:
        parser.error("转向须在[-1,1]内")
    if args.gc_rate is not None and not 0.<args.gc_rate<=1.:
        parser.error("缓存回收比例须在(0,1]内")
    if args.switch_interval is not None and not 0.<args.switch_interval<1.:
        parser.error("线程切换间隔须在(0,1)秒内")
    if args.traffic_count is not None and args.traffic_count < 0:
        parser.error('交通车数须非负')
    if args.switch_interval is not None:
        sys.setswitchinterval(args.switch_interval)
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    sys.path.insert(0, str(args.source.resolve()))
    import paths
    paths.resource_root = lambda: ROOT
    streaming_phases = {}
    tracing = False
    gc_started = {}
    gc_pauses = []

    def cyclic_collection(phase, info):
        generation = info['generation']
        if phase == 'start':
            gc_started[generation] = time.perf_counter()
        else:
            started = gc_started.pop(generation)
            if tracing:
                gc_pauses.append({'generation':generation, 'ms':(time.perf_counter()-started)*1000,
                                  'collected':info['collected'], 'started_at':started})

    gc.callbacks.append(cyclic_collection)
    if args.trace_streaming:
        from environment import expressway_route

        original_steps = expressway_route.segment_steps

        def traced_steps(*a, **kw):
            steps = original_steps(*a, **kw)
            try:
                while True:
                    started = time.perf_counter()
                    try:
                        phase = next(steps)
                    except StopIteration:
                        return
                    elapsed = (time.perf_counter()-started)*1000
                    if tracing:
                        values = streaming_phases.setdefault(phase, {"count": 0, "total_ms": 0, "max_ms": 0})
                        values["count"] += 1
                        values["total_ms"] += elapsed
                        values["max_ms"] = max(values["max_ms"], elapsed)
                    yield phase
            finally:
                steps.close()

        expressway_route.segment_steps = traced_steps
    if args.baseline_compute:
        for name in ("highway_curve", "vehicle", "simulation", "ui.hud", "application"):
            source = subprocess.check_output(
                ["git", "show", f"f9431dd:src/{name.replace('.', '/')}.py"],
                cwd=ROOT, text=True, encoding="utf-8",
            )
            module = ModuleType(name)
            sys.modules[name] = module
            exec(compile(source, name, "exec"), module.__dict__)  # noqa: S102
        # 保留PERF-02已交接的精确采样缓存，只隔离本轮计算修改。
        from functools import lru_cache

        curve_type = sys.modules["highway_curve"].HighwayCurve
        original_init = curve_type.__init__

        def cached_init(self, *a, **kw):
            original_init(self, *a, **kw)
            self.sample = lru_cache(maxsize=8192)(self.sample)

        curve_type.__init__ = cached_init
    from panda3d.core import (
        CallbackObject,
        ClockObject,
        ConfigVariableBool,
        Filename,
        RenderState,
        Thread,
        TransformState,
        loadPrcFileData,
    )

    from application import CoastalDrive
    from controls import ConstantController
    from driving_modes import DrivingMode
    from simulation import Control

    if args.traffic_count is not None:
        from simulation import Simulation

        original_simulation_init = Simulation.__init__
        original_simulation_reset = Simulation.reset

        def fixed_traffic(self, *arguments, **keywords):
            keywords['traffic_count'] = args.traffic_count
            original_simulation_init(self, *arguments, **keywords)

        Simulation.__init__ = fixed_traffic

        def fixed_traffic_reset(self, *arguments, **keywords):
            self.traffic_count = args.traffic_count
            original_simulation_reset(self, *arguments, **keywords)

        Simulation.reset = fixed_traffic_reset

    EnduranceDriver = importlib.import_module('endurance_check').EnduranceDriver

    # 耐久工具的历史入口会插入当前src；源码对照必须在加载游戏前锁定指定模块。
    sys.path.insert(0, str(args.source.resolve()))
    source_modules = {} if args.baseline_compute else {name: importlib.import_module(name).__file__ for name in (
        'application','simulation','vehicle','world_step','physics_workers','tire_drivetrain',
        'vehicle_tires','suspension_contacts','triangle_support','coastal_map')}
    if not args.baseline_compute:
        for name,filename in source_modules.items():
            if Path(filename).resolve().parent != args.source.resolve():
                raise RuntimeError(f'窗口源码对照未加载指定模块：{name}: {filename}')
        import physics_workers

        physics_workers._worker_loop = partial(audited_worker, str(args.output.resolve()))

    phase_samples = {}
    measuring_phases = False

    def timed(name, function):
        @wraps(function)
        def call(*arguments, **keywords):
            if not measuring_phases:
                return function(*arguments,**keywords)
            wall,cpu = time.perf_counter(),time.thread_time()
            try:
                return function(*arguments,**keywords)
            finally:
                durations = time.perf_counter()-wall,time.thread_time()-cpu
                record = phase_samples.setdefault(name,{'count':0,'wall':0.,'cpu':0.,'samples':deque(maxlen=4096),
                                                        'slow_calls':deque(maxlen=16), 'wall_max':0.})
                record['count'] += 1
                record['wall'] += durations[0]
                record['wall_max'] = max(record['wall_max'], durations[0])
                record['cpu'] += durations[1]
                record['samples'].append(durations)
                if durations[0] >= .020:
                    record['slow_calls'].append({'started_at':wall,'wall_ms':durations[0]*1000,
                                                 'cpu_ms':durations[1]*1000})
        return call

    if args.trace_phases:
        from direct.showbase.ShowBase import ShowBase

        import session_process
        import world_step
        from highway_driver import HighwayDriver
        from physics_workers import PhysicsWorkers
        from session import Session
        from session_process import SessionProcess

        session_process._serve = partial(traced_authority, str(args.output.resolve()))
        from simulation import Simulation
        from soundscape import Soundscape
        from streamed_road import StreamedRoad
        from vehicle import Vehicle

        for owner,attribute,name in (
            (CoastalDrive,'update','window-update'),(Session,'frame','render-snapshot'),
            (CoastalDrive,'apply_scene','scene-application'),
            (CoastalDrive,'pace_frame','frame-pacing'),
            (CoastalDrive,'refresh_panel','panel-refresh'),
            (Soundscape,'update','soundscape-update'),
            (ShowBase,'_ShowBase__audioLoop','audio-device-update'),
            (SessionProcess,'frame','remote-frame'),
            (SessionProcess,'camera_position','camera-roundtrip'),
            (Session,'tick','physical-session-tick'),(Simulation,'step','physical-world-tick'),
            (Vehicle,'after_step','vehicle-observation'),(PhysicsWorkers,'submit','worker-submit'),
            (PhysicsWorkers,'_receive','worker-receive'),
            (world_step,'static_support_shapes','static-geometry'),
            (Simulation,'_drive_traffic','traffic-decision'),
            (Simulation,'_update_stream','physics-stream-update'),
            (StreamedRoad,'add','physics-road-attach'),
            (HighwayDriver,'plan','traffic-plan'),
            (HighwayDriver,'control','traffic-control'),
            (ShowBase,'_ShowBase__garbageCollectStates','panda-state-collection'),
            (ShowBase,'_ShowBase__igLoop','render-frame'),
        ):
            setattr(owner,attribute,timed(name,getattr(owner,attribute)))

    pipelines = {"single": "", "draw": "/Draw", "cull-draw": "Cull/Draw"}
    loadPrcFileData("performance-pipeline", "threading-model " + pipelines[args.pipeline])
    if args.gc_rate is not None:
        loadPrcFileData("performance-gc","garbage-collect-states-rate "+str(args.gc_rate))
    app = CoastalDrive(smoke=True, smoke_audio=args.audio, onscreen=True, track=args.track, road_shape=args.shape,
                       seed=23, output=args.output, render_size=(1920, 1080),
                       threading_model=pipelines[args.pipeline],independent_clock=args.independent_clock,
                       sync_video=args.vsync == 'on',
                       vehicle_design_id=args.vehicle_design, driving_mode=DrivingMode(args.driving_mode),
                       physics_workers=args.physics_workers)
    audio_managers = [{'type': manager.getType().getName(), 'valid': manager.isValid()}
                      for manager in app.sfxManagerList]
    if args.audio and not all(manager['type'] == 'OpenALAudioManager' and manager['valid']
                              for manager in audio_managers):
        app.close_game()
        raise RuntimeError('带声音测量未获得有效OpenAL设备，不能作为正式声音负载收据')
    if args.game_mode is not None:
        from race import GameMode

        app.session.start(mode=GameMode(args.game_mode), countdown=False)
        app.sync_scene()
    if args.traffic_count is not None and len(app.session.current.traffic) != args.traffic_count:
        from highway_run import TRAFFIC_DENSITIES

        densities = {density.cars: name for name, density in TRAFFIC_DENSITIES.items()}
        if args.track != 'endless' or args.traffic_count not in densities:
            app.close_game()
            raise ValueError('窗口交通数量须对应真实无限高速车流选项')
        # 与游戏菜单相同，重建会话时读取车流密度；不能只检查数量或改显示快照。
        app.session.traffic_density = densities[args.traffic_count]
        app.session.start(countdown=False)
        app.sync_scene()
        if len(app.session.current.traffic) != args.traffic_count:
            app.close_game()
            raise RuntimeError('窗口启动后的实际交通车数与指定工况不一致')
    app.taskMgr.remove("finish-smoke")
    from route_driver import RouteDriver

    from session_process import SessionProcess

    controller = (EnduranceDriver(app.session.simulation, 724) if args.track == "endless"
                  else RouteDriver(90) if args.game_mode == 'time_trial'
                  else ConstantController(Control(throttle=.3,steering=args.steering)))
    if isinstance(app.session,SessionProcess):
        app.session.set_controller(controller,bind_world=args.track == 'endless')
    else:
        app.session.set_controller(controller)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
    handle = app.win.getWindowHandle().getIntHandle()
    user32.ShowWindow(handle, 9)
    if not user32.SetForegroundWindow(handle):
        # 独立工具进程不一定获得Windows的前台许可；只在启动时挂接一次输入队列。
        # 无论激活成败立即解除挂接，采样仍逐秒核对真实窗口状态。
        current_thread = ctypes.WinDLL('kernel32').GetCurrentThreadId()
        foreground_thread = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(),None)
        attached = bool(foreground_thread and foreground_thread != current_thread
                        and user32.AttachThreadInput(current_thread,foreground_thread,True))
        try:
            user32.SetForegroundWindow(handle)
        finally:
            if attached:
                user32.AttachThreadInput(current_thread,foreground_thread,False)
    samples, windows = [], []
    previous_progress = app.session.simulation.road.locate(app.session.current.player)[0]
    route_distance = 0.
    work_samples = []
    previous = time.perf_counter()
    last_second = -1
    start_dropped = None
    start_tick = None
    sample_started_at = None
    final = {}
    audio_samples = []
    driving_end_progress = None
    results_started_at = None
    if args.profile:
        import cProfile
        profiler = cProfile.Profile()
    draw_times = []
    draw_poses = []
    measuring_draw = False

    def count_draw(data):
        if measuring_draw:
            now = time.perf_counter()
            draw_times.append(now)
            if args.trace_draw_poses:
                draw_poses.append((now,ClockObject.getGlobalClock().getFrameTime(),
                                   tuple(app.scene.player.getPos()),tuple(app.camera.getPos())))
        data.upcall()

    # 末个活动显示区每个实际窗口绘制调用一次；避免把主线程超前更新当作显示FPS。
    region = max((r for r in app.win.getDisplayRegions() if r.isActive()),
                 key=lambda r: r.getSort())
    region.setDrawCallback(CallbackObject.make(count_draw))

    def observe(task):
        nonlocal previous, last_second, start_dropped, start_tick, sample_started_at, measuring_draw, tracing, measuring_phases, previous_progress, route_distance
        nonlocal driving_end_progress, results_started_at
        now = time.perf_counter()
        road = app.session.simulation.road
        progress = road.locate(app.session.current.player)[0]
        route_distance += road.delta(progress, previous_progress)
        previous_progress = progress
        if task.time >= 3:
            if start_dropped is None:
                start_tick, start_dropped, sample_started_at = physics_progress(app.session)
                app.scene.segment_work["max_step_ms"] = 0
                measuring_draw = True
                tracing = True
                measuring_phases = args.trace_phases
                if args.profile:
                    profiler.enable()
            samples.append({"second": task.time, "ms": (now - previous) * 1000,
                            "physics_lag_ms": app.session.stepper.backlog_time * 1000,
                            "presentation_time": app._camera_time,
                            "phase":app.session.phase.value})
            work_samples.append(dict(app.scene.segment_work))
            if args.game_mode == 'time_trial' and app.session.phase.value == 'driving':
                driving_end_progress = physics_progress(app.session)
        previous = now
        if int(task.time) != last_second:
            props = app.win.getProperties()
            windows.append({"second": int(task.time), "minimized": props.getMinimized(),
                            "foreground": props.getForeground(),
                            "transform_states":TransformState.getNumStates(),
                            "render_states":RenderState.getNumStates()})
            last_second = int(task.time)
            if args.audio:
                audio_samples.append({
                    'second': int(task.time), 'loops_playing': app.soundscape.loops_playing,
                    'engine_status': [int(sound.status()) for sound in app.soundscape.engine_audio.loops],
                    'music_status': [int(sound.status()) for sound in app.soundscape.music.tracks],
                })
        trial_finished = args.game_mode == 'time_trial' and app.session.race.snapshot.finished
        if trial_finished and results_started_at is None:
            results_started_at = task.time
        results_observed = trial_finished and task.time - results_started_at >= args.results_seconds
        if task.time >= args.seconds or results_observed:
            if args.independent_clock:
                app.session.stop_clock()
            end_tick, end_dropped, sample_finished_at = physics_progress(app.session)
            # 完赛后Simulation正常停止；结算创建/绘制不能算进驾驶吞吐的分母。
            if trial_finished and driving_end_progress is not None:
                end_tick, end_dropped, sample_finished_at = driving_end_progress
            measuring_draw = False
            tracing = False
            measuring_phases = False
            if args.profile:
                profiler.disable()
                profiler.dump_stats(str(args.output / "main.prof"))
            values = sorted(row["ms"] for row in samples)
            lag_values = sorted(row["physics_lag_ms"] for row in samples)
            stalled_frames, stall_ms, maximum_stall_ms = 0, 0., 0.
            for before, after in pairwise(samples):
                if (before['phase'] == after['phase'] == 'driving'
                        and after['presentation_time'] <= before['presentation_time'] + 1e-9):
                    stalled_frames += 1
                    stall_ms += after['ms']
                    maximum_stall_ms = max(maximum_stall_ms, stall_ms)
                else:
                    stall_ms = 0.
            draw_values = sorted((b - a) * 1000 for a, b in pairwise(draw_times))
            valid = all(not w["minimized"] and w["foreground"] for w in windows)
            state = app.session.current
            distance = route_distance
            final.update({
                "kind": "extended foreground sample; not full-stage or human gate" if args.extended else "short window comparison; not final performance or human gate",
                "source": str(args.source.resolve()), "track": args.track,
                "vehicle_design": args.vehicle_design, "driving_mode": args.driving_mode,
                "game_mode":app.session.mode.value,
                "end_reason":'time_trial_finished' if trial_finished else 'time_limit',
                "phase":app.session.phase.value,
                "race_finished":app.session.race.snapshot.finished,
                "race_invalidated":app.session.race.snapshot.invalidated,
                "race_elapsed_seconds":app.session.race.snapshot.elapsed,
                "results_observed_seconds":task.time-results_started_at if trial_finished else 0.,
                "results_transition_frames":[row for row in samples if results_started_at is not None
                                             and abs(row['second']-results_started_at) <= .25],
                "controller": "highway-driver" if args.track == "endless" else 'route-driver-90' if args.game_mode == 'time_trial' else "constant-throttle-0.3",
                "constant_steering": args.steering,
                "gc_rate":1. if args.gc_rate is None else args.gc_rate,
                "transform_cache":ConfigVariableBool('transform-cache').getValue(),
                "sync_video_requested":args.vsync,
                "sync_video_configured":ConfigVariableBool('sync-video').getValue(),
                "render_clock_mode":int(ClockObject.getGlobalClock().getMode()),
                "render_clock_average_rate":ClockObject.getGlobalClock().getAverageFrameRate(),
                "traffic_models":(dict(Counter(app.session.simulation.traffic_models))
                                  if isinstance(app.session,SessionProcess)
                                  else dict(Counter(type(car).__name__ for car in app.session.simulation.npcs))),
                "python_switch_interval":sys.getswitchinterval(),
                "audio": "OpenAL driving audio and radio" if args.audio else "disabled by existing smoke mode",
                "audio_managers":audio_managers,
                "audio_samples":audio_samples,
                "tick": state.tick, "fixed_hz": 120,
                "shape": args.shape, "seed": 23, "resolution": [1920, 1080],
                "traffic_count": len(state.traffic), "pipeline": args.pipeline,
                "baseline_compute": args.baseline_compute, "window_sampling_valid": valid,
                "renderer": app.win.getGsg().getDriverRenderer(),
                "profile": args.profile,
                "draw_thread":Thread.getCurrentThread().getName() if args.trace_draw_poses else None,
                "source_modules":source_modules,
                "authority_source_modules":app.session.source_modules if isinstance(app.session,SessionProcess) else source_modules,
                "trace_phases":args.trace_phases,
                "python_gc_pauses":gc_pauses,
                "observation_time_origin":now-task.time,
                "phase_timing":{
                    name:{
                        'count':record['count'],'window_samples':len(record['samples']),
                        'wall_mean_ms':record['wall']/record['count']*1000,
                        'cpu_mean_ms':record['cpu']/record['count']*1000,
                        'wall_p95_ms':sorted(sample[0]*1000 for sample in record['samples'])[int((len(record['samples'])-1)*.95)],
                        'wall_max_ms':record['wall_max']*1000,
                        'cpu_p95_ms':sorted(sample[1]*1000 for sample in record['samples'])[int((len(record['samples'])-1)*.95)],
                        'slow_calls':list(record['slow_calls']),
                    } for name,record in phase_samples.items()
                },
                "independent_clock": args.independent_clock,
                "physics_workers": app.session.simulation._physics_workers.diagnostics() if app.session.simulation._physics_workers is not None else None,
                "streaming_phases": streaming_phases,
                "wall_seconds": task.time, "sample_seconds": sum(values) / 1000,
                "frames": len(values), "average_fps": len(values) * 1000 / sum(values),
                "display_draw_frames": len(draw_values),
                "display_draw_fps": len(draw_values) * 1000 / sum(draw_values),
                "display_draw_p95_ms": draw_values[int(len(draw_values) * .95)],
                "display_draw_p99_ms": draw_values[int(len(draw_values) * .99)],
                "display_draw_max_ms": max(draw_values),
                "display_draw_over_50ms": sum(v > 50 for v in draw_values),
                "p95_ms": values[int(len(values) * .95)],
                "p99_ms": values[int(len(values) * .99)], "max_ms": max(values),
                "frames_over_50ms": sum(v > 50 for v in values),
                "frames_over_100ms": sum(v > 100 for v in values),
                "dropped_simulation_seconds": end_dropped - start_dropped,
                "warmup_dropped_seconds": start_dropped, "distance_m": distance,
                "physics_start_tick":start_tick, "physics_end_tick":end_tick,
                "physics_sample_ticks":end_tick-start_tick,
                "physics_sample_simulated_seconds":(end_tick-start_tick)/120,
                "physics_sample_wall_seconds":sample_finished_at-sample_started_at,
                "physics_sample_hz":(end_tick-start_tick)/(sample_finished_at-sample_started_at),
                "physics_time_deficit_seconds":(sample_finished_at-sample_started_at)-(end_tick-start_tick)/120,
                "physics_lag_p95_ms":lag_values[int((len(lag_values)-1)*.95)],
                "physics_lag_max_ms":max(lag_values),
                "presentation_stalled_frames":stalled_frames,
                "presentation_stalled_frame_percent":100*stalled_frames/max(1,len(samples)-1),
                "presentation_maximum_stall_ms":maximum_stall_ms,
                "collisions": app.session.simulation.collision_count,
                "frames_slow": sorted(samples, key=lambda row: row["ms"], reverse=True)[:12],
                "segment_work_max_ms": max(w["frame_ms"] for w in work_samples),
                "segment_step_max_ms": max(w["max_step_ms"] for w in work_samples),
                "near_pending_frames": sum(w["near_pending"] > 0 for w in work_samples),
                "segment_work_slow": sorted(work_samples, key=lambda w: w["frame_ms"],
                                            reverse=True)[:12],
                "windows": windows,
                "passed": valid and distance > 600 and not app.session.simulation.collision_count,
            })
            final["short_performance_passed"] = (
                final["passed"] and final["display_draw_fps"] >= 70
                and final["display_draw_p95_ms"] <= 25
                and final["display_draw_over_50ms"] == 0
                and final["dropped_simulation_seconds"] == 0
                and final["physics_sample_hz"] >= 119.9
                and final["physics_lag_p95_ms"] <= 25
                and final["physics_lag_max_ms"] <= 100
                and final["near_pending_frames"] == 0
            )
            app.userExit()
            return task.done
        return task.cont

    app.taskMgr.add(observe, "performance-observe", sort=55)
    try:
        app.run()
        app.graphicsEngine.syncFrame()
        app.win.saveScreenshot(Filename.fromOsSpecific(str(args.output / "final.png")))
    finally:
        gc.callbacks.remove(cyclic_collection)
        app.close_game()
    final["git_head"] = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
    ).strip()
    worker_sources = [json.loads(path.read_text(encoding='utf-8')) for path in args.output.glob('worker-source-*.json')]
    final['worker_sources'] = worker_sources
    final['worker_source_valid'] = all(Path(filename).resolve().parent == args.source.resolve()
                                       for modules in worker_sources for filename in modules.values())
    if not final['worker_source_valid']:
        final['passed'] = final['short_performance_passed'] = False
    final["git_status"] = subprocess.check_output(
        ["git", "status", "--short"], cwd=ROOT, text=True, encoding="utf-8",
    ).strip()
    (args.output / "report.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
    if args.trace_draw_poses:
        (args.output / "draw-poses.json").write_text(json.dumps(draw_poses),encoding='utf-8')
    print(json.dumps({k: v for k, v in final.items()
                      if k not in ("windows", "frames_slow", "git_status", "segment_work_slow", "audio_samples")},
                     indent=2))
    return 0 if final["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
