"""生成独立源码副本，原项目和原数值内核保持不动。"""

import argparse
import shutil
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='必须是尚不存在的副本目录')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('输出目录已存在；请使用新目录，不覆盖已有实验')
    destination = args.output/'src'
    shutil.copytree(root/'src', destination, ignore=shutil.ignore_patterns('__pycache__'))
    path = destination/'world_step.py'
    source = path.read_text(encoding='utf-8')
    old_submit = 'pending.append(workers.submit(inputs, static_shapes, material))'
    old_results = 'workers.results(requests, pending, query_lock)'
    if source.count(old_submit) != 1 or source.count(old_results) != 1:
        raise ValueError('当前世界子步接口已变化，原型需要重新核对')
    source = source.replace(old_submit, 'pending.append(None)')
    source = source.replace(old_results, 'workers.batch(requests, static_shapes, material, query_lock)')
    path.write_text(source, encoding='utf-8')
    path = destination/'physics_workers.py'
    extension = Path(__file__).with_name('batch_workers.py.in').read_text(encoding='utf-8')
    path.write_text(path.read_text(encoding='utf-8')+'\n\n'+extension, encoding='utf-8')
    print(destination.resolve())


if __name__ == '__main__':
    main()
