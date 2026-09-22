import math
from itertools import pairwise

import pytest

from highway_curve import HighwayCurve


@pytest.mark.parametrize("hills", [False, True])
def test_projection_round_trip_across_signed_cells_and_seams(hills):
    for seed in range(10):
        road = HighwayCurve(seed, hills=hills)
        for s in (-3000.001, -2000, -0.001, 0, 199.999, 200, 500, 999.999, 1000, 2400):
            for d in (-8.5, -4.5, 0, 4.5, 8.5):
                p = road.sample(s, d)
                distance, lateral = road.project((p.x, p.y, p.z))
                assert distance == pytest.approx(s, abs=0.001)
                assert lateral == pytest.approx(d, abs=0.001)


def test_cell_joins_are_continuous_and_flat():
    road = HighwayCurve(42, hills=True)
    for s in range(-4000, 4001, 1000):
        a, b, c = (road.sample(s + delta) for delta in (-0.001, 0, 0.001))
        assert math.dist((a.x, a.y, a.z), (c.x, c.y, c.z)) < 0.00201
        assert b.heading == pytest.approx(0, abs=1e-9)
        assert b.grade == pytest.approx(0, abs=1e-9)


def test_arc_length_and_grade_bounds():
    road = HighwayCurve(7, hills=True)
    points = [road.sample(s) for s in range(1001)]
    length = sum(math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) for a, b in pairwise(points))
    assert length == pytest.approx(1000, abs=0.01)
    assert max(abs(math.tan(math.radians(p.grade))) for p in points) < 0.042
    assert min(p.z for p in points) >= 4


def test_samples_are_independent_of_query_order():
    road = HighwayCurve(11, hills=True)
    distances = [-2500, 2, 950, 1750, 9000000]
    expected = {s: road.sample(s) for s in distances}
    for s in reversed(distances):
        assert road.sample(s) == expected[s]
