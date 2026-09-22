"""Behavior checks for faults missed by the initial vehicle integration."""

import math

import pytest

from simulation import Control, Simulation
from test_track import SPAWN, TEST_SPAWN

NEUTRAL = Control()


@pytest.fixture
def simulation():
    sim = Simulation(17, track="test")
    yield sim
    sim.close()


def drive(sim, seconds, control=NEUTRAL):
    for _ in range(round(seconds * 120)):
        sim.step(control)
    return sim.snapshot().player


def on_test_straight(sim):
    sim.reset_player(TEST_SPAWN)


def test_idle_car_has_four_ground_contacts_and_can_start(simulation):
    on_test_straight(simulation)
    idle = drive(simulation, 15)
    assert idle.position == pytest.approx((TEST_SPAWN[0], TEST_SPAWN[1], 0.419), abs=0.01)
    for wheel in simulation._vehicle.getWheels():
        ray = wheel.getRaycastInfo()
        assert ray.isInContact()
        assert tuple(ray.getContactPointWs())[2] == pytest.approx(0, abs=0.001)
        assert 0.2 < ray.getSuspensionLength() < 0.4
    car = drive(simulation, 3, Control(throttle=1))
    assert car.speed > 9
    assert car.position[1] > TEST_SPAWN[1] + 12
    assert abs(car.position[0] - TEST_SPAWN[0]) < 0.05


def test_acceleration_and_braking_distances(simulation):
    on_test_straight(simulation)
    drive(simulation, 2)
    for ticks in range(1, 1441):
        simulation.step(Control(throttle=1))
        if simulation.snapshot().player.speed >= 100 / 3.6:
            break
    else:
        pytest.fail("Car failed to reach 100 km/h within twelve seconds")
    assert 8 <= ticks / 120 <= 11
    start = simulation.snapshot().player.position[1]
    for _ in range(600):
        simulation.step(Control(brake=1))
        if abs(simulation.snapshot().player.speed) < 0.15:
            break
    else:
        pytest.fail("Car failed to stop")
    assert 35 <= simulation.snapshot().player.position[1] - start <= 50


def test_car_can_restart_after_braking_and_waiting(simulation):
    on_test_straight(simulation)
    drive(simulation, 2)
    drive(simulation, 4, Control(throttle=1))
    for _ in range(600):
        simulation.step(Control(brake=1))
        if abs(simulation.snapshot().player.speed) < 0.15:
            break
    drive(simulation, 15)
    start = simulation.snapshot().player.position
    car = drive(simulation, 3, Control(throttle=1))
    assert car.speed > 9
    assert car.position[1] - start[1] > 10


@pytest.mark.parametrize("steering", [-1, 1])
def test_low_speed_turn_is_substantial_and_returns_to_center(simulation, steering):
    on_test_straight(simulation)
    drive(simulation, 2)
    car = drive(simulation, 3, Control(steering=steering, throttle=0.5))
    assert steering * (car.position[0] - TEST_SPAWN[0]) > 2
    assert steering * car.heading < -30
    assert abs(car.roll) < 8
    car = drive(simulation, 1)
    assert abs(car.steering) < 0.1


def test_speed_limit_and_high_speed_turn_stay_upright(simulation):
    on_test_straight(simulation)
    drive(simulation, 2)
    car = drive(simulation, 22, Control(throttle=1))
    assert 150 <= car.speed * 3.6 <= 161
    for _ in range(480):
        simulation.step(Control(steering=1, throttle=0.4))
        car = simulation.snapshot().player
        assert abs(car.roll) < 25
        assert abs(car.pitch) < 25
        assert car.position[2] > 0.25
        assert math.isfinite(car.speed)


def test_collision_wall_stops_car_without_tunneling(simulation):
    simulation.reset_player((95, 670, SPAWN[2]))
    drive(simulation, 2)
    peak_speed = 0
    for _ in range(1200):
        simulation.step(Control(throttle=1))
        car = simulation.snapshot().player
        peak_speed = max(peak_speed, car.speed)
        assert car.position[1] < 719
    assert peak_speed > 10
    assert abs(car.speed) < 1


def test_shallow_ramp_has_real_height_and_body_pitch(simulation):
    simulation.reset_player((70, 25, SPAWN[2]))
    drive(simulation, 2)
    heights = []
    pitches = []
    for _ in range(1080):
        simulation.step(Control(throttle=0.4))
        car = simulation.snapshot().player
        heights.append(car.position[2])
        pitches.append(car.pitch)
        assert abs(car.roll) < 10
        assert car.position[2] > 0.25
    assert max(heights) > 1.1
    assert max(pitches) > 3
    assert car.position[1] > 55


def test_grass_slows_coasting_more_than_asphalt(simulation):
    losses = []
    for x in (95, 155):
        simulation.reset_player((x, 200, SPAWN[2]))
        drive(simulation, 2)
        drive(simulation, 3, Control(throttle=1))
        before = simulation.snapshot().player.speed
        after = drive(simulation, 4).speed
        losses.append(before - after)
    assert losses[1] > losses[0] + 1.5
    assert simulation.snapshot().player.surface == "grass"


def test_reset_clears_body_wheel_and_control_state(simulation):
    drive(simulation, 4, Control(throttle=1, steering=0.2))
    simulation.reset_player()
    car = simulation.snapshot().player
    assert car.position == pytest.approx(SPAWN)
    assert car.heading == car.pitch == car.roll == car.speed == car.steering == 0
    assert simulation.snapshot().events == ("player_reset",)
    for wheel in simulation._vehicle.getWheels():
        assert wheel.getEngineForce() == wheel.getBrake() == wheel.getSteering() == 0
    assert len(car.wheels) == 4
    assert drive(simulation, 3, Control(throttle=1)).position[1] > 10
