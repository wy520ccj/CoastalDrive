"""旧/新路面索引完整树及ABBA构建成本；不替代窗口/物理吞吐验收。"""

import argparse
import hashlib
import importlib.util
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))

import curve_mesh
from highway_curve import HighwayCurve
from triangle_support import TriangleSupport


def payload(tree):
    return (tree.low, tree.high, tree.triangles, tree.center, tree.half, tree.triangle_bounds,
            tuple(payload(child) for child in tree.children))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('baseline_support', args.baseline)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    curve = HighwayCurve(23, hills=True)
    meshes = [tuple(tuple(vertices[i] for i in face) for face in faces)
              for index in (8, 9, 10, 11) for vertices, faces in curve_mesh.surfaces(curve, index).values()]
    rows = {'old': [], 'new': []}
    hashes = {}
    for label in ('old', 'new', 'new', 'old'):
        cls = module.TriangleSupport if label == 'old' else TriangleSupport
        wall, cpu = time.perf_counter(), time.thread_time()
        trees = [cls.build(mesh) for mesh in meshes]
        rows[label].append({'wall_ms': (time.perf_counter()-wall)*1000,
                            'cpu_ms': (time.thread_time()-cpu)*1000})
        hashes[label] = hashlib.sha256(pickle.dumps(tuple(payload(tree) for tree in trees), protocol=5)).hexdigest()
    assert hashes['old'] == hashes['new']
    result = {'passed': True, 'mesh_count': len(meshes), 'abba': rows, 'full_tree_sha256': hashes,
              'baseline_source_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
              'current_source_sha256': hashlib.sha256((ROOT/'src/triangle_support.py').read_bytes()).hexdigest(),
              'scope': '完整24网格各节点边界、排序、三角面与叶界字节相同；局部构建成本，不是总性能。'}
    (args.output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': True, 'abba': rows}))


if __name__ == '__main__':
    main()
