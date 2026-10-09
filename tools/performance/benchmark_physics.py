"""完整120Hz物理吞吐与分段诊断；固定输入，预热和正式样本分开。"""

import argparse
import cProfile
import ctypes
import hashlib
import json
import lzma
import os
import pickle
import platform
import pstats
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from functools import partial, wraps
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def profile_worker(output, skip, native_profile, connection):
    """仅诊断子进程的实际数值执行，去掉管道等待和预热；不用profile耗时作吞吐。"""
    import mechanical_kernels

    import physics_workers
    import tire_drivetrain

    original_solve = physics_workers._solve_vehicle
    original_advance = tire_drivetrain.advance_drivetrain
    profiler = cProfile.Profile()
    count = 0
    measuring = False
    sweeps = Counter()
    durations = []

    def advance(*args, **kwargs):
        result = original_advance(*args, **kwargs)
        if measuring:
            sweeps[result.sweeps] += 1
        return result

    def solve(*args):
        nonlocal count, measuring
        measuring = count >= skip
        if native_profile and count == skip:
            mechanical_kernels.solver_profile(True)
        count += 1
        start = time.perf_counter()
        if measuring:
            profiler.enable()
        try:
            return original_solve(*args)
        finally:
            if measuring:
                profiler.disable()
                durations.append(time.perf_counter()-start)
            measuring = False

    physics_workers._solve_vehicle = solve
    tire_drivetrain.advance_drivetrain = advance
    try:
        physics_workers._worker_loop(connection)
    finally:
        profiler.dump_stats(str(Path(output)/f'worker-{os.getpid()}.pstats'))
        (Path(output)/f'worker-{os.getpid()}.json').write_text(
            json.dumps({'requests': count, 'skipped': skip, 'sweeps': dict(sweeps),
                        'native_iterations':mechanical_kernels.solver_profile_snapshot() if native_profile else None,
                        'profiled_solve': distribution(durations)}), encoding='utf-8')


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {}

    def percentile(fraction):
        position = (len(ordered)-1)*fraction
        low = int(position)
        high = min(low+1, len(ordered)-1)
        return ordered[low]+(ordered[high]-ordered[low])*(position-low)

    return {'count': len(values), 'mean_ms': sum(values)/len(values)*1000,
            'p95_ms': percentile(.95)*1000, 'p99_ms': percentile(.99)*1000,
            'max_ms': ordered[-1]*1000, 'total_seconds': sum(values)}


