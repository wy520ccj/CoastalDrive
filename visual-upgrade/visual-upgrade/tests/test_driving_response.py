"""Short taps, gradual steering and drivetrain transitions should feel continuous."""

import pytest

from chase_camera import ChaseCamera
from simulation import FIXED_DT, CarState, Control, Simulation
from test_track import TEST_SPAWN
from vehicle_response import VehicleResponse


def straight_simulation():
    sim = Simulation(track="test")
    sim.reset_player(TEST_SPAWN)
    return sim


def test_short_throttle_tap_does_not_leave_power_latched():
    sim = straight_simulation()
    try:
        for _ in range(240):
            sim.step(Control())
        peak = 0.0
        for tick in range(240):
            sim.step(Control(throttle=1) if tick < 18 else Control())
            peak = max(peak, sim.snapshot().player.speed)
        assert 0 < peak * 3.6 < 1
        assert sim.snapshot().player.throttle == 0
        assert abs(sim.response.force) < 0.01
    finally:
        sim.close()


def test_held_throttle_builds_speed_and_changes_gears():
    sim = straight_simulation()
    try:
        for _ in range(240):
            sim.step(Control())
        checkpoints = {}
        gear_changes = []
        last_gear = 1
        for tick in range(1, 1201):
            sim.step(Control(throttle=1))
            car = sim.snapshot().player
            if tick in (60, 120, 360, 600, 1200):
                checkpoints[tick] = car.speed * 3.6
            if car.gear != last_gear:
                gear_changes.append((last_gear, car.gear))
                last_gear = car.gear
            assert 800 < car.rpm < 6500
        assert 0.5 < checkpoints[60] < 3
        assert 4 < checkpoints[120] < 12
        assert checkpoints[120] < checkpoints[360] < checkpoints[600] < checkpoints[1200]
        assert checkpoints[1200] > 95
        assert gear_changes[:2] == [(1, 2), (2, 3)]
    finally:
        sim.close()


@pytest.mark.parametrize("speed", [0, 100 / 3.6])
def test_steering_tap_and_reversal_are_continuous(speed):
    response = VehicleResponse()
    positions = []
    for _ in range(120):
        response.pedals_and_steering(Control(steering=1), speed, FIXED_DT)
        positions.append(response.steering)
    # A tenth-second tap must not already be at full lock, even at speed.
    assert positions[11] < positions[-1] * 0.25
    assert 0 < positions[0] < 0.1
    before = response.steering
    response.pedals_and_steering(Control(steering=-1), speed, FIXED_DT)
    assert abs(response.steering - before) < 0.5
    assert response.steering > 0
    for _ in range(240):
        response.pedals_and_steering(Control(), speed, FIXED_DT)
    assert abs(response.steering) < 0.001


def test_light_pedal_is_distinct_from_full_pedal():
    speeds = []
    for pedal in (0.25, 0.5, 1):
        sim = straight_simulation()
        try:
            for _ in range(240):
                sim.step(Control())
            for _ in range(360):
                sim.step(Control(throttle=pedal))
            speeds.append(sim.snapshot().player.speed)
        finally:
            sim.close()
    assert 0 < speeds[0] < speeds[1] < speeds[2]
    assert speeds[2] > speeds[0] * 3


def test_lifting_off_coasts_and_slows_without_stopping_instantly():
    sim = straight_simulation()
    try:
        for _ in range(240):
            sim.step(Control())
        for _ in range(480):
            sim.step(Control(throttle=1))
        before = sim.snapshot().player.speed
        sim.step(Control())
        assert abs(sim.snapshot().player.speed - before) < 0.1
        for _ in range(480):
            sim.step(Control())
        assert 0 < sim.snapshot().player.speed < before - 1
    finally:
        sim.close()


def test_camera_lags_heading_without_changing_the_vehicle():
    camera = ChaseCamera()
    initial = CarState((95, 0, 0.42))
    camera.update(initial, 11, 1 / 60, snap=True)
    turning = CarState((95, 0, 0.42), heading=30)
    camera.update(turning, 11, 1 / 60)
    assert 0 < camera.heading < 5
    assert turning.heading == 30
    for _ in range(120):
        camera.update(turning, 11, 1 / 60)
    assert camera.heading == pytest.approx(30, abs=0.01)
    camera.update(initial, 11, 0, snap=True)
    assert camera.heading == 0
