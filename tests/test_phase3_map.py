"""The coastal loop has one source of truth for road shape and collisions."""

import math

import pytest

from coastal_map import MAP_POINT_COUNT, MAP_POINTS, map_length
from simulation import Control, Simulation


def test_coastal_loop_is_long_and_has_real_grade():
    assert len(MAP_POINTS) == MAP_POINT_COUNT
    assert map_length() > 600
    assert max(point.z for point in MAP_POINTS) - min(point.z for point in MAP_POINTS) > 4
    assert all(
        2
        < math.dist(
            (point.x, point.y),
            (MAP_POINTS[(i + 1) % MAP_POINT_COUNT].x, MAP_POINTS[(i + 1) % MAP_POINT_COUNT].y),
        )
        < 4
        for i, point in enumerate(MAP_POINTS)
    )


@pytest.mark.parametrize("speed", [60, 90])
def test_two_complete_ordered_laps(speed):
    from phase3_route_check import check_route

    report = check_route(speed)
    assert report["passed"], report


@pytest.mark.parametrize("index", range(0, MAP_POINT_COUNT, 32))
def test_every_sampled_map_point_supports_the_car(index):
    point = MAP_POINTS[index]
    simulation = Simulation(31)
    try:
        simulation.reset_player((point.x, point.y, point.z + 0.55), point.heading)
        for _ in range(180):
            simulation.step(Control())
        car = simulation.snapshot().player
        assert car.position[2] > point.z + 0.25
        assert all(w.getRaycastInfo().isInContact() for w in simulation._vehicle.getWheels())
    finally:
        simulation.close()
