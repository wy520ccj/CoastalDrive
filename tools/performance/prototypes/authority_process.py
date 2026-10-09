"""隔离原型：先销毁绘制进程的世界，再由一个独立进程持有原Session/唯一Bullet世界。"""
import argparse
import hashlib
import json
import os
import pickle
import sys
import time
import traceback
from dataclasses import replace
from functools import partial
from multiprocessing import get_context
from pathlib import Path
from types import SimpleNamespace


def serve(connection, options, output):
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root/'src'))
    sys.path.insert(0, str(root/'tools/performance'))
    sys.path.insert(0, str(root/'tools'))
    from benchmark_runtime import audited_worker
    from endurance_check import EnduranceDriver
    from panda3d.core import TransformState

    import physics_workers
    from session import Session
    from session_clock import SessionClock
    from simulation import Simulation

    original_init = Simulation.__init__
    original_reset = Simulation.reset
    def fixed_count(self, *args, **kwargs):
        kwargs['traffic_count'] = options['traffic_count']
        original_init(self, *args, **kwargs)
    Simulation.__init__ = fixed_count
    def fixed_reset(self, *args, **kwargs):
        self.traffic_count = options['traffic_count']
        original_reset(self, *args, **kwargs)
    Simulation.reset = fixed_reset
    physics_workers._worker_loop = partial(audited_worker, output)
    session = None
    collections = []
    hashes, published = [], []
    original_publish = SessionClock.publish
    def publish(clock):
        original_publish(clock)
        current = clock.current
        published.append((time.perf_counter(), current.tick, current.origin_y,
                          [tuple(car.position) for car in (current.player, *current.traffic)]))
        if os.environ.get('PHYS_STRUCT_HASH') and (not hashes or hashes[-1][0] != current.tick):
            state = replace(current, contact_epoch=0, impacts=tuple(replace(e, epoch=0) for e in current.impacts))
            hashes.append((state.tick, hashlib.sha256(pickle.dumps(state, protocol=5)).hexdigest()))
    SessionClock.publish = publish
    try:
        session = Session(options['seed'], track='endless', road_shape='hills',
                          driving_mode=options['mode'], vehicle_config=options['config'],
                          physics_workers=9, independent_clock=True)
        session.start(countdown=False)
        session.set_controller(EnduranceDriver(session.simulation, options['seed']+701))

        def packet(state, final=False):
            return (state, session.current, session.previous, session.phase, session.countdown_ticks,
                    session.stepper.dropped_time, session.race.snapshot, session.highway.snapshot,
                    session.notice, session.simulation.collision_count, session.render_segments(),
                    session.render_origin(), session.simulation.origin_y,
                    session.simulation._physics_workers.diagnostics() if final else None)

        connection.send(('ready', packet(session.current)))
        frames = 0
        while True:
            message = connection.recv()
            if message[0] == 'close':
                break
            if message[0] == 'frame':
                state = session.frame(0.)
                frames += 1
                if frames % 60 == 0:
                    TransformState.garbageCollect()
                    collections.append((session.current.tick, TransformState.getNumStates()))
                result = packet(state)
            elif message[0] == 'camera':
                from panda3d.core import Vec3
                result = tuple(session.camera_position(Vec3(*message[1]), Vec3(*message[2]), message[3]))
            elif message[0] == 'stop':
                session.stop_clock()
                result = packet(session.current, final=True)
            elif message[0] == 'progress':
                if session._clock is None:
                    result = session.current.tick, session.stepper.dropped_time, time.perf_counter()
                else:
                    with session._clock.output_lock:
                        result = session._clock.current.tick, session.stepper.dropped_time, time.perf_counter()
            else:
                raise ValueError('权威进程原型收到未知请求')
            connection.send(('ok', result))
    except Exception as error:  # noqa: BLE001 - 外部进程必须完整回传原异常。
        connection.send(('error', str(error), traceback.format_exc()))
    finally:
        if session is not None:
            session.close()
        connection.close()
        (Path(output)/'authority-memory.json').write_text(json.dumps(collections), encoding='utf-8')
        (Path(output)/'authority-published.json').write_text(json.dumps(published), encoding='utf-8')
        if hashes:
            (Path(output)/'clock-hashes.json').write_text(json.dumps(hashes), encoding='utf-8')


def main():
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--traffic-count', type=int, required=True)
    args, _ = parser.parse_known_args()
    sys.path.insert(0, str(root/'src'))
    sys.path.insert(0, str(root/'tools/performance'))
    import benchmark_runtime
    from panda3d.core import Vec3

    from application import CoastalDrive
    original_init = CoastalDrive.__init__
    original_apply = CoastalDrive.apply_scene
    rendered = []
    def apply(app, state, dt):
        start = time.perf_counter()
        original_apply(app, state, dt)
        rendered.append((start, state.tick, state.origin_y,
                         [tuple(car.position) for car in (state.player, *state.traffic)],
                         tuple(app.camera.getPos()), dt, (time.perf_counter()-start)*1000))
    CoastalDrive.apply_scene = apply

    def install(app, *arguments, **keywords):
        original_init(app, *arguments, **keywords)
        session = app.session
        curve = session.simulation.stream.curve
        options = {'seed': session.seed, 'mode': session.driving_mode, 'config': session.base_vehicle_config,
                   'traffic_count': args.traffic_count}
        session.close()
        session.simulation.stream = SimpleNamespace(curve=curve, segments=())
        session.simulation._physics_workers = SimpleNamespace(diagnostics=lambda: stats['workers'])
        context = get_context('spawn')
        parent, child = context.Pipe()
        process = context.Process(target=serve, args=(child, options, str(args.output.resolve())))
        process.start()
        child.close()
        stats = {'workers': None, 'segments': (), 'origin': 0.}

        def request(message):
            parent.send(message)
            response = parent.recv()
            if response[0] == 'error':
                raise RuntimeError(response[1]+'\n'+response[2])
            return response[1]

        def update(packet):
            (state, session.current, session.previous, session.phase, session.countdown_ticks,
             session.stepper.dropped_time, session.race.snapshot, session.highway.snapshot,
             session.notice, session.simulation.collision_count, stats['segments'], stats['origin'],
             session.simulation.origin_y, workers) = packet
            if workers is not None:
                stats['workers'] = workers
            return state

        initial = parent.recv()
        if initial[0] != 'ready':
            raise RuntimeError(str(initial))
        update(initial[1])
        session.frame = lambda elapsed: update(request(('frame',)))
        session.camera_position = lambda start, end, origin: Vec3(*request(('camera', tuple(start), tuple(end), origin)))
        session.render_segments = lambda: stats['segments']
        session.render_origin = lambda: stats['origin']
        session.stop_clock = lambda: update(request(('stop',)))
        benchmark_runtime.physics_progress = lambda owner: request(('progress',))

        def close():
            parent.send(('close',))
            process.join(10.)
            if process.is_alive():
                raise RuntimeError('权威进程原型未完成关闭')
            parent.close()
            process.close()
        session.close = close

    CoastalDrive.__init__ = install
    try:
        return benchmark_runtime.main()
    finally:
        (args.output/'authority-rendered.json').write_text(json.dumps(rendered), encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
