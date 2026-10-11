"""独立会话进程持有唯一物理世界；窗口通过完成步快照和驾驶请求协作。"""

import traceback
from collections import deque
from dataclasses import dataclass, replace
from importlib import import_module
from itertools import pairwise
from multiprocessing import get_context
from threading import Thread
from time import perf_counter
from types import SimpleNamespace

from panda3d.core import Vec3

from controls import KeyboardController
from session import Phase, Session
from session_clock import PRESENTATION_DELAY
from simulation import FIXED_DT, interpolate, shift_snapshot
from traffic import Road


@dataclass(frozen=True)
class SessionOutput:
    history: tuple
    timeline_origin: float
    dropped_epoch: float
    previous: object
    current: object
    impacts: tuple
    phase: Phase
    countdown_ticks: int
    dropped_time: float
    race: object
    highway: object
    notice: str
    segments: tuple
    collisions: int
    rebases: int
    traffic_cycles: int
    initialisation_ticks: int


def _output(session):
    clock = session._clock
    if clock is None:
        previous, current = session.previous, session.current
        history, timeline_origin, dropped_epoch = (current,), perf_counter()-current.time, 0.
        impacts = ()
        segments = session.render_segments()
        status = (session.phase, session.countdown_ticks, session.stepper.dropped_time,
                  session.race.snapshot, session.highway.snapshot, session.notice,
                  session.simulation.collision_count, session.simulation.rebases,
                  session.simulation.traffic_cycles, session.simulation.initialisation_ticks)
    else:
        if clock.error is not None:
            raise clock.error
        with clock.output_lock:
            previous, current = clock.previous, clock.current
            reset = (clock.current.contact_epoch != session._ipc_epoch or session.phase != session._ipc_phase)
            history = tuple(state for state in clock.history if reset or state.tick > session._ipc_tick)
            session._ipc_tick, session._ipc_epoch, session._ipc_phase = clock.current.tick, clock.current.contact_epoch, session.phase
            timeline_origin, dropped_epoch = clock.timeline_origin, clock.timeline_dropped
            impacts = tuple(clock.impacts)
            clock.impacts.clear()
            segments = clock.segments
            status = clock.status
    phase, countdown, dropped, race, highway, notice, collisions, rebases, cycles, initial = status
    return SessionOutput(history, timeline_origin, dropped_epoch, previous, current, impacts, phase, countdown,
                         dropped, race, highway, notice, segments, collisions, rebases, cycles, initial)


def _metadata(session):
    sim = session.simulation
    return (sim.track, sim.seed, sim.road_shape, tuple(sim.props), session.vehicle_config,
            session.abs_enabled, session.tcs_enabled, session.esc_enabled, session.mode,
            tuple(type(car).__name__ for car in sim.npcs),
            {name:import_module(name).__file__ for name in
             ('session','session_clock','simulation','npc_physics','vehicle','world_step','tire_drivetrain')})


def _reply(connection, operation):
    try:
        result = operation()
    except Exception as error:  # noqa: BLE001 - 进程边界完整回传原始失败。
        connection.send((False, error, traceback.format_exc()))
    else:
        connection.send((True, result, None))


def _camera_loop(connection, session):
    try:
        while True:
            message = connection.recv()
            if message is None:
                return
            start, end, origin = message
            _reply(connection, lambda start=start, end=end, origin=origin:
                   tuple(session.camera_position(Vec3(*start), Vec3(*end), origin)))
    except EOFError:
        return
    finally:
        connection.close()


