"""真实道路/路肩共享边线的原算法对照；离场构建，不作为整机帧率证据。"""

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools/environment'))

from check_segment_batches import AssetLoader, geometry
from local_kcd_drive import LocalVegetation
from panda3d.core import NodePath

from career_courses import CareerCourse
from environment import expressway_route
from scene import Scene


def surface_prefix(build, root, index, kit, curve):
    work = build(root, index, 0, kit, lambda node: None, curve)
    count = 0
    try:
        for phase in work:
            count += phase == 'surface'
            if count == 3:
                break
        else:
            raise AssertionError('未取得道路与两侧路肩')
    finally:
        work.close()


def check(output, baseline):
    output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('route_projection_baseline', baseline)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    holder = NodePath('shared-surface-check')
    templates = holder.attachNewNode('templates')
    scene = Scene.__new__(Scene)
    trees = [scene.load_model('nature/tree_pineTall'+variant+'.glb') for variant in ('A', 'B')]
    profile = LocalVegetation(ROOT/'logs/local-kcd-drive/assets', ROOT/'logs/local-kcd-original-environment')
    profile.install()
    # 本机入口替换了太阳方向，旧源码对照也必须使用同一个实际光源公式。
    original.rail_shadow_coordinate = expressway_route.rail_shadow_coordinate
    rows = []
    try:
        kit = profile.load_kit(AssetLoader(), templates, trees)
        curve = CareerCourse('ridge-club')
        project = curve.project
        for index in (0, 2, 4, 9):
            expected = None
            for label in ('original', 'shared', 'shared', 'original'):
                count = 0

                def measured(position):
                    nonlocal count
                    count += 1
                    return project(position)

                curve.project = measured
                root = holder.attachNewNode('segment')
                started = time.perf_counter()
                surface_prefix(original.segment_steps if label == 'original' else expressway_route.segment_steps,
                               root, index, kit, curve)
                elapsed = (time.perf_counter()-started)*1000
                result = geometry(root)
                if expected is None:
                    expected = result
                if result != expected:
                    differences = [(part, field) for part, (left, right) in enumerate(zip(expected, result, strict=True))
                                   for field, (a, b) in enumerate(zip(left, right, strict=True)) if a != b]
                    print('DIFFERENCES', differences, flush=True)
                    for part, field in differences[:2]:
                        if field == 3:
                            for number, (a, b) in enumerate(zip(expected[part][field], result[part][field], strict=True)):
                                print('BYTES', part, number, len(a), len(b),
                                      [(i, x, y) for i, (x, y) in enumerate(zip(a, b, strict=True)) if x != y][:16], flush=True)
                        else:
                            print('VALUES', part, field, str(expected[part][field])[:500],
                                  str(result[part][field])[:500], flush=True)
                    raise AssertionError((index, label))
                row = {'segment': index, 'mode': label, 'wall_ms': elapsed, 'project_calls': count,
                       'geometry_and_states_equal': True}
                rows.append(row)
                print(row, flush=True)
                root.removeNode()
        (output/'summary.json').write_text(json.dumps({
            'scope': '真实原资源/山脊1m路面/两侧路肩，原/新/新/原；顶点数组/索引/格式/状态精确一致。含冷启动首项，非正常驾驶或GPU性能Gate。',
            'baseline': str(baseline), 'runs': rows}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    finally:
        profile.restore()
        holder.removeNode()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.baseline.resolve())
