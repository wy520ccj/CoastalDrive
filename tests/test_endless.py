import math

import pytest
from panda3d.core import Vec3
from traffic_interaction_check import _run_case

from highway_driver import HighwayDriver, acceleration
from session import Phase, Session
from simulation import Control, Simulation, interpolate
from traffic import Driver, Road
from vehicle_state import CarState


def test_idm_reacts_to_speed_difference_and_stopped_leader():
    assert acceleration(20, 30) > 0
    assert acceleration(20, 30, 25, 5) < acceleration(20, 30, 25, 20)
    assert acceleration(0, 30, 2, 0) < 0


def test_fast_rear_car_and_reserved_gap_block_lane_change():
    driver = HighwayDriver(1, 42)
    car = CarState((0, 100, 0.42), speed=20)
    rear = CarState((4.5, 70, 0.42), speed=35)
    road = Road("endless")
    assert driver.opportunity(car, [rear], road, 2, []) is None
    assert driver.opportunity(car, [], road, 2, [(2, 110, 20)]) is None
    assert driver.opportunity(car, [], road, 2, []) is not None


def test_two_drivers_do_not_reserve_the_same_middle_gap():
    road = Road("endless")
    left, right = HighwayDriver(0, 1), HighwayDriver(2, 2)
    left.decision_clock = right.decision_clock = 0
    a = CarState((-4.5, 100, 0.42), speed=20)
    b = CarState((4.5, 105, 0.42), speed=20)
    slow = [CarState((-4.5, 125, 0.42), speed=5), CarState((4.5, 130, 0.42), speed=5)]
    reservations = []
    left.plan(a, [b, *slow], road, reservations)
    right.plan(b, [a, *slow], road, reservations)
    assert left.phase == "signal" and left.target_lane == 1
    assert right.phase == "cruise"


def test_forward_preview_is_not_current_path_deviation():
    road = Road("endless")
    driver = Driver(1, 20, target_lateral=0.2, preview_lateral=4.5)
    car = CarState((0, 100, .42), speed=20)
    action = driver.control(car, [], road, [road.locate(car)])
    assert not driver.recovering
    assert action.steering > 0
    assert action.brake == 0


def test_rear_yield_finishes_physically_without_rear_braking_or_contact():
    def target(sim):
        driver = sim.drivers[0]
        driver.preferred_speed = driver.cruise = driver.target_speed = 25.0
        driver.speed_clock = 100.0

    def hold_player_speed(sim, elapsed):
        error = 32 - sim.player.snapshot().speed
        return Control(throttle=max(0, min(1, .55 + error * .08)))

    result = _run_case("rear_approach", 23, 1, 38, 32, [(1, 98, 20)], 8,
                       configure=target, control_for=hold_player_speed)
    assert result["passed"], result["failures"]
    assert result["metrics"]["traffic"][0]["lane_changes"] == 1
    assert abs(result["metrics"]["traffic"][0]["end_position"][0] - 4.5) < .25


def test_cut_in_cancels_before_leaving_original_lane():
    road = Road("endless")
    driver = HighwayDriver(1, 3)
    driver.phase, driver.target_lane, driver.signal = "changing", 2, 1
    car = CarState((0.4, 100, 0.42), speed=20)
    intrusion = CarState((4.5, 102, 0.42), speed=10)
    driver.plan(car, [intrusion], road, [])
    assert driver.phase == "cruise" and driver.lane == 1
    assert driver.signal == 0


def test_driver_variation_is_seeded_and_smooth():
    a, b, c = HighwayDriver(1, 42), HighwayDriver(1, 42), HighwayDriver(1, 43)
    assert a.preferred_speed == b.preferred_speed != c.preferred_speed
    car, road = CarState((0, 0, 0.42), speed=20), Road("endless")
    previous = a.cruise
    for _ in range(1000):
        a.plan(car, [], road, [])
        b.plan(car, [], road, [])
        assert abs(a.cruise - previous) <= 0.030001
        assert a.cruise == b.cruise
        previous = a.cruise


