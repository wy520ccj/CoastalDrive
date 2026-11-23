"""固定预算关卡与方案保存失败机械输入；捕获不等于独立等价重放。"""

import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools'), str(Path(__file__).parent)]

from challenge_balance_check import run
from coastal_shared_failure import freeze

from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from tire_drivetrain import DrivetrainInput


def replay(source, output):
    import physics_workers
    from physics_workers import StaticSource
    from suspension_contacts import StaticSupportShapes

    output.mkdir(parents=True, exist_ok=False)
    inputs, groups, kwargs = pickle.loads(source.read_bytes())
    physics_workers._worker_geometry = StaticSupportShapes(tuple(
        (StaticSource(index), supported, parts) for index, supported, parts in groups))
    for plane in inputs.parameters['suspension'].kinematics:
        if plane is not None:
            # 捕获未保留原候选盒；空盒不能当三维向量，改走同批完整真实几何查询。
            plane.surface.candidates.clear()
    rows = []
    for repeat in range(3):
        try:
            result = inputs.solve(**kwargs)
            # 支持几何的查询缓存可能含原生句柄，只哈希已发布的物理数值。
            physical = (result.velocity, result.angular, result.engine_omega, result.shaft_omega,
                        result.wheels, result.suspension)
            row = {'repeat': repeat, 'failed': False, 'result_type': type(result).__name__,
                   'sweeps': result.sweeps, 'normal_residual': result.normal_residual,
                   'wheel_residual': max(wheel.residual for wheel in result.wheels),
                   'physical_sha256': hashlib.sha256(pickle.dumps(physical, protocol=5)).hexdigest()}
        except (ArithmeticError, ValueError) as error:
            row = {'repeat': repeat, 'failed': True, 'error_type': type(error).__name__, 'error': str(error)}
        rows.append(row)
    modules = {name: {'path': sys.modules[name].__file__,
                     'sha256': hashlib.sha256(Path(sys.modules[name].__file__).read_bytes()).hexdigest()}
               for name in ('mechanical_kernels', 'wheel_contact_kernels')}
    report = {'rows': rows, 'modules': modules, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'scope': '冻结输入和完整支持几何重放，原候选盒未捕获；未证明与原世界逐值等价。'}
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    original = DrivetrainInput.solve
    calls = 0

    def solve(inputs, **kwargs):
        nonlocal calls
        calls += 1
        try:
            return original(inputs, **kwargs)
        except ArithmeticError:
            frozen, groups = freeze(inputs)
            (output/'failed-input.pkl').write_bytes(pickle.dumps((frozen, groups, kwargs), protocol=5))
            raise

    DrivetrainInput.solve = solve
    try:
        run(output/'drive', ['bend_sprint'], ['handling'], 180., 105., 3.8)
        report = {'reproduced': False, 'calls': calls}
    except ArithmeticError as error:
        report = {'reproduced': True, 'error': str(error), 'calls': calls,
                  'sha256': hashlib.sha256((output/'failed-input.pkl').read_bytes()).hexdigest()}
    finally:
        DrivetrainInput.solve = original
    report.update(source=model_fingerprint(), runtime=runtime_fingerprint(),
                  scope='原120Hz关卡/实际控制与机械失败输入；不是通过结果或等价重放。')
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key not in ('source', 'runtime')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--replay', type=Path)
    args = parser.parse_args()
    replay(args.replay, args.output.resolve()) if args.replay else capture(args.output.resolve())
