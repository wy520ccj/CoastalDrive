"""原海岸高度查询与静态模型共享对照；不代表正常驾驶帧率。"""

import argparse
import importlib.util
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools/environment')]

from check_segment_batches import geometry

from environment import coastal_slice, foundation, terrain
from scene import Scene


def source(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def check(output, baseline):
    output.mkdir(parents=True, exist_ok=False)
    old_terrain = source(baseline/'terrain-before-coastal37.py', 'coast_old_terrain')
    old_coast = source(baseline/'coastal_slice-before-coastal37.py', 'coast_old_placements')
    old_scene = source(baseline/'scene-before-coastal37.py', 'coast_old_scene')
    old_terrain.landscape_meshes = terrain.landscape_meshes
    queries = []

    def measured(x, y):
        queries.append((x, y))
        return old_terrain.ground_height(x, y)

    old_coast.ground_height = measured
    original_placements = old_coast.placements()
    reference = [old_terrain.ground_height(*point) for point in queries]
    setup = time.perf_counter()
    terrain.ground_cells()
    setup_ms = (time.perf_counter()-setup)*1000
    timings = []
    for name, function in (('original', old_terrain.ground_height), ('indexed', terrain.ground_height),
                           ('indexed', terrain.ground_height), ('original', old_terrain.ground_height)):
        started = time.perf_counter()
        values = [function(*point) for point in queries]
        elapsed = (time.perf_counter()-started)*1000
        assert values == reference
        timings.append({'mode': name, 'queries': len(queries), 'wall_ms': elapsed})
    assert [asdict(item) for item in coastal_slice.placements()] == [asdict(item) for item in original_placements]
    pairs = []
    previous, current = old_scene.Scene.__new__(old_scene.Scene), Scene.__new__(Scene)
    for filename in ('nature/tree_pineTallA.glb', 'nature/tree_pineTallB.glb', 'nature/rock_largeA.glb'):
        for variant in ((None, 'a', 'b') if 'tree' in filename else (None,)):
            first, second = previous.load_model(filename), current.load_model(filename)
            try:
                foundation.style_existing_prop(first)
                foundation.style_existing_prop(second)
                if variant is not None:
                    old_coast.dress_existing_tree(first, variant)
                    coastal_slice.dress_existing_tree(second, variant)
                assert geometry(first) == geometry(second), (filename, variant)
                assert first.getTightBounds() == second.getTightBounds()
                pairs.append({'model': filename, 'crown': variant, 'geometry_material_equal': True})
            finally:
                first.removeNode()
                second.removeNode()
    report = {'passed': True, 'height_queries': timings, 'ground_cells_setup_ms': setup_ms,
              'placements_equal': True, 'placements': len(original_placements), 'models': pairs,
              'scope': '真实570个种植支撑点高度逐值相同、全部摆放相同、原树/石及两冠几何/材质/外廓相同；离场分项，非正常驾驶FPS或完整GPU检查。'}
    (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    arguments = parser.parse_args()
    check(arguments.output.resolve(), arguments.baseline.resolve())
