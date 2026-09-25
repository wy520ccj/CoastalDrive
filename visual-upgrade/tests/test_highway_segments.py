from math import floor

import pytest

from highway_segments import (
    KEEP_RADIUS,
    REBASE_DISTANCE,
    SEGMENT_LENGTH,
    indices_around,
    segment,
    segment_index,
    surface_meshes,
)


def test_public_constants_and_segment_determinism():
    assert (SEGMENT_LENGTH, KEEP_RADIUS, REBASE_DISTANCE) == (200, 1200, 2000)
    for seed in range(10):
        assert segment(seed, -3) == segment(seed, -3)
        assert segment(seed, 10**12).index == 10**12
        assert all(abs(tree[0]) >= 20 and 0 <= tree[1] <= SEGMENT_LENGTH for tree in segment(seed, 2).trees)


def test_segment_is_independent_of_other_load_order():
    expected = {index: segment(42, index) for index in (-100, -1, 0, 1, 100)}
    for index in (100, 1, -100, 0, -1, 1, 100):
        assert segment(42, index) == expected[index]


@pytest.mark.parametrize("y", [-400.0, -200.0, -0.001, 0.0, 199.999, 200.0, 401.0])
def test_segment_index_uses_floor_at_negative_boundaries(y):
    assert segment_index(y) == floor(y / SEGMENT_LENGTH)


def test_indices_around_is_contiguous_and_inclusive():
    indices = indices_around(0.0)
    assert indices == range(-6, 7)
    assert list(indices_around(-200.0, 0)) == [-1]


def test_surface_meshes_are_short_strips_and_closed_rails():
    meshes = surface_meshes()
    assert {"road", "shoulder-left", "shoulder-right", "ground", "rail-left", "rail-right"} <= meshes.keys()
    for name in ("road", "shoulder-left", "shoulder-right", "ground"):
        vertices, triangles = meshes[name]
        assert min(v[1] for v in vertices) == 0
        assert max(v[1] for v in vertices) == SEGMENT_LENGTH
        assert len(triangles) == 10
    for name in ("rail-left", "rail-right"):
        vertices, triangles = meshes[name]
        assert len(vertices) == 8 and len(triangles) == 12
        assert {v[2] for v in vertices} == {0.0, 0.8}