def test_rebase_preserves_motion_and_interpolation():
    sim = Simulation(track="endless")
    try:
        sim.reset_player((0, 2010, 0.55))
        sim._chassis.setLinearVelocity(Vec3(0, 25, 0))
        before = sim.snapshot()
        sim._rebase()
        after = sim.snapshot()
        assert after.origin_y == 2000
        assert after.player.speed == before.player.speed
        for a, b in zip((before.player, *before.traffic), (after.player, *after.traffic)):
            assert b.position[1] + after.origin_y == pytest.approx(a.position[1], abs=0.001)
            assert b.steering == a.steering and b.rpm == a.rpm
            for wa, wb in zip(a.wheels, b.wheels):
                assert wb.position[1] + 2000 == pytest.approx(wa.position[1], abs=0.001)
        mid = interpolate(before, after, 0.5)
        assert mid.player.position == after.player.position
        sim._update_stream()
        for y in (0, 199.999, 200, 200.001):
            for x in (-5.34, -0.84, 0.84, 5.34, 7.2):
                assert sim.ground_height(x, y) == pytest.approx(0, abs=0.015)
    finally:
        sim.close()


def test_reverse_reload_and_occupied_segment_retention():
    sim = Simulation(track="endless", traffic_count=0)
    try:
        old = set(sim.stream.segments)
        sim.stream.update(5000, 0, [8])
        assert 0 in sim.stream.segments
        sim.stream.update(-2200, 0, [])
        assert 0 not in sim.stream.segments
        sim.stream.update(8, 0, [])
        assert set(sim.stream.segments) == old
    finally:
        sim.close()


def test_lane_change_uses_vehicle_steering_and_finishes():
    sim = Simulation(track="endless", traffic_count=1)
    try:
        driver = sim.drivers[0]
        driver.lane = driver.target_lane = 1
        # 先完成直行准备；避免自动决策在准备期开始换道，又被测试强制重置信号。
        driver.decision_clock = 1000
        sim.npcs[0].reset((0, 150, 0.55))
        for _ in range(1000):
            sim.step(Control())
        driver.target_lane, driver.phase, driver.elapsed = 2, "signal", 0
        driver.signal = 1
        previous = sim.npcs[0].snapshot()
        steering_seen = False
        for _ in range(1800):
            sim.step(Control())
            car = sim.npcs[0].snapshot()
            assert math.dist(previous.position, car.position) < 0.4
            steering_seen |= abs(car.steering) > 0.1
            assert abs(car.roll) < 5
            previous = car
        assert driver.lane == 2 and driver.lane_changes == 1
        assert abs(car.position[0] - 4.5) < 0.3
        assert steering_seen
    finally:
        sim.close()


def test_headless_transform_cache_stays_bounded():
    from panda3d.core import TransformState

    sim = Simulation(track="endless", traffic_count=8)
    try:
        TransformState.garbageCollect()
        baseline = TransformState.getNumStates()
        for tick in range(3600):
            sim.step(Control(brake=1))
            sim.snapshot()
            if (tick + 1) % 120 == 0:
                assert TransformState.getNumStates() < baseline + 2000
    finally:
        sim.close()


def test_endless_session_reset_pause_and_restart():
    session = Session(track="endless")
    try:
        session.start(countdown=False)
        session.simulation.reset_player((0, 2100, 0.55))
        session.tick()
        assert session.current.origin_y == 2000
        session.reset_player()
        assert session.phase == Phase.DRIVING
        assert session.current.origin_y == 2000
        session.pause()
        before = session.current
        session.frame(1)
        assert session.current == before
        session.resume()
        session.start(countdown=False)
        assert session.current.origin_y == 0
        assert len(session.simulation.stream.segments) == 13
    finally:
        session.close()