def _serve(connection, camera, input_word, seed, options, worker_loop):
    import physics_workers

    physics_workers._worker_loop = worker_loop
    session = None
    camera_thread = None
    try:
        session = Session(seed, **options, independent_clock=True)
        session.keyboard.input_word = input_word
        session.keyboard.input_reader = True
        session._ipc_tick, session._ipc_epoch, session._ipc_phase = -1, None, None
        camera_thread = Thread(target=_camera_loop, args=(camera, session), daemon=True)
        camera_thread.start()
        connection.send((True, (_output(session), _metadata(session)), None))
        while True:
            command, arguments = connection.recv()
            if command == 'close':
                break

            def execute(command=command, arguments=arguments):
                if command == 'frame':
                    if session._clock is None and session.phase in (Phase.DRIVING, Phase.COUNTDOWN):
                        session.frame(0.)
                    return _output(session)
                if command == 'progress':
                    clock = session._clock
                    if clock is None:
                        return session.current.tick, session.stepper.dropped_time, perf_counter()
                    with clock.output_lock:
                        return clock.current.tick, session.stepper.dropped_time, perf_counter()
                session.stop_clock()
                if command == 'start':
                    start_options, shape, density = arguments
                    session.road_shape, session.traffic_density = shape, density
                    session.start(**start_options)
                elif command == 'controller':
                    controller, bind_world = arguments
                    if bind_world:
                        controller.bind(session.simulation)
                    session.set_controller(controller)
                elif command == 'keyboard':
                    session.set_controller(session.keyboard)
                elif command == 'pause':
                    session.pause()
                elif command == 'resume':
                    session.resume()
                elif command == 'menu':
                    session.menu()
                elif command == 'finish':
                    session.finish()
                elif command == 'reset_player':
                    session.reset_player()
                elif command == 'driving_mode':
                    session.set_driving_mode(arguments[0])
                elif command == 'vehicle_config':
                    session.set_vehicle_config(arguments[0])
                elif command == 'abs':
                    session.set_abs_enabled(arguments[0])
                elif command == 'tcs':
                    session.set_tcs_enabled(arguments[0])
                elif command == 'esc':
                    session.set_esc_enabled(arguments[0])
                elif command != 'stop':
                    raise ValueError('未知独立会话命令：' + command)
                diagnostics = (session.simulation._physics_workers.diagnostics()
                               if session.simulation._physics_workers else None)
                return _output(session), _metadata(session), diagnostics

            _reply(connection, execute)
    except Exception as error:  # noqa: BLE001 - 启动与通信失败须传回窗口。
        connection.send((False, error, traceback.format_exc()))
    finally:
        if session is not None:
            session.close()
        if camera_thread is not None:
            camera_thread.join(5.)
        camera.close()
        connection.close()


class SimulationView:
    """只读道路描述和完成步统计；无Bullet对象、推进方法或另一套车辆状态。"""

    def diagnostics(self):
        return self.worker_statistics


