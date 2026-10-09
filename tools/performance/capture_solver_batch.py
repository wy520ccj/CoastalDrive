"""保存真实两个子步的完整数值输入/结果及当前几何，供连续原生求解器对照。"""

import argparse
import json
import pickle
import sys
from dataclasses import asdict
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--traffic', type=int, default=12)
    parser.add_argument('--warmup', type=int, default=240)
    args, _ = parser.parse_known_args()
    sys.path.insert(0, str(root/'src'))
    sys.path.insert(0, str(root/'tools/performance'))
    import benchmark_physics

    import physics_wire
    from physics_wire import input_bytes, result_bytes
    from physics_workers import PhysicsWorkers

    first = args.warmup * 2 * (args.traffic+1)
    last = first + 2 * (args.traffic+1)
    records = {}
    original_submit, original_receive = PhysicsWorkers.submit, PhysicsWorkers._receive

    def submit(pool, request, shapes, material):
        identifier = pool.identifier
        handle = original_submit(pool, request, shapes, material)
        if first <= identifier < last:
            records[identifier] = {'dt': request.dt, 'tick': request.tick}
            (args.output/f'input-{identifier}.bin').write_bytes(input_bytes(request))
            if identifier == first:
                (args.output/'hardware.json').write_text(json.dumps(asdict(request.config), indent=2), encoding='utf-8')
                (args.output/'hardware.pickle').write_bytes(pickle.dumps(request.config, protocol=5))
                (args.output/'geometry.pickle').write_bytes(bytes(pool.memory.buf[:pool.reference.size]))
        return handle

    def receive(pool, index, identifier):
        result = original_receive(pool, index, identifier)
        if identifier in records:
            if result is None:
                raise ValueError('捕获工况含唯一世界回查，不能当作独立原生输入')
            (args.output/f'result-{identifier}.bin').write_bytes(result_bytes(result))
        return result

    PhysicsWorkers.submit, PhysicsWorkers._receive = submit, receive
    try:
        return benchmark_physics.main()
    finally:
        (args.output/'fixture.json').write_text(json.dumps({
            'kind': '真实方程验证输入；本次文件记录含I/O，不是性能基准',
            'entries': records, 'schema_records': physics_wire._names,
            'physical_substeps': 2, 'numerical_results_replayed_in_physics': False,
        }, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
