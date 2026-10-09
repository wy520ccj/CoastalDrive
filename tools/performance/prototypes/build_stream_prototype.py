"""生成独立流式数值队列原型；生产求解器和世界推进保持原样。"""

import argparse
import shutil
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('输出目录必须尚不存在，避免覆盖已有对照实验')
    destination = args.output/'src'
    shutil.copytree(root/'src', destination, ignore=shutil.ignore_patterns('__pycache__'))
    path = destination/'physics_workers.py'
    extension = Path(__file__).with_name('stream_workers.py.in').read_text(encoding='utf-8')
    path.write_text(path.read_text(encoding='utf-8')+'\n\n'+extension, encoding='utf-8')
    print(destination.resolve())


if __name__ == '__main__':
    main()