class SessionProcess:
    def __init__(self, seed=0, *, track='coastal', road_shape='straight', driving_mode,
                 vehicle_config=None, scores=None, abs_enabled=None, tcs_enabled=None,
                 esc_enabled=None, physics_workers=0, independent_clock=True):
        import physics_workers as workers

        if not independent_clock:
            raise ValueError('独立会话进程必须使用独立120Hz时钟')
        self.seed, self.road_shape = seed, road_shape
        self.track_id = track
        self.driving_mode = driving_mode
        self.base_vehicle_config = vehicle_config
        self.traffic_density = 'normal'
        self.keyboard = KeyboardController(driving_mode.input_config)
        self.controller = self.keyboard
        self.camera_distance = 11.
        self.closed = False
        self.pending_frame = False
        self.output = None
        self.history = deque(maxlen=12)
        self.received_impacts = []
        self.simulation = SimulationView()
        self.simulation.input_config = driving_mode.input_config
        self.simulation._physics_workers = self.simulation if physics_workers else None
        self.simulation.worker_statistics = None
        self.stepper = SimpleNamespace(dropped_time=0.)
        self.race = SimpleNamespace(snapshot=None)
        self.highway = SimpleNamespace(snapshot=None)
        context = get_context('spawn')
        self.keyboard.input_word = context.Value('I', 0)
        self.connection, child = context.Pipe()
        self.camera, camera_child = context.Pipe()
        self.process = context.Process(target=_serve, args=(child, camera_child, self.keyboard.input_word, seed, {
            'track':track, 'road_shape':road_shape, 'driving_mode':driving_mode, 'scores':scores,
            'vehicle_config':vehicle_config, 'abs_enabled':abs_enabled, 'tcs_enabled':tcs_enabled,
            'esc_enabled':esc_enabled, 'physics_workers':physics_workers}, workers._worker_loop),
            name='CoastalDrive session')
        self.process.start()
        child.close()
        camera_child.close()
        try:
            output, metadata = self._receive()
            self._metadata(metadata)
            self._update(output)
        except BaseException:
            self.close()
            raise

    def _receive(self):
        if not self.connection.poll(60.):
            raise TimeoutError('独立会话未返回结果')
        try:
            ok, result, trace = self.connection.recv()
        except EOFError as error:
            raise RuntimeError('独立会话进程意外退出') from error
        if not ok:
            result.add_note(trace)
            raise result
        return result

    def _metadata(self, metadata):
        (track, seed, shape, props, config, self.abs_enabled, self.tcs_enabled,
         self.esc_enabled, self.mode, traffic_models, self.source_modules) = metadata
        self.seed, self.track_id = seed, track
        self.vehicle_config = config
        sim = self.simulation
        if self.output is None or (sim.track, sim.seed, sim.road_shape) != (track, seed, shape):
            sim.road = Road(track, seed=seed, shape=shape)
        sim.track, sim.seed, sim.road_shape, sim.props, sim.config = track, seed, shape, props, config
        sim.traffic_models = traffic_models

    def _update(self, output):
        if self.output is not None and output.current.contact_epoch != self.current.contact_epoch:
            self.received_impacts.clear()
        if output.phase in (Phase.MENU,Phase.PAUSED,Phase.COUNTDOWN):
            self.received_impacts.clear()
        if self.output is None or (output.current.contact_epoch != self.current.contact_epoch
                                  or output.phase != self.phase or output.current.tick < self.current.tick):
            self.history.clear()
        for state in output.history:
            if not self.history or state.tick > self.history[-1].tick:
                self.history.append(state)
        if not self.history:
            self.history.append(output.current)
        self.output = output
        self.previous, self.current = output.previous, output.current
        self.received_impacts.extend(output.impacts)
        self.phase, self.countdown_ticks = output.phase, output.countdown_ticks
        self.stepper.dropped_time = output.dropped_time
        self.race.snapshot, self.highway.snapshot, self.notice = output.race, output.highway, output.notice
        sim = self.simulation
        sim.origin_y = self.current.origin_y
        sim.road.origin_y = sim.origin_y
        sim.stream = SimpleNamespace(curve=sim.road.curve, segments=output.segments) if sim.track == 'endless' else None
        sim.collision_count, sim.rebases, sim.traffic_cycles = output.collisions, output.rebases, output.traffic_cycles
        sim.initialisation_ticks = output.initialisation_ticks

    def _finish_frame(self):
        if self.pending_frame:
            self._update(self._receive())
            self.pending_frame = False

    def _command(self, command, *arguments):
        self._finish_frame()
        self.connection.send((command, arguments))
        output, metadata, diagnostics = self._receive()
        self._metadata(metadata)
        self._update(output)
        self.simulation.worker_statistics = diagnostics
        self.simulation._physics_workers = self.simulation if diagnostics is not None else None

    def frame(self, elapsed, *, sampled_at=None):
        self.keyboard.publish_input()
        if self.pending_frame and self.connection.poll():
            self._finish_frame()
        if not self.pending_frame and self.phase in (Phase.DRIVING, Phase.COUNTDOWN):
            self.connection.send(('frame', ()))
            self.pending_frame = True
        if not self.process.is_alive():
            self._finish_frame()
            raise RuntimeError('独立会话进程意外退出')
        if self.phase not in (Phase.DRIVING, Phase.COUNTDOWN):
            impacts = tuple(self.received_impacts)
            self.received_impacts.clear()
            return replace(self.current,impacts=impacts)
        output = self.output
        sampled_at = perf_counter() if sampled_at is None else sampled_at
        display_time = sampled_at-output.timeline_origin-(output.dropped_time-output.dropped_epoch)-PRESENTATION_DELAY
        state = self.history[-1]
        if display_time <= self.history[0].time:
            state = self.history[0]
        else:
            for previous, current in pairwise(self.history):
                if display_time <= current.time:
                    state = interpolate(previous,current,(display_time-previous.time)/FIXED_DT)
                    break
        if state.origin_y != output.current.origin_y:
            state = shift_snapshot(state,output.current.origin_y)
        state = replace(state,time=min(output.current.time,max(self.history[0].time,display_time)))
        impacts = tuple(self.received_impacts)
        self.received_impacts.clear()
        return replace(state, impacts=impacts, contacts=output.current.contacts)

    def start(self, seed=None, *, countdown=True, mode=None, track=None, settle_initial=False):
        self._command('start', {'seed':seed, 'countdown':countdown, 'mode':mode, 'track':track,
                               'settle_initial':settle_initial}, self.road_shape, self.traffic_density)
        self.keyboard.clear()
        self.keyboard.direction = 1
        self.controller = self.keyboard
        self.received_impacts.clear()

    def set_controller(self, controller, *, bind_world=False):
        if controller is self.keyboard:
            self._command('keyboard')
        else:
            self._command('controller', controller, bind_world)
        self.controller = controller
        self.keyboard.clear()

    def stop_clock(self):
        self._command('stop')

    def progress(self):
        """性能计时直接读取权威进度，不能把显示缓存当物理完成时间。"""
        self._finish_frame()
        self.connection.send(('progress', ()))
        return self._receive()

    def pause(self):
        self._command('pause')
        self.keyboard.clear()

    def resume(self):
        self._command('resume')
        self.keyboard.clear()

    def menu(self):
        self._command('menu')
        self.keyboard.clear()

    def finish(self):
        self._command('finish')
        self.keyboard.clear()

    def reset_player(self):
        self._command('reset_player')
        self.keyboard.clear()

    def focus_changed(self, foreground):
        if not foreground:
            self.pause()

    def command(self, key):
        if key == 'escape':
            self.resume() if self.phase == Phase.PAUSED else self.pause()
        elif key == 'r' and self.phase == Phase.DRIVING:
            self.reset_player()
        elif key == 'c' and self.phase == Phase.DRIVING:
            self.camera_distance = 16. if self.camera_distance == 11. else 11.
        elif key == 'enter':
            if self.phase == Phase.PAUSED:
                self.resume()
            elif self.phase == Phase.RESULTS:
                self.start(mode=self.mode, track=self.track_id)
            elif self.phase == Phase.MENU:
                from race import GameMode

                self.start(mode=GameMode.TIME_TRIAL, track='coastal')

    def set_driving_mode(self, mode):
        self._command('driving_mode', mode)
        self.driving_mode = mode
        self.keyboard.input_config = mode.input_config
        self.simulation.input_config = mode.input_config

    def set_vehicle_config(self, config):
        self._command('vehicle_config', config)
        self.base_vehicle_config = config

    def set_abs_enabled(self, enabled):
        self._command('abs', enabled)

    def set_tcs_enabled(self, enabled):
        self._command('tcs', enabled)

    def set_esc_enabled(self, enabled):
        self._command('esc', enabled)

    def render_segments(self):
        return self.output.segments

    def render_origin(self):
        return self.current.origin_y

    def camera_position(self, start, end, origin_y):
        self.camera.send((tuple(start), tuple(end), origin_y))
        if not self.camera.poll(30.):
            raise TimeoutError('独立会话未返回相机扫掠')
        ok, result, trace = self.camera.recv()
        if not ok:
            result.add_note(trace)
            raise result
        return Vec3(*result)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            try:
                if self.process.is_alive():
                    # 不领取失败的未完成请求；关闭消息顺序排在它后面，由持有者收尾。
                    try:
                        self.camera.send(None)
                        self.connection.send(('close', ()))
                    except (BrokenPipeError,ConnectionResetError):
                        # 子进程已报告启动/运行失败并关闭管道，仍须等待它退出。
                        pass
                    self.process.join(10.)
            finally:
                if self.process.is_alive():
                    self.process.terminate()
                    self.process.join(5.)
                    raise RuntimeError('独立会话关闭超时')
        finally:
            self.keyboard.clear()
            self.camera.close()
            self.connection.close()
            self.process.close()
