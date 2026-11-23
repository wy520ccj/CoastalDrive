"""实际草木原/新种植结果和检查步骤对照；离场耗时不代表驾驶帧率。"""

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/environment')]

from check_segment_batches import AssetLoader, geometry
from local_coastal_landscape import rock_steps
from local_kcd_drive import LocalVegetation, floor_point
from panda3d.core import NodePath

from career_courses import CareerCourse
from scene import Scene


def check(output, baseline):
    output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('vegetation_site_baseline', baseline)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    holder = NodePath('site-budget-check')
    profile = LocalVegetation(ROOT/'logs/local-kcd-drive/assets', ROOT/'logs/local-kcd-original-environment')
    profile.install()
    rows = []
    try:
        scene = Scene.__new__(Scene)
        trees = [scene.load_model('nature/tree_pineTall'+variant+'.glb') for variant in ('A', 'B')]
        kit = profile.load_kit(AssetLoader(), holder.attachNewNode('templates'), trees)
        curve = CareerCourse('ridge-club')
        for index in (0, 8):
            expected = None
            for label, function in (('original', original.LocalVegetation.vegetation),
                                    ('budgeted', LocalVegetation.vegetation)):
                root = holder.attachNewNode('segment')
                parent = lambda _s, root=root: root
                list(rock_steps(root, index, 0, curve, kit, parent, floor_point))
                work = function(profile, root, index, 0, curve, kit, parent)
                controls, timings = [], []
                while True:
                    started = time.perf_counter()
                    try:
                        phase = next(work)
                    except StopIteration:
                        timings.append(('finished', (time.perf_counter()-started)*1000))
                        break
                    timings.append((phase, (time.perf_counter()-started)*1000))
                    if phase == 'local-kcd-grass-batch':
                        values = work.gi_frame.f_locals
                        controls.append((values['count'], tuple(
                            (key, tuple(tuple(point) for point in data))
                            for key, data in values['controls'].items())))
                        # PTA对象地址不同；独立逐值比较后再比较其余完整材质状态。
                        for key in values['controls']:
                            values['batch'].clearShaderInput('grass_floor'+key)
                result = geometry(root), controls, tuple(
                    (node.getName(), node.getMat(root), node.getState(root), node.node().getDrawControlMask(),
                     node.node().getDrawShowMask()) for node in root.findAllMatches('**'))
                if expected is None:
                    expected = result
                assert result == expected, (index, label)
                row = {'segment': index, 'mode': label, 'geometry_states_controls_equal': True,
                       'geoms': len(result[0]), 'grass_batches': len(controls),
                       'max_step_ms': max(value for _phase, value in timings),
                       'total_ms': sum(value for _phase, value in timings), 'steps': timings}
                rows.append(row)
                print({key: value for key, value in row.items() if key != 'steps'}, flush=True)
                root.removeNode()
        report = {'passed': True, 'baseline': str(baseline), 'runs': rows,
                  'scope': '实际原岩岸/草木，两段原/新完整几何、种植变换、状态和全部草控制点精确一致；离场步骤计时，不是正常驾驶/GPU/人工验收。'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    finally:
        profile.restore()
        holder.removeNode()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    arguments = parser.parse_args()
    check(arguments.output.resolve(), arguments.baseline.resolve())
