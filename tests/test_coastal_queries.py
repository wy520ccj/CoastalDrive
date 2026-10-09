"""完整道路查询保留边界、线段顺序和最近点的几何定义。"""

import math
import random

import pytest
from wheel_contact_kernels import road_strip_coefficients, road_strip_contains, road_strip_project

from coastal_map import MAP_POINTS, ROAD_SEGMENTS, ROAD_WIDTH, on_road, project


def test_ordered_projection_preserves_original_distance_arithmetic():
    random_source = random.Random(1709)
    points = [(random_source.uniform(-150, 150), random_source.uniform(-150, 150)) for _ in range(256)]
    points.extend((point.x, point.y) for point in MAP_POINTS)
    for x, y in points:
        candidates = []
        for i, a in enumerate(MAP_POINTS):
            b = MAP_POINTS[(i+1) % len(MAP_POINTS)]
            dx, dy = b.x-a.x, b.y-a.y
            t = max(0, min(1, ((x-a.x)*dx+(y-a.y)*dy)/(dx*dx+dy*dy)))
            distance = (x-a.x-t*dx)**2+(y-a.y-t*dy)**2
            candidates.append((distance, i, t))
        expected = min(candidates)
        actual = road_strip_project(road_strip_coefficients(ROAD_SEGMENTS, (ROAD_WIDTH/2)**2), x, y)
        assert actual == (expected[1], expected[2], expected[0])
        assert project(x, y)[1] == math.sqrt(expected[0])


def test_material_boundary_retains_one_ulp_inside_and_outside_and_projection_ties():
    strip = road_strip_coefficients(((0., 0., 10., 0., 100., -1., 11., -1., 1.),
                                     (0., 2., 10., 0., 100., -1., 11., 1., 3.)), 1.)
    assert road_strip_contains(strip, 5., 1.)
    assert road_strip_contains(strip, 5., math.nextafter(-1., 0.))
    assert not road_strip_contains(strip, 5., math.nextafter(-1., -math.inf))
    assert road_strip_project(strip, 5., 1.) == (0, .5, 1.)
    assert road_strip_project(strip, -1., 0.) == (0, 0., 1.)
    assert road_strip_project(strip, 11., 0.) == (0, 1., 1.)
    assert not road_strip_contains(strip, math.nan, 0.)
    assert not road_strip_contains(strip, math.inf, 0.)
    assert all(on_road(point.x, point.y) for point in MAP_POINTS)


@pytest.mark.parametrize('segments,width', [((), 1.), (((0.,)*9,), 1.), (ROAD_SEGMENTS, 0.)])
def test_invalid_external_geometry_is_reported(segments, width):
    with pytest.raises(ValueError):
        road_strip_coefficients(segments, width)
