"""逐字段检查完整快照，只对绘制轮姿使用三轴旋转等价比较。"""
import argparse
import json
import lzma
from pathlib import Path

from panda3d.core import Quat, Vec3

parser = argparse.ArgumentParser()
parser.add_argument('old', type=Path)
parser.add_argument('new', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
with lzma.open(args.old, 'rt', encoding='utf-8') as stream:
    old = json.load(stream)
with lzma.open(args.new, 'rt', encoding='utf-8') as stream:
    new = json.load(stream)
fields = 0
rotations = 0
max_axis_error = 0.


def compare(a, b, path=()):
    global fields, rotations, max_axis_error
    assert type(a) is type(b), (path, type(a), type(b))
    if len(path) >= 3 and path[-3] == 'wheels' and path[-1] == 'orientation':
        assert len(a) == len(b) == 4
        rotations += 1
        qa, qb = Quat(*a), Quat(*b)
        for axis in (Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)):
            error = (qa.xform(axis) - qb.xform(axis)).length()
            max_axis_error = max(max_axis_error, error)
            assert error < 2e-6, (path, error)
    elif isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for key in a:
            compare(a[key], b[key], (*path, key))
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for index, (left, right) in enumerate(zip(a, b)):
            compare(left, right, (*path, index))
    else:
        fields += 1
        assert a.hex() == b.hex() if isinstance(a, float) else a == b, (path, a, b)


compare(old, new)
report = {'ticks': len(old), 'exact_fields': fields, 'wheel_rotations': rotations,
          'max_axis_error': max_axis_error, 'passed': True,
          'scope': 'all snapshot fields and float bits exact except visual wheel quaternions; three unit axes equivalent'}
args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report))
