"""真实请求时间线：原方程照常运行，不将远程未完成时间当作IPC。"""
import argparse
import ctypes
import json
import os
import sys
import time
from functools import partial
from pathlib import Path

_kernel = ctypes.WinDLL('kernel32', use_last_error=True)
_kernel.GetCurrentThread.restype = ctypes.c_void_p
_kernel.QueryThreadCycleTime.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulonglong))


def clock():
    cycles = ctypes.c_ulonglong()
    if not _kernel.QueryThreadCycleTime(_kernel.GetCurrentThread(), ctypes.byref(cycles)):
        raise ctypes.WinError(ctypes.get_last_error())
    return time.perf_counter(), cycles.value


class ConnectionTrace:
    def __init__(self, connection, events):
        self.connection, self.events = connection, events

    def send_bytes(self, payload):
        start, cpu = clock()
        self.connection.send_bytes(payload)
        end, final_cpu = clock()
        identifier = int.from_bytes(payload[1:9], 'little') if payload[0] in (1, 2, 3) else None
        self.events.append(('send', identifier, start, end, final_cpu-cpu, len(payload)))

    def recv_bytes(self):
        start, cpu = clock()
        payload = self.connection.recv_bytes()
        end, final_cpu = clock()
        identifier = int.from_bytes(payload[1:9], 'little') if payload[0] in (1, 2, 3) else None
        self.events.append(('recv', identifier, start, end, final_cpu-cpu, len(payload)))
        return payload

    def poll(self, timeout=0.):
        return self.connection.poll(timeout)

    def close(self):
        return self.connection.close()


def worker(output, connection):
    import cProfile

    import physics_workers
    events = []
    job = None
    original_receive = physics_workers._receive_message
    original_solve = physics_workers._solve_vehicle
    profiler = cProfile.Profile() if os.environ.get('PHYS_STRUCT_PROFILE') else None

    def receive(connection):
        nonlocal job
        message = original_receive(connection)
        if message is not None and message[0] == 'numeric':
            job = message[1]
        return message

    def solve(*args, **kwargs):
        start, cpu = clock()
        active = profiler is not None and 6240 <= job < 9360
        if active:
            profiler.enable()
        try:
            return original_solve(*args, **kwargs)
        finally:
            if active:
                profiler.disable()
            end, final_cpu = clock()
            events.append(('solve', job, start, end, final_cpu-cpu, 0))

    physics_workers._receive_message = receive
    physics_workers._solve_vehicle = solve
    try:
        physics_workers._worker_loop(ConnectionTrace(connection, events))
    finally:
        (Path(output)/f'worker-timeline-{os.getpid()}.json').write_text(json.dumps(events), encoding='utf-8')
        if profiler is not None:
            profiler.dump_stats(str(Path(output)/f'worker-profile-{os.getpid()}.prof'))


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--output', type=Path, required=True)
    args, _ = parser.parse_known_args()
    sys.path.insert(0, str(root/'src'))
    sys.path.insert(0, str(root/'tools/performance'))
    import benchmark_physics

    import physics_workers
    import world_step
    from physics_workers import PhysicsWorkers
    from simulation import Simulation
    from vehicle import Vehicle

    events = []
    physics_workers._worker_loop = partial(worker, str(args.output.resolve()))
    original_start = PhysicsWorkers._start_one

    def start(pool):
        original_start(pool)
        process, connection = pool.processes[-1]
        pool.processes[-1] = process, ConnectionTrace(connection, events)

    PhysicsWorkers._start_one = start

    def timed(owner, name, label):
        original = getattr(owner, name)
        def call(*args, **kwargs):
            begin, cpu = clock()
            try:
                return original(*args, **kwargs)
            finally:
                end, final_cpu = clock()
                events.append((label, None, begin, end, final_cpu-cpu, 0))
        setattr(owner, name, call)

    for owner, name, label in ((Simulation, 'step', 'full-step'),
                              (Simulation, 'snapshot', 'snapshot'),
                              (Vehicle, 'prepare_command', 'control'),
                              (Vehicle, 'after_step', 'observation'),
                              (PhysicsWorkers, 'submit', 'submit-including-backpressure'),
                              (physics_workers, 'input_bytes', 'input-encoding'),
                              (physics_workers, 'from_bytes', 'output-decoding'),
                              (world_step, 'static_support_shapes', 'static-world-read')):
        timed(owner, name, label)
    original_stages = Vehicle.physics_stages
    def stages(car, *args, **kwargs):
        iterator = original_stages(car, *args, **kwargs)
        value, label = None, 'prepare-read'
        while True:
            begin, cpu = clock()
            try:
                request = iterator.send(value)
            except StopIteration as result:
                return result.value
            finally:
                end, final_cpu = clock()
                events.append((label, None, begin, end, final_cpu-cpu, 0))
            value = yield request
            label = 'ordered-commit'
    Vehicle.physics_stages = stages
    original_world = world_step.advance_world

    class WorldTrace:
        def __init__(self, world):
            self.world = world

        def getRigidBodies(self):
            return self.world.getRigidBodies()

        def sweepTestClosest(self, *args):
            return self.world.sweepTestClosest(*args)

        def rayTestClosest(self, *args):
            return self.world.rayTestClosest(*args)

        def doPhysics(self, *args):
            begin, cpu = clock()
            try:
                return self.world.doPhysics(*args)
            finally:
                end, final_cpu = clock()
                events.append(('bullet', None, begin, end, final_cpu-cpu, 0))

    def advance(world, *args, **kwargs):
        return original_world(WorldTrace(world), *args, **kwargs)

    sys.modules['simulation'].advance_world = advance
    try:
        return benchmark_physics.main()
    finally:
        (args.output/'parent-timeline.json').write_text(json.dumps(events), encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
