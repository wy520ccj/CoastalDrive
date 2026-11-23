"""离线制作沿海生涯岸坡；只读原物理网格，粗细网格共边，草高场来自成品。"""

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))

from career_courses import CareerCourse
from career_terrain import terrain
from environment.expressway import smooth


def _plane(x, y, points):
    a, b, c = points
    area = (b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1])
    u = ((x-a[0])*(c[1]-a[1])-(y-a[1])*(c[0]-a[0]))/area
    v = ((b[0]-a[0])*(y-a[1])-(b[1]-a[1])*(x-a[0]))/area
    return a[2]*(1-u-v)+b[2]*u+c[2]*v, u, v


def build(course_id, output):
    course = CareerCourse(course_id)
    source = terrain(course_id)
    originals = [(owner, tuple(vertices[i] for i in face))
                 for owner, (vertices, faces) in source.items() for face in faces]
    profiles, old_heights, new_heights = {}, {}, {}

    def profile(x, y):
        key = x, y
        if key not in profiles:
            _station, lateral = course.project(key)
            coast = smooth(-90, 45, x-(30+.12*y+20*math.sin(y/240)))
            profiles[key] = abs(lateral), coast
        return profiles[key]

    # 原抬坡与最近道路基高分开处理；平滑基高不传入原物理地形。
    source_points = {p[:2]: p[2] for _owner, triangle in originals for p in triangle}
    base_left = min(p[0] for p in source_points)/8
    base_bottom = min(p[1] for p in source_points)/8
    base_width = round(max(p[0] for p in source_points)/8-base_left)+1
    base_height = round(max(p[1] for p in source_points)/8-base_bottom)+1
    values, weights = np.zeros((base_height, base_width)), np.zeros((base_height, base_width))
    for (x, y), z in source_points.items():
        distance, _coast = profile(x, y)
        bank = min(44., max(0., distance-36)*.24)
        row, col = round(y/8-base_bottom), round(x/8-base_left)
        values[row, col] = z-bank*(1+.15*math.sin(x*.018+y*.011))
        weights[row, col] = 1
    kernel = np.exp(-np.arange(-6, 7, dtype=float)**2/18)
    kernel /= kernel.sum()
    for axis in (0, 1):
        padding = [(0, 0), (0, 0)]
        padding[axis] = 6, 6
        for array in (values, weights):
            padded = np.pad(array, padding, mode='edge')
            array.fill(0)
            for offset, weight in enumerate(kernel):
                slices = [slice(None), slice(None)]
                slices[axis] = slice(offset, offset+array.shape[axis])
                array += padded[tuple(slices)]*weight
    base = np.divide(values, weights, out=np.zeros_like(values), where=weights > 0)

    def soft_base(x, y):
        px = min(base_width-1., max(0., x/8-base_left))
        py = min(base_height-1., max(0., y/8-base_bottom))
        col, row = min(base_width-2, max(0, math.floor(px))), min(base_height-2, max(0, math.floor(py)))
        u, v = px-col, py-row
        return (base[row, col]*(1-u)+base[row, col+1]*u)*(1-v)+(base[row+1, col]*(1-u)+base[row+1, col+1]*u)*v

    # 单片粗远景填满有限地形外侧；近路下方让开，外缘在相机裁剪面之外。
    bg_left = math.floor((min(p.x for p in course.points)-1700)/64)*64
    bg_bottom = math.floor((min(p.y for p in course.points)-1700)/64)*64
    bg_width = math.ceil((max(p.x for p in course.points)+1700-bg_left)/64)+1
    bg_height = math.ceil((max(p.y for p in course.points)+1700-bg_bottom)/64)+1
    background = []
    for row in range(bg_height):
        for col in range(bg_width):
            x, y = bg_left+col*64, bg_bottom+row*64
            station, lateral = course.project((x, y))
            distance, coast = profile(x, y)
            shape = .5+.25*math.sin(x/83+y/119)+.25*math.sin(x/147-y/71)
            land = soft_base(x, y)+12*(.75+.25*shape)
            far = land*(1-coast)-8*coast
            beyond = smooth(0, 180, max(-station, station-course.length, 0))
            low = course.sample(station).z-48*(1-beyond)-.8*beyond
            blend = smooth(96, 224, abs(lateral))
            background.append((x, y, low*(1-blend)+far*blend))
    bg_points = np.asarray(background)
    bg_faces = []
    for row in range(bg_height-1):
        for col in range(bg_width-1):
            a = row*bg_width+col
            bg_faces.extend(((a, a+1, a+bg_width+1), (a, a+bg_width+1, a+bg_width)))
    bg_faces = np.asarray(bg_faces, dtype=np.uint32)
    bg_normals = np.zeros_like(bg_points)
    bg_cross = np.cross(bg_points[bg_faces[:, 1]]-bg_points[bg_faces[:, 0]],
                        bg_points[bg_faces[:, 2]]-bg_points[bg_faces[:, 0]])
    for corner in range(3):
        np.add.at(bg_normals, bg_faces[:, corner], bg_cross)
    bg_normals /= np.linalg.norm(bg_normals, axis=1)[:, None]
    bg_alpha = np.asarray([.6*(1-smooth(.72, .94, n[2])) for n in bg_normals])

    def background_sample(x, y, field):
        px, py = (x-bg_left)/64, (y-bg_bottom)/64
        col, row = math.floor(px), math.floor(py)
        u, v = px-col, py-row
        a, b = row*bg_width+col, row*bg_width+col+1
        d, c = (row+1)*bg_width+col, (row+1)*bg_width+col+1
        return field[a]*(1-u)+field[b]*(u-v)+field[c]*v if u >= v else field[a]*(1-v)+field[c]*u+field[d]*(v-u)

    def height(x, y, old):
        key = x, y
        if key not in new_heights:
            distance, coast = profile(x, y)
            value = old
            if distance > 38:
                bank = min(44., max(0., distance-36)*.24)
                lip = min(44., max(0., min(distance, 38)-36)*.24)
                edge = old-(bank-lip)*(1+.15*math.sin(x*.018+y*.011))
                soften = smooth(38, 104, distance)
                elevation = soft_base(x, y)
                shape = .5+.25*math.sin(x/83+y/119)+.25*math.sin(x/147-y/71)
                hill = min(12., max(0., distance-36)*.18)*(.75+.25*shape)
                land = old*(1-soften)+(elevation+hill)*soften
                edge = edge*(1-soften)+(elevation+lip)*soften
                fall = smooth(38, 92, distance)
                value = land*(1-coast)+(edge*(1-fall)-8*fall)*coast
                outer = smooth(128, 208, distance)
                value = value*(1-outer)+(float(background_sample(x, y, bg_points[:, 2]))+.08)*outer
            old_heights[key], new_heights[key] = old, value
        return new_heights[key]

    refined, edges = [], defaultdict(list)
    for number, (_owner, triangle) in enumerate(originals):
        fields = [profile(x, y) for x, y, _z in triangle]
        refined.append(min(d for d, _c in fields) < 56 and max(d for d, _c in fields) > 24)
        for x, y, z in triangle:
            height(x, y, z)
        for i in range(3):
            edge = tuple(sorted((triangle[i][:2], triangle[(i+1) % 3][:2])))
            edges[edge].append(number)
    split_edges = {edge for edge, adjacent in edges.items() if any(refined[i] for i in adjacent)}
    border_edges = {edge for edge in split_edges if not all(refined[i] for i in edges[edge])}
    positions, reference_z, ids, faces, owners = [], [], {}, [], []

    def vertex(x, y, old, forced=None):
        key = x, y
        if key not in ids:
            ids[key] = len(positions)
            value = height(x, y, old) if forced is None else forced
            positions.append((x, y, value))
            reference_z.append(old)
        return ids[key]

    # 先登记原点，粗细边界的每个点只持有一份最终高度。
    for _owner, triangle in originals:
        for x, y, z in triangle:
            vertex(x, y, z)
    for number, (owner, triangle) in enumerate(originals):
        if not refined[number]:
            continue
        a, b, c = triangle
        lattice = {}
        for i in range(5):
            for j in range(5-i):
                x = a[0]+(b[0]-a[0])*i/4+(c[0]-a[0])*j/4
                y = a[1]+(b[1]-a[1])*i/4+(c[1]-a[1])*j/4
                old = a[2]+(b[2]-a[2])*i/4+(c[2]-a[2])*j/4
                boundary = ((a, b, i/4) if j == 0 else
                            (a, c, j/4) if i == 0 else
                            (b, c, j/4) if i+j == 4 else None)
                forced = None
                if boundary is not None:
                    first, last, t = boundary
                    if tuple(sorted((first[:2], last[:2]))) in border_edges:
                        forced = new_heights[first[:2]]*(1-t)+new_heights[last[:2]]*t
                lattice[i, j] = vertex(x, y, old, forced)
        for i in range(4):
            for j in range(4-i):
                faces.append((lattice[i, j], lattice[i+1, j], lattice[i, j+1]))
                owners.append(owner)
                if i+j < 3:
                    faces.append((lattice[i+1, j], lattice[i+1, j+1], lattice[i, j+1]))
                    owners.append(owner)
    for number, (owner, triangle) in enumerate(originals):
        if refined[number]:
            continue
        polygon = []
        for i in range(3):
            a, b = triangle[i], triangle[(i+1) % 3]
            polygon.append(ids[a[:2]])
            if tuple(sorted((a[:2], b[:2]))) in split_edges:
                for part in (1, 2, 3):
                    t = part/4
                    polygon.append(ids[a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t])
        if len(polygon) == 3:
            faces.append(tuple(polygon))
            owners.append(owner)
            continue
        # 中心仍在2米格点，扇面把邻接细边全部接入；远处面不额外变弯。
        x, y = (round(sum(p[axis] for p in triangle)/6)*2 for axis in (0, 1))
        old = _plane(x, y, triangle)[0]
        changed = [(a, b, new_heights[a, b]) for a, b, _z in triangle]
        center = vertex(x, y, old, _plane(x, y, changed)[0])
        for i, first in enumerate(polygon):
            faces.append((center, first, polygon[(i+1) % len(polygon)]))
            owners.append(owner)
    points, triangles = np.asarray(positions), np.asarray(faces, dtype=np.uint32)
    crosses = np.cross(points[triangles[:, 1]]-points[triangles[:, 0]],
                       points[triangles[:, 2]]-points[triangles[:, 0]])
    assert np.all(crosses[:, 2] > 0)
    normals = np.zeros_like(points)
    for corner in range(3):
        np.add.at(normals, triangles[:, corner], crosses)
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    # 岸脚与陡面使用原岩石材料；未降坡的原近路表面仍为0权重。
    alpha = np.asarray([.85*smooth(.2, 2, old-z)*max(.15, 1-smooth(-3, 1, z),
                         1-smooth(.72, .94, n[2]))
                        for old, (_x, _y, z), n in zip(reference_z, positions, normals, strict=True)])
    for number, (x, y, _z) in enumerate(positions):
        outer = smooth(128, 208, profile(x, y)[0])
        if outer:
            normals[number] = normals[number]*(1-outer)+background_sample(x, y, bg_normals)*outer
            normals[number] /= np.linalg.norm(normals[number])
            alpha[number] = alpha[number]*(1-outer)+background_sample(x, y, bg_alpha)*outer
    left, bottom = np.floor(points[:, :2].min(axis=0)/2).astype(int)
    right, top = np.ceil(points[:, :2].max(axis=0)/2).astype(int)
    heights = np.full((top-bottom+1, right-left+1), np.nan, dtype=np.float32)
    for face in triangles:
        triangle = points[face]
        low = np.ceil(triangle[:, :2].min(axis=0)/2).astype(int)
        high = np.floor(triangle[:, :2].max(axis=0)/2).astype(int)
        for row in range(low[1], high[1]+1):
            for col in range(low[0], high[0]+1):
                z, u, v = _plane(col*2, row*2, triangle)
                if u >= -1e-8 and v >= -1e-8 and u+v <= 1+1e-8:
                    previous = heights[row-bottom, col-left]
                    if np.isfinite(previous):
                        assert abs(float(previous)-z) < 1e-4
                    heights[row-bottom, col-left] = z
    output.mkdir(parents=True, exist_ok=True)
    path = output/(course_id+'.npz')
    np.savez_compressed(path, points=points.astype(np.float32), faces=triangles,
                        owners=np.asarray(owners, dtype=np.int16), normals=normals.astype(np.float32),
                        alpha=alpha.astype(np.float32), heights=heights,
                        grid_origin=np.asarray((left*2, bottom*2), dtype=np.float32),
                        bg_points=(bg_points-np.asarray((0., 0., .04))).astype(np.float32), bg_faces=bg_faces,
                        bg_normals=bg_normals.astype(np.float32), bg_alpha=bg_alpha.astype(np.float32))
    report = {'course': course_id, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'sources': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
                  'src/career_courses.py', 'src/career_terrain.py', 'tools/environment/prepare_career_coast.py')},
              'original_triangles': len(originals), 'refined_original_triangles': sum(refined),
              'triangles': len(triangles), 'vertices': len(points), 'grid_step': 2,
              'file_bytes': path.stat().st_size, 'protected_radius': 35, 'height_change_start': 38,
              'background_triangles': len(bg_faces), 'background_vertices': len(bg_points),
              'scope': 'Original visual mesh; physics terrain remains unchanged; rendered/performance acceptance pending'}
    path.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--courses', nargs='+', choices=('coast-club', 'coast-final'), default=('coast-club', 'coast-final'))
    args = parser.parse_args()
    for course_id in args.courses:
        build(course_id, args.output.resolve())
