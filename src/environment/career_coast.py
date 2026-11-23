"""有限沿海生涯的离线表现网格与海面；不替换物理地形。"""

import hashlib
import json
import math
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from panda3d.core import Shader

from paths import resource_root


def _enabled(course_id):
    return course_id in ('coast-club', 'coast-final') and os.environ.get('COASTALDRIVE_COAST_CANDIDATE') == '1'


def _shoreline(y):
    return 30+.12*y+20*math.sin(y/240)


@lru_cache(maxsize=2)
def _data(course_id):
    folder = resource_root()/'assets/game/environment/career-coast'
    path = folder/(course_id+'.npz')
    metadata = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata['sha256']:
        raise ValueError('沿海生涯表现网格校验失败：'+str(path))
    with np.load(path, allow_pickle=False) as stored:
        result = {name: stored[name] for name in ('points', 'faces', 'owners', 'normals',
                                                 'alpha', 'heights', 'grid_origin', 'bg_points', 'bg_faces',
                                                 'bg_normals', 'bg_alpha')}
    for value in result.values():
        value.setflags(write=False)
    return result


def _segment(course_id, index, origin):
    data = _data(course_id)
    faces = data['faces'][data['owners'] == index]
    if not len(faces):
        return None
    selected, remap = np.unique(faces, return_inverse=True)
    vertices = data['points'][selected]-np.asarray(tuple(origin))
    normals = data['normals'][selected]
    colors = [(.24, .34, .08, float(a)) for a in data['alpha'][selected]]
    return vertices.tolist(), remap.reshape(-1, 3).tolist(), normals.tolist(), colors


def _height(course_id, x, y):
    data = _data(course_id)
    col, row = (x-float(data['grid_origin'][0]))/2, (y-float(data['grid_origin'][1]))/2
    left, bottom = math.floor(col), math.floor(row)
    heights = data['heights']
    if not (0 <= left < heights.shape[1]-1 and 0 <= bottom < heights.shape[0]-1):
        return None
    a, b, c, d = (float(heights[j, i]) for i, j in (
        (left, bottom), (left+1, bottom), (left+1, bottom+1), (left, bottom+1)))
    if not all(math.isfinite(v) for v in (a, b, c, d)):
        return None
    u, v = col-left, row-bottom
    return a*(1-u)+b*(u-v)+c*v if u >= v else a*(1-v)+c*u+d*(v-u)


def _backdrop(course_id):
    from environment.surface_mesh import surface_mesh

    data = _data(course_id)
    points = data['bg_points']
    colors = [(.24, .34, .08, float(a)) for a in data['bg_alpha']]
    return surface_mesh('career-backdrop', points, data['bg_faces'], data['bg_normals'], colors, points[:, :2])


def _water_surface(curve):
    bottom = min(p.y for p in curve.points)-1400
    top = max(p.y for p in curve.points)+1400
    count = math.ceil((top-bottom)/80)
    vertices, faces = [], []
    right = max(p.x for p in curve.points)+2200
    for row in range(count+1):
        y = bottom+(top-bottom)*row/count
        vertices.extend(((_shoreline(y)-100, y, -3), (right, y, -3)))
        if row:
            a = (row-1)*2
            faces.extend(((a, a+1, a+3), (a, a+3, a+2)))
    return vertices, faces


@lru_cache(maxsize=1)
def _water_shader():
    from environment.expressway_materials import shader_path

    folder = resource_root()/'assets/game/environment/career-coast'
    vertex = (folder/'water.vert').read_text(encoding='utf-8')
    fragment = (folder/'water.frag').read_text(encoding='utf-8')
    haze = Path(shader_path('distance-haze.glsl').toOsSpecific()).read_text(encoding='utf-8')
    fragment = fragment.replace('void main() {', haze+'\nvoid main() {')
    return Shader.make(Shader.SLGLSL, vertex, fragment)
