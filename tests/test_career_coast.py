"""沿海表现网格保持物理近路、原边界和粗细共边。"""

import math
from collections import Counter

import numpy as np
import pytest

from career_courses import CareerCourse
from career_terrain import terrain
from environment.career_coast import _data


def _boundary_segments(edges):
    result = set()
    for a, b in edges:
        a, b = tuple(round(v/2) for v in a), tuple(round(v/2) for v in b)
        dx, dy = b[0]-a[0], b[1]-a[1]
        count = math.gcd(abs(dx), abs(dy))
        points = [(a[0]+dx*i//count, a[1]+dy*i//count) for i in range(count+1)]
        result.update(tuple(sorted((points[i], points[i+1]))) for i in range(count))
    return result


@pytest.mark.parametrize('course_id', ('coast-club', 'coast-final'))
def test_baked_coast_preserves_physical_band_and_has_no_new_open_edges(course_id):
    physical = terrain(course_id)
    before = {i: (tuple(v), tuple(f)) for i, (v, f) in physical.items()}
    data = _data(course_id)
    points, faces = data['points'], data['faces']
    edges = np.concatenate((faces[:, (0, 1)], faces[:, (1, 2)], faces[:, (2, 0)]))
    edges.sort(axis=1)
    edges, counts = np.unique(edges, axis=0, return_counts=True)
    assert np.all(counts <= 2)
    actual_boundary = [(tuple(points[a, :2]), tuple(points[b, :2])) for a, b in edges[counts == 1]]
    original_edges = Counter()
    original_points = {}
    for vertices, triangles in physical.values():
        for face in triangles:
            for i in range(3):
                a, b = vertices[face[i]], vertices[face[(i+1) % 3]]
                original_edges[tuple(sorted((a[:2], b[:2])))] += 1
                original_points[a[:2]] = a[2]
    assert _boundary_segments(actual_boundary) == _boundary_segments(
        [edge for edge, count in original_edges.items() if count == 1])
    curve, checked = CareerCourse(course_id), 0
    for x, y, z in points:
        if (x, y) in original_points and abs(curve.project((float(x), float(y)))[1]) <= 35:
            assert z == np.float32(original_points[x, y])
            checked += 1
    assert checked > 100
    assert np.all(np.isfinite(points))
    assert np.allclose(np.linalg.norm(data['normals'], axis=1), 1., atol=1e-6)
    assert {i: (tuple(v), tuple(f)) for i, (v, f) in physical.items()} == before
