import math
from dataclasses import replace

import pytest
from panda3d.core import Vec3

from highway_driver import HighwayDriver
from simulation import Simulation, interpolate
from traffic import Road
from vehicle_state import CarState, Control


def state_on(road, s, d, speed):
    p = road.sample_lateral(s, d)
    h, grade = math.radians(p.heading), math.radians(p.grade)
    v = (-math.sin(h) * math.cos(grade) * speed,
         math.cos(h) * math.cos(grade) * speed, math.sin(grade) * speed)
    return CarState((p.x, p.y, p.z + 0.42), p.heading, speed, velocity=v)


def test_sensing_projects_speed_and_relative_heading_on_slope():
    road = Road("endless", seed=7, shape="hills")
    state = state_on(road, 220, 4.5, 30)
    local = road.lane_frame(state)
    assert local.position == pytest.approx((4.5, 220, 0.42), abs=0.001)
    assert local.velocity[:2] == pytest.approx((0, 30), abs=1e-6)
    assert local.heading == pytest.approx(0, abs=1e-6)


def test_curve_yield_matches_straight_road_decision():
    curve, straight = Road("endless", seed=3, shape="hills"), Road("endless")
    a, b = HighwayDriver(1, 7), HighwayDriver(1, 7)
    car = state_on(curve, 280, 0, 22)
    follower = state_on(curve, 245, 0, 30)
    for _ in range(15):
        a.plan(car, [follower], curve, [])
        b.plan(curve.lane_frame(car), [curve.lane_frame(follower)], straight, [])
    assert (a.phase, a.target_lane, a.reason) == (b.phase, b.target_lane, b.reason)
    assert a.reason == "yield_rear"


def test_curved_rebase_preserves_road_coordinates_and_support():
    sim = Simulation(track="endless", road_shape="hills", traffic_count=0)
    try:
        p = sim.road.sample(2200, 1)
        sim.reset_player((p.x, p.y, p.z + 0.55), p.heading, p.grade)
        sim._update_stream()
        sim.player._chassis.setLinearVelocity(Vec3(0, 25, 0))
        before = sim.snapshot()
        location = sim.road.locate(before.player)
        sim._rebase()
        after = sim.snapshot()
        assert sim.road.locate(after.player) == pytest.approx(location, abs=0.001)
        assert after.player.velocity == before.player.velocity
        assert interpolate(before, after, 0.5).player.position == pytest.approx(after.player.position)
        sim._update_stream()
        for s in (2199.999, 2200, 2200.001):
            p = sim.road.sample(s, 1)
            assert sim.ground_height(p.x, p.y) == pytest.approx(p.z, abs=0.015)
        assert sim.recover_player()
        reset_s, reset_d = sim.road.locate(sim.snapshot().player)
        assert reset_s == pytest.approx(2200, abs=0.001)
        assert reset_d == pytest.approx(0, abs=0.001)
    finally:
        sim.close()


def test_negative_curve_segments_can_reload():
    sim = Simulation(track="endless", road_shape="curves", traffic_count=0)
    try:
        p = sim.road.sample(-2400, 1)
        sim.reset_player((p.x, p.y, p.z + 0.55), p.heading)
        sim._update_stream()
        sim._rebase()
        current = sim.snapshot().player
        assert sim.road.locate(current)[0] == pytest.approx(-2400, abs=0.001)
        assert -12 in sim.stream.segments
        point = sim.road.sample(-2400, 1)
        assert sim.ground_height(point.x, point.y) == pytest.approx(point.z, abs=0.015)
        shifted = replace(current, position=(current.position[0], current.position[1] + 100, current.position[2]))
        assert sim.road.locate(shifted)[0] > -2400
    finally:
        sim.close()


def test_reverse_over_hill_segment_join_keeps_wheel_support():
    sim = Simulation(track="endless", road_shape="hills", traffic_count=0)
    try:
        p = sim.road.sample(200.5, 1)
        sim.reset_player((p.x, p.y, p.z + 0.55), p.heading, p.grade)
        sim._update_stream()
        distances = []
        for tick in range(960):
            sim.step(Control(brake=1))
            if tick % 120 == 0:
                car = sim.snapshot().player
                s, d = sim.road.locate(car)
                surface = sim.road.sample_lateral(s, d)
                assert 0.25 < car.position[2] - surface.z < 0.8
                distances.append(s)
        assert min(distances) < 198
        assert sim.collision_count == 0
    finally:
        sim.close()
