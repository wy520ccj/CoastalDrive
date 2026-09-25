from dataclasses import replace

import pytest

from highway_driver import HighwayDriver
from simulation import Control, Simulation, interpolate
from traffic import Road
from vehicle_state import CarState


def decide(driver, car, others=()):
    road = Road("endless")
    driver.plan(car, others, road, [])
    return driver.control(car, others, road, [road.locate(c) for c in (car, *others)])


def test_recovery_waits_for_nearby_and_approaching_traffic():
    driver = HighwayDriver(1, 9)
    car = CarState((0, 100, 0.42), heading=60)
    parked = CarState((-2, 104, 0.42))
    for _ in range(60):
        action = decide(driver, car, [parked])
        assert action.brake == 1 and action.throttle == 0
    approaching = CarState((-2, 60, 0.42), speed=25)
    for _ in range(20):
        action = decide(driver, car, [approaching])
        assert action.brake == 1
    for _ in range(20):
        action = decide(driver, car)
    assert action.throttle > 0 and driver.recovery.phase == "returning"
    assert decide(driver, car, [parked]).brake == 1


@pytest.mark.parametrize("car", [
    CarState((0, 100, 0.42), roll=100),
    CarState((0, 100, 0.42), heading=170),
    CarState((-6.5, 100, 0.42), heading=70),
])
def test_unrecoverable_pose_waits_instead_of_forcing_through_barrier(car):
    driver = HighwayDriver(1, 9)
    for _ in range(60):
        action = decide(driver, car)
        assert action.throttle == 0 and action.brake == 1
    assert driver.recovering


@pytest.mark.parametrize("shape,yaw", [("straight", 90), ("hills", -60)])
def test_displaced_car_returns_with_physical_controls(shape, yaw):
    sim = Simulation(track="endless", road_shape=shape, traffic_count=1)
    try:
        driver = sim.drivers[0]
        driver.lane = driver.target_lane = 1
        p = sim.road.sample(300, 1)
        sim.npcs[0].reset((p.x, p.y, p.z + 0.55), p.heading + yaw, p.grade)
        seen_recovery = False
        previous = sim.npcs[0].snapshot()
        for _ in range(18 * 120):
            sim.step(Control(brake=1))
            current = sim.snapshot()
            car = current.traffic[0]
            seen_recovery |= car.hazards
            assert car.generation == 0
            assert abs(car.position[0] - previous.position[0]) < 0.2
            assert abs(car.position[1] - previous.position[1]) < 0.4
            if car.hazards:
                assert interpolate(replace(current, traffic=(previous,)), current, 0.5).traffic[0].hazards
            previous = car
        local = sim.road.lane_frame(car)
        assert seen_recovery and not driver.recovering
        assert abs(local.position[0] - sim.road.lanes[driver.lane]) < 0.5
        assert abs(local.heading) < 6
        assert car.speed > 3
    finally:
        sim.close()
