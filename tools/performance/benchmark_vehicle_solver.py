"""独立真实车辆子步求解对照；排除IPC，不代替完整物理步/前台验收。"""

import argparse
import cProfile
import hashlib
import importlib
import json
import pickle
import sys
import time
from dataclasses import replace
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'src')
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--warmup', type=int, default=8, help='对全部真实输入作预热的轮数')
    parser.add_argument('--repeats', type=int, default=40, help='完整输入集的计时轮数')
    parser.add_argument('--profile', action='store_true', help='单独定位；profile时间不作为吞吐')
    args = parser.parse_args()
    if args.warmup < 0 or args.repeats < 1:
        parser.error('预热轮数不能为负，计时轮数必须为正')
    args.output.mkdir(parents=True, exist_ok=False)
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    sys.path.insert(0, str(ROOT/'tools/performance'))
    import benchmark_physics

    import physics_wire
    import physics_workers

    modules = {}
    for name in ('physics_workers', 'physics_wire', 'vehicle_tire_step', 'tire_drivetrain',
                 'vehicle_tires', 'suspension_kinematics', 'mechanical_kernels', 'wheel_contact_kernels'):
        filename = Path(importlib.import_module(name).__file__).resolve()
        if filename.parent != source:
            raise RuntimeError(f'完整求解对照加载了错误源码：{name}: {filename}')
        modules[name] = {'path': str(filename), 'sha256': hashlib.sha256(filename.read_bytes()).hexdigest()}
    fixture = json.loads((args.fixture/'fixture.json').read_text(encoding='utf-8'))
    if fixture['physical_substeps'] != 2 or tuple(map(tuple, fixture['schema_records'])) != physics_wire._names:
        raise ValueError('真实输入的子步数或数值记录结构与当前源码不一致')
    hardware = pickle.loads((args.fixture/'hardware.pickle').read_bytes())
    geometry = (args.fixture/'geometry.pickle').read_bytes()
    arena = SharedMemory(create=True, size=len(geometry))
    arena.buf[:] = geometry
    reference = physics_workers.GeometryRef(arena.name, len(geometry), 1)
    entries = []
    for identifier in sorted(map(int, fixture['entries'])):
        payload = (args.fixture/f'input-{identifier}.bin').read_bytes()
        request = replace(physics_wire.from_bytes(payload), config=hardware)
        expected = (args.fixture/f'result-{identifier}.bin').read_bytes()
        entries.append((identifier, request, expected))
    durations, cpu, mismatches = [], [], []
    try:
        physics_workers._load_geometry(reference)
        for _ in range(args.warmup):
            for _, request, _ in entries:
                if physics_workers._solve_vehicle(request, reference) is None:
                    raise ValueError('当前输入需要唯一世界回查，不能独立衡量完整求解')
        # 序列化/核对位于计时区间之外；每次都实际重新解完整车辆，绝不重放旧结果。
        for repeat in range(args.repeats):
            for identifier, request, expected in entries:
                cpu_start, started = time.process_time(), time.perf_counter()
                result = physics_workers._solve_vehicle(request, reference)
                elapsed = time.perf_counter()-started
                cpu_elapsed = time.process_time()-cpu_start
                if result is None:
                    raise ValueError('真实有限接触进入唯一世界回查')
                durations.append(elapsed)
                cpu.append(cpu_elapsed)
                actual = physics_wire.result_bytes(result)
                if actual != expected:
                    mismatches.append({'repeat': repeat, 'identifier': identifier,
                                       'actual_sha256': hashlib.sha256(actual).hexdigest(),
                                       'expected_sha256': hashlib.sha256(expected).hexdigest()})
        if args.profile:
            profiler = cProfile.Profile()
            profiler.enable()
            for _, request, _ in entries:
                physics_workers._solve_vehicle(request, reference)
            profiler.disable()
            profiler.dump_stats(str(args.output/'complete-solver.pstats'))
        report = {
            'kind': '完整真实数值子步，独立于IPC；不能证明完整物理步或前台120Hz',
            'source': str(source), 'modules': modules, 'inputs': len(entries),
            'warmup_rounds': args.warmup, 'measured_rounds': args.repeats,
            'complete_vehicle_substep': benchmark_physics.distribution(durations),
            'quantized_process_cpu_seconds': sum(cpu),
            'all_results_byte_exact': not mismatches, 'mismatches': mismatches,
            'physics_world_created': False, 'original_results_used_only_for_validation': True,
            'timing_excludes_wire_encoding_and_validation': True,
            'profile_is_separate_from_timing': True,
            'checked_modules_unchanged': all(
                hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() == record['sha256']
                for record in modules.values()),
        }
        report['passed'] = not mismatches and report['checked_modules_unchanged']
        (args.output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['passed'] else 1
    finally:
        physics_workers._worker_geometry = None
        physics_workers._worker_candidates.clear()
        if physics_workers._worker_memory is not None:
            physics_workers._worker_memory.close()
            physics_workers._worker_memory = None
        arena.close()
        arena.unlink()


if __name__ == '__main__':
    raise SystemExit(main())
