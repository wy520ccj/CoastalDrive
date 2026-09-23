"""Regression checks for road/shoulder gaps, invisible walls, recovery and camera clipping."""

import pytest
from panda3d.core import BitMask32, Vec3

from coastal_map import MAP_POINTS, SEA_LEVEL, map_length, offset_point, point_at, project
from session import Session
from simulation import Control, Simulation


@pytest.fixture
def sim():
    simulation = Simulation(31)
    yield simulation
    simulation.close()


def test_road_and_both_shoulders_have_continuous_support(sim):
    for i, a in enumerate(MAP_POINTS):
        b = MAP_POINTS[(i + 1) % len(MAP_POINTS)]
        for offset in (-5.4, 0, 5.4):
            start, end = offset_point(a, offset), offset_point(b, offset)
            for fraction in (0, 0.5):
                x, y, z = (p + (q - p) * fraction for p, q in zip(start, end))
                assert sim.ground_height(x, y) == pytest.approx(z, abs=0.015)


def test_both_rails_are_continuous_including_previously_invisible_sections(sim):
    for a in MAP_POINTS:
        for side in (-1, 1):
            start = Vec3(*offset_point(a, side * 5, 0.4))
            end = Vec3(*offset_point(a, side * 7, 0.4))
            hit = sim._world.rayTestClosest(start, end, BitMask32.bit(0))
            assert hit.hasHit()
            assert hit.getNode().getName() == ("outer-rail" if side > 0 else "inner-rail")


@pytest.mark.parametrize("offset", [-4.95, 4.95])
def test_raised_shoulders_support_the_vehicle(sim, offset):
    point = max(MAP_POINTS, key=lambda p: p.z)
    sim.reset_player(offset_point(point, offset, 0.55), point.heading, point.grade)
    for _ in range(240):
        sim.step(Control())
    car = sim.snapshot().player
    assert abs(car.roll) < 3
    assert car.position[2] > point.z + 0.3
    assert all(w.getRaycastInfo().isInContact() for w in sim._vehicle.getWheels())


def test_sea_has_no_invisible_floor_and_old_test_obstacles_are_absent(sim):
    hit = sim._world.rayTestClosest(Vec3(180, 200, 40), Vec3(180, 200, -30))
    assert not hit.hasHit()
    names = {b.getName() for b in sim._world.getRigidBodies()}
    assert not any(name.startswith(("slalom", "end-wall", "test-ground", "ramp")) for name in names)
    assert names >= {
        "road",
        "inner-shoulder",
        "outer-shoulder",
        "inner-rail",
        "outer-rail",
        "cliff",
        "island",
        "player-chassis",
    }
    assert not sim.on_asphalt(95, 600)


def test_projection_is_continuous_between_samples_and_at_loop_seam():
    for distance in (0.01, 125.35, map_length() - 0.01):
        point = point_at(distance)
        nearest, error, along = project(point.x, point.y)
        assert error < 1e-8
        assert along == pytest.approx(distance)
        assert nearest.z == pytest.approx(point.z)


def test_r_recovers_near_the_current_bend_and_clears_motion():
    session = Session()
    try:
        session.start(countdown=False)
        point = point_at(map_length() * 0.52)
        session.simulation.reset_player(offset_point(point, 8, 1), point.heading + 80)
        session.keyboard.press("w")
        session.reset_player()
        car = session.current.player
        distance, lateral = session.simulation.road.locate(car)
        _, _, expected_distance = project(point.x, point.y)
        assert min(abs(lateral - lane) for lane in session.simulation.road.lanes) < 0.35
        assert abs(session.simulation.road.delta(distance, expected_distance)) < 25
        assert (
            abs(
                (
                    car.heading
                    - session.simulation.road.sample(
                        distance,
                        min(
                            range(2), key=lambda i: abs(session.simulation.road.lanes[i] - lateral)
                        ),
                    ).heading
                    + 180
                )
                % 360
                - 180
            )
            < 5
        )
        assert abs(car.position[0] - point.x) < 3
        assert abs(car.position[1] - point.y) < 3
        assert abs((car.heading - point.heading + 180) % 360 - 180) < 5
        assert car.speed == 0 and car.throttle == 0
        assert not session.keyboard.pressed
    finally:
        session.close()


def test_falling_into_sea_recovers_at_nearby_road(sim):
    point = point_at(280)
    sim.reset_player(offset_point(point, 30, SEA_LEVEL - point.z - 2))
    sim.step(Control())
    car = sim.snapshot().player
    assert sim.snapshot().events == ("player_reset",)
    distance, lateral = sim.road.locate(car)
    _, _, expected_distance = project(point.x, point.y)
    assert min(abs(lateral - lane) for lane in sim.road.lanes) < 0.35
    assert abs(sim.road.delta(distance, expected_distance)) < 25
    lane = min(range(len(sim.road.lanes)), key=lambda i: abs(sim.road.lanes[i] - lateral))
    assert abs((car.heading - sim.road.sample(distance, lane).heading + 180) % 360 - 180) < 5
    assert car.position[2] > 0


def test_camera_cannot_sweep_through_rails_and_does_not_change_physics(sim):
    before = sim.snapshot()
    for point in MAP_POINTS[::16]:
        for side in (-1, 1):
            anchor = offset_point(point, 0, 1.4)
            desired = offset_point(point, side * 10, 0.6)
            actual = sim.camera_position(anchor, desired)
            assert (actual - Vec3(*anchor)).length() < (Vec3(*desired) - Vec3(*anchor)).length() - 1
            hit = sim._world.rayTestClosest(Vec3(*anchor), actual, BitMask32.bit(0))
            assert not hit.hasHit()
    assert sim.snapshot() == before


def test_camera_query_ignores_player_body(sim):
    anchor, desired = (95, 0, 1), (95, -10, 2)
    assert tuple(sim.camera_position(anchor, desired)) == pytest.approx(desired)


def test_water_recovery_is_not_interpolated_through_the_scenery():
    session = Session()
    try:
        session.start(countdown=False)
        session.simulation.reset_player((180, 200, SEA_LEVEL - 2))
        session.sync_snapshots()
        session.tick()
        assert session.current.events == ("player_reset",)
        assert session.previous == session.current
    finally:
        session.close()


@pytest.mark.parametrize("speed_kmh", [60, 120])
def test_oblique_guardrail_impact_does_not_tunnel(sim, speed_kmh):
    sim.reset_player((95, 0, 0.55), -15)
    for _ in range(120):
        sim.step(Control())
    direction = sim._chassis.getTransform().getQuat().getForward()
    sim._chassis.setLinearVelocity(direction * speed_kmh / 3.6)
    collision_events = []
    for _ in range(360):
        sim.step(Control())
        car = sim.snapshot().player
        assert project(*car.position[:2])[1] < 6
        assert abs(car.roll) < 45
        collision_events.extend(sim.snapshot().events)
    # 撞上实体护栏应记录一次事故，持续接触不能逐 tick 重复计数。
    assert collision_events == ["player_collision"]
