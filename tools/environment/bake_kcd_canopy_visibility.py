"""用原树三角形和atlas透明遮罩离线估计天空可见率；不改游戏物理世界。"""

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from zipfile import ZipFile

import numpy as np
from panda3d.bullet import (
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
    BulletWorld,
)
from panda3d.core import Vec3
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from kcd_local_assets import INSTALL, TREE, decode_texture, read_mesh


def prepare(output):
    """包版本变化或缓存缺失时重算；已准备的本机入口只做文件检查。"""
    source = (INSTALL / 'IPL_Objects-part5.pak').stat()
    key = {'algorithm': 1, 'rays': 24, 'package_size': source.st_size, 'package_mtime_ns': source.st_mtime_ns}
    manifest = output / 'manifest.json'
    files = [output / ('quercus_' + letter + suffix + '.json')
             for letter in 'abcde' for suffix in ('', '_lod1', '_lod2')]
    if manifest.is_file() and json.loads(manifest.read_text(encoding='utf-8'))['cache_key'] == key and all(p.is_file() for p in files):
        return
    output.mkdir(parents=True, exist_ok=True)
    atlas = output / 'oak.png'
    with ZipFile(INSTALL / 'IPL_Objects-part5.pak') as package:
        decode_texture(package, TREE + 'quercus_atlas_diff.dds', '.5', (2048, 1024), atlas)
    reports = [bake(letter, output, atlas, 24) for letter in 'abcde']
    pending = manifest.with_suffix('.json.tmp')
    pending.write_text(json.dumps({'cache_key': key, 'trees': reports}, ensure_ascii=False, indent=2), encoding='utf-8')
    pending.replace(manifest)


def bake(letter, output, atlas, rays):
    output.mkdir(parents=True, exist_ok=True)
    with ZipFile(INSTALL / 'IPL_Objects-part5.pak') as package:
        levels = [read_mesh(package.read(TREE + 'quercus_' + letter + suffix + '.cgfm'))
                  for suffix in ('', '_lod1', '_lod2')]
        atlas_hash = hashlib.sha256(package.read(TREE + 'quercus_atlas_diff.dds')
                                    + package.read(TREE + 'quercus_atlas_diff.dds.5')).hexdigest()
    original = levels[0]
    points = [Vec3(*p) for p in original['points']]
    triangles, mesh = [], BulletTriangleMesh()
    for a, b, c in original['faces']:
        origin, edge1, edge2 = points[a], points[b] - points[a], points[c] - points[a]
        d00, d01, d11 = edge1.dot(edge1), edge1.dot(edge2), edge2.dot(edge2)
        determinant = d00 * d11 - d01 * d01
        if determinant <= 1e-12:
            continue
        mesh.addTriangle(points[a], points[b], points[c])
        triangles.append((origin, edge1, edge2, d00, d01, d11, 1 / determinant,
                          original['uv'][a], original['uv'][b], original['uv'][c]))
    alpha = np.array(Image.open(atlas).convert('RGBA'))[:, :, 3]
    height, width = alpha.shape
    body = BulletRigidBodyNode('offline-canopy-visibility')
    body.addShape(BulletTriangleMeshShape(mesh, dynamic=False))
    world = BulletWorld()
    world.attachRigidBody(body)
    directions = [Vec3(math.sqrt(1 - ((i + .5) / rays) ** 2) * math.cos(i * 2.3999632297),
                       math.sqrt(1 - ((i + .5) / rays) ** 2) * math.sin(i * 2.3999632297),
                       (i + .5) / rays) for i in range(rays)]

    def opaque(hit):
        a, e1, e2, d00, d01, d11, inverse, uv0, uv1, uv2 = triangles[hit.getTriangleIndex()]
        delta = hit.getHitPos() - a
        d20, d21 = delta.dot(e1), delta.dot(e2)
        v, w = (d11 * d20 - d01 * d21) * inverse, (d00 * d21 - d01 * d20) * inverse
        u = uv0[0] + (uv1[0] - uv0[0]) * v + (uv2[0] - uv0[0]) * w
        t = uv0[1] + (uv1[1] - uv0[1]) * v + (uv2[1] - uv0[1]) * w
        # Panda UV原点在左下，PIL原点在左上；原件atlas使用repeat。
        return alpha[int((1 - t) * height) % height, int(u * width) % width] >= 64

    started, cache, report = time.perf_counter(), {}, []
    for level, source in enumerate(levels):
        values = []
        for vertex in source['points']:
            key = tuple(round(v, 5) for v in vertex)
            if key not in cache:
                origin = Vec3(*vertex)
                visible = 0
                for direction in directions:
                    hits = world.rayTestAll(origin + direction * .04, origin + direction * 5.)
                    blocked = any(opaque(hit) for hit in sorted(hits.getHits(), key=lambda h: h.getHitFraction()))
                    visible += not blocked
                cache[key] = visible / rays
            values.append(cache[key])
        record = {'source_sha256': source['sha256'], 'source_atlas_sha256': atlas_hash,
                  'sky_visibility': values}
        path = output / ('quercus_' + letter + ('' if not level else '_lod' + str(level)) + '.json')
        pending = path.with_suffix('.json.tmp')
        pending.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
        pending.replace(path)
        report.append({'lod': level, 'vertices': len(values), 'min': min(values), 'mean': float(np.mean(values)),
                       'max': max(values), 'file': path.name})
        print('CANOPY', letter, level, report[-1], 'seconds', time.perf_counter() - started, flush=True)
    result = {'scope': '本机原件的离线遮罩射线估计；非原引擎GI；游戏Simulation未参与', 'tree': letter,
              'reference_sha256': original['sha256'], 'rays': rays, 'radius_m': 5., 'bias_m': .04,
              'source_atlas_sha256': atlas_hash,
              'alpha_cutoff': .25, 'seconds': time.perf_counter() - started, 'lods': report}
    report_path = output / ('quercus_' + letter + '-report.json')
    pending = report_path.with_suffix('.json.tmp')
    pending.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    pending.replace(report_path)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trees', default='a')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--atlas', type=Path, default=ROOT / 'logs/local-kcd-drive/assets/oak.png')
    parser.add_argument('--rays', type=int, default=24)
    arguments = parser.parse_args()
    for family in arguments.trees:
        bake(family, arguments.output.resolve(), arguments.atlas.resolve(), arguments.rays)