class PhaseTimers:
    """只量函数实际执行；生成器等待交回结果的时间不算读取或提交。"""

    def __init__(self):
        self.enabled = False
        self.samples = defaultdict(list)
        self.originals = []

    def wrap(self, owner, attribute, name):
        original = getattr(owner, attribute)

        @wraps(original)
        def call(*args, **kwargs):
            if not self.enabled:
                return original(*args, **kwargs)
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                self.samples[name].append(time.perf_counter()-start)

        self.originals.append((owner, attribute, original))
        setattr(owner, attribute, call)

    def stages(self, owner, attribute, read_name, commit_name):
        original = getattr(owner, attribute)

        @wraps(original)
        def call(*args, **kwargs):
            stages = original(*args, **kwargs)
            value = None
            name = read_name
            while True:
                start = time.perf_counter()
                try:
                    request = stages.send(value)
                except StopIteration as finished:
                    return finished.value
                finally:
                    if self.enabled:
                        self.samples[name].append(time.perf_counter()-start)
                value = yield request
                name = commit_name

        self.originals.append((owner, attribute, original))
        setattr(owner, attribute, call)

    def restore(self):
        for owner, attribute, original in reversed(self.originals):
            setattr(owner, attribute, original)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT/'src')
    parser.add_argument('--workers', type=int, default=9)
    parser.add_argument('--traffic', type=int, default=8)
    parser.add_argument('--mode', choices=('game', 'simulation'), default='game')
    parser.add_argument('--track', choices=('test', 'coastal', 'endless'), default='coastal')
    parser.add_argument('--shape', choices=('straight', 'curves', 'hills'), default='straight')
    parser.add_argument('--driver', choices=('sequence','endurance'), default='sequence')
    parser.add_argument('--seed', type=int, default=17)
    parser.add_argument('--warmup', type=int, default=240)
    parser.add_argument('--steps', type=int, default=480)
    parser.add_argument('--trace', action='store_true')
    parser.add_argument('--profile', action='store_true', help='当前主进程调用定位，不能作吞吐结论')
    parser.add_argument('--capture', action='store_true', help='记录每拍完整快照，写文件在计时之外')
    parser.add_argument('--capture-hashes', action='store_true', help='每拍完整物理快照的原浮点载荷SHA，序列化在计时之外')
    parser.add_argument('--cpu-mask', type=lambda value: int(value, 0), help='仅本次基准的Windows进程CPU掩码，子进程继承')
    parser.add_argument('--worker-profile', action='store_true', help='定位9车9进程的实际数值执行，不作吞吐证据')
    parser.add_argument('--native-profile', action='store_true', help='仅配合隔离计数内核，记录内部求根迭代')
    args = parser.parse_args()
    if min(args.workers, args.traffic, args.warmup) < 0 or args.steps <= 0:
        parser.error('进程/交通/预热非负，采样步数为正')
    if args.profile and args.worker_profile:
        parser.error('主进程和子进程profile分开执行，避免同时污染诊断')
    if args.worker_profile and (args.workers != 9 or args.traffic != 8):
        parser.error('子进程profile固定9车9进程，以每个进程2次/拍准确排除预热')
    if args.native_profile and not args.worker_profile:
        parser.error('原生计数须同时启用--worker-profile并指定隔离内核源码目录')
    if args.driver == 'endurance' and args.track != 'endless':
        parser.error('已有耐久控制器使用无限高速赛道')
    args.output.mkdir(parents=True, exist_ok=False)
    if args.cpu_mask is not None:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        kernel.SetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
        if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(), args.cpu_mask):
            raise ctypes.WinError(ctypes.get_last_error())
    sys.path.insert(0, str(args.source.resolve()))
    import paths

    paths.resource_root = lambda: ROOT
    import physics_workers
    import world_step
    from driving_modes import DrivingMode
    from physics_workers import PhysicsWorkers
    from powertrain import Powertrain
    from simulation import Control, Simulation
    from vehicle import Vehicle
    from vehicle_designs import GR86_DESIGN
    from vehicle_suspension import Suspension
    from vehicle_tire_step import TireAdvanceInput, TireAdvanceResult

    if args.worker_profile:
        physics_workers._worker_loop = partial(profile_worker, str(args.output.resolve()), args.warmup*2, args.native_profile)

    timers = PhaseTimers()
    sweeps = Counter()
    worker_times = []
    original_receive = PhysicsWorkers._receive
    original_accept = Powertrain.accept_step

    def receive(pool, index, identifier):
        result = original_receive(pool, index, identifier)
        if timers.enabled:
            worker_times.append((index, identifier, *pool.samples[-1]))
        return result

    PhysicsWorkers._receive = receive

    def accept(powertrain, result, dt):
        if timers.enabled:
            sweeps[result.sweeps] += 1
        return original_accept(powertrain, result, dt)

    Powertrain.accept_step = accept
    if args.trace:
        for owner, attribute, name in (
            (world_step, 'static_support_shapes', 'static_geometry'),
            (Vehicle, 'prepare_control', 'control'),
            (Vehicle, 'prepare_command', 'command'),
            (Suspension, 'prepare', 'suspension_prepare'),
            (PhysicsWorkers, 'submit', 'freeze_encode_send_including_backpressure'),
            (PhysicsWorkers, '_receive', 'wait_receive_decode'),
            (physics_workers, '_receive_message', 'receive_message_including_wait'),
            (physics_workers, 'from_bytes', 'decode'),
            (physics_workers, 'input_bytes', 'encode'),
            (TireAdvanceInput, 'solve', 'serial_complete_solve'),
            (TireAdvanceResult, 'commit', 'impulse_state_commit'),
            (Vehicle, 'after_step', 'after_step'),
            (Simulation, '_read_impact_contacts', 'contact_observation'),
        ):
            timers.wrap(owner, attribute, name)
        timers.stages(Vehicle, 'physics_stages', 'read_prepare', 'resume_commit')
        timers.stages(PhysicsWorkers, 'results', 'collect_results', 'collect_results')

    class TimedWorld:
        def __init__(self, world):
            self.world = world

        def __getattr__(self, name):
            return getattr(self.world, name)

        def doPhysics(self, *values):
            start = time.perf_counter()
            try:
                return self.world.doPhysics(*values)
            finally:
                if timers.enabled:
                    timers.samples['bullet'].append(time.perf_counter()-start)

    mode = DrivingMode(args.mode)
    config = mode.configured_vehicle(base_config=GR86_DESIGN)
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in args.source.iterdir() if path.suffix in ('.py', '.c', '.cpp', '.h', '.pyd')}
    sim = Simulation(seed=args.seed, track=args.track, road_shape=args.shape,
                     traffic_count=args.traffic, config=config, input_config=mode.input_config,
                     traffic_input_config=mode.input_config, physics_workers=args.workers)
    driver = None
    if args.driver == 'endurance':
        sys.path.insert(0, str(ROOT/'tools'))
        from endurance_check import EnduranceDriver

        driver = EnduranceDriver(sim, args.seed+701)
        sys.path.insert(0, str(args.source.resolve()))
    state = sim.snapshot()
    if args.trace:
        sim._world = TimedWorld(sim._world)
    profiler = cProfile.Profile() if args.profile else None
    snapshots, snapshot_hashes, elapsed, cpu_samples, geometry_updates, slow_steps = [], [], [], [], [], []
    report = {'arguments': {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'python': sys.version, 'machine': platform.platform(), 'source_hashes': hashes,
              'vehicle_design':'gr86-2022-premium-6mt',
              'vehicle_config_sha256':hashlib.sha256(json.dumps(asdict(config),sort_keys=True).encode()).hexdigest(),
              'physical_substeps':world_step.physical_substeps(config),
              'budget_ms': 1000/120, 'passed': False}
    try:
        start = time.perf_counter()
        sim.prepare_physics()
        report['preparation_seconds'] = time.perf_counter()-start

        def control(tick):
            # 统一确定性驾驶序列：加速、小幅转向、制动，随后重复。
            phase = tick % 1200
            return Control(throttle=.5 if phase < 840 else 0.,
                           steering=.06 if 480 <= phase < 720 else 0.,
                           brake=.6 if 840 <= phase < 1080 else 0.)

        start = time.perf_counter()
        for tick in range(args.warmup):
            sim.step(driver.sample(state,1/120) if driver else control(tick))
            state = sim.snapshot()
        report['warmup_seconds'] = time.perf_counter()-start
        if sim._physics_workers:
            sim._physics_workers.samples.clear()
        timers.enabled = True
        previous_geometry = sim._physics_workers.version if sim._physics_workers else 0
        if profiler:
            profiler.enable()
        for tick in range(args.warmup, args.warmup+args.steps):
            start_cpu = time.process_time()
            start = time.perf_counter()
            sim.step(driver.sample(state,1/120) if driver else control(tick))
            snapshot_start = time.perf_counter()
            state = sim.snapshot()
            if args.trace:
                timers.samples['snapshot'].append(time.perf_counter()-snapshot_start)
            elapsed.append(time.perf_counter()-start)
            cpu_samples.append(time.process_time()-start_cpu)
            geometry = sim._physics_workers.version if sim._physics_workers else 0
            if geometry != previous_geometry:
                geometry_updates.append({'tick':state.tick,'version':geometry,'ms':elapsed[-1]*1000})
                previous_geometry = geometry
            if elapsed[-1] >= .05:
                slow_steps.append({'tick':state.tick,'geometry_version':geometry,'ms':elapsed[-1]*1000})
            if args.capture_hashes:
                if profiler:
                    profiler.disable()
                normalized = replace(state, contact_epoch=0,
                                     impacts=tuple(replace(event, epoch=0) for event in state.impacts))
                snapshot_hashes.append(hashlib.sha256(pickle.dumps(normalized, protocol=5)).hexdigest())
                if profiler:
                    profiler.enable()
            if args.capture:
                if profiler:
                    profiler.disable()
                record = asdict(state)
                record['contact_epoch'] = 0
                for event in record['impacts']:
                    event['epoch'] = 0
                snapshots.append(record)
                if profiler:
                    profiler.enable()
        report['main_cpu_seconds'] = sum(cpu_samples)
        report['complete_step'] = distribution(elapsed)
        report['simulated_seconds'] = args.steps/120
        report['throughput_hz'] = args.steps/sum(elapsed)
        report['compute_budget_met'] = (sum(elapsed)/len(elapsed) < 1/120
                                       and report['complete_step']['p95_ms'] < 1000/120)
        report['simulated_to_compute_wall'] = args.steps/120/sum(elapsed)
        report['sweeps'] = dict(sorted(sweeps.items()))
        report['final_tick'] = state.tick
        report['player_collisions'] = state.collisions
        report['active_traffic'] = sum(car.active for car in state.traffic)
        report['geometry_updates'] = geometry_updates
        report['steps_over_50ms'] = slow_steps
        report['phases_inclusive_do_not_sum'] = {name: distribution(values) for name, values in timers.samples.items()}
        report['workers'] = sim._physics_workers.diagnostics() if sim._physics_workers else None
        report['worker_solve_all_samples'] = {
            'wall': distribution([row[2] for row in worker_times]),
            'cpu': distribution([row[3] for row in worker_times]),
            'by_process': {index: distribution([row[2] for row in worker_times if row[0] == index])
                           for index in range(args.workers)},
        }
        report['total_cpu_seconds'] = sum(cpu_samples)+sum(row[3] for row in worker_times)
        report['average_cpu_cores'] = report['total_cpu_seconds']/sum(elapsed)
        report['passed'] = True
        report['measurement_complete'] = True
    except Exception as error:
        report['error'] = repr(error)
        report['completed_samples'] = len(elapsed)
        raise
    finally:
        timers.enabled = False
        if profiler:
            profiler.disable()
            profiler.dump_stats(str(args.output/'profile.pstats'))
            stats = pstats.Stats(profiler)
            report['profile_inclusive_do_not_sum'] = [
                {'file': key[0], 'line': key[1], 'name': key[2], 'calls': values[1],
                 'self_seconds': values[2], 'inclusive_seconds': values[3]}
                for key, values in sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)]
        if snapshots:
            with lzma.open(args.output/'snapshots.json.xz', 'wt', encoding='utf-8') as stream:
                json.dump(snapshots, stream, separators=(',', ':'))
        if snapshot_hashes:
            (args.output/'snapshot-hashes.json').write_text(json.dumps(snapshot_hashes), encoding='utf-8')
        timers.restore()
        Powertrain.accept_step = original_accept
        PhysicsWorkers._receive = original_receive
        if args.trace:
            sim._world = sim._world.world
        sim.close()
        report['source_unchanged'] = hashes == {name: hashlib.sha256((args.source/name).read_bytes()).hexdigest() for name in hashes}
        (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('complete_step', 'throughput_hz', 'sweeps', 'source_unchanged')}))


if __name__ == '__main__':
    main()
