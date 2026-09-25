"""Wheel rays must see the displayed road, including collision-box seams."""

import pytest
from panda3d.core import BitMask32, Vec3

from simulation import Control, Simulation


def test_highway_surface_queries_match_the_flat_road():
    sim = Simulation(track="highway", traffic_count=0)
    try:
        for y in range(-20, 1421, 20):
            for dy in (-0.001, 0, 0.001):
                if not -20 <= y + dy <= 1420:
                    continue
                for x in (-5.34, -3.66, -0.84, 0.84, 3.66, 5.34, -7.2, 7.2):
                    hit = sim._world.rayTestClosest(
                        Vec3(x, y + dy, 2), Vec3(x, y + dy, -2), BitMask32.bit(0)
                    )
                    assert hit.hasHit()
                    assert hit.getHitPos().z == pytest.approx(0, abs=0.015)
    finally:
        sim.close()


def test_high_speed_crosses_short_slab_seams_without_bouncing():
    sim = Simulation(track="highway", traffic_count=0)
    try:
        for _ in range(240):
            sim.step(Control())
        sim._chassis.setLinearVelocity(Vec3(0, 44, 0))
        for _ in range(2400):
            sim.step(Control(throttle=1))
            car = sim.snapshot().player
            assert 0.3 < car.position[2] < 0.65
            assert abs(car.pitch) < 3 and abs(car.roll) < 3
        assert car.position[1] > 750
    finally:
        sim.close()
