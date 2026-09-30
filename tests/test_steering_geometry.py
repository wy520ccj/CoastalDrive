"""左右前轮共同瞬时转动中心与真实Bullet转向方向。"""

import math

import pytest

from simulation import Simulation
from test_track import TEST_SPAWN
from vehicle_config import CAR
from vehicle_state import VehicleCommand
from vehicle_steering import wheel_angles


@pytest.mark.parametrize("angle", [-26, -20, -5, 5, 20, 26])
def test_front_wheel_axes_meet_on_same_rear_axle_center(angle):
    left, right = wheel_angles(angle)
    left_radius = CAR.wheelbase / math.tan(math.radians(left)) - CAR.track_width / 2
    right_radius = CAR.wheelbase / math.tan(math.radians(right)) + CAR.track_width / 2
    expected = CAR.wheelbase / math.tan(math.radians(angle))
    assert left_radius == pytest.approx(expected)
    assert right_radius == pytest.approx(expected)
    inner, outer = (right, left) if angle > 0 else (left, right)
    assert abs(inner) > abs(angle) > abs(outer)
    assert wheel_angles(-angle) == pytest.approx((-right, -left))


def test_straight_wheels_are_parallel():
    assert wheel_angles(0) == (0, 0)


@pytest.mark.parametrize("direction", [-1, 1])
def test_right_steering_turns_forward_right_and_reverse_left(direction):
    sim = Simulation(track="test")
    try:
        sim.reset_player(TEST_SPAWN)
        for _ in range(240):
            sim.step(VehicleCommand())
        for _ in range(360):
            sim.step(VehicleCommand(throttle=.3, steering=15, direction=direction))
        car = sim.snapshot().player
        assert car.speed * direction > 1
        assert car.dynamics.yaw_rate * direction < 0
        assert car.heading * direction < 0
        assert -sim._vehicle.getSteeringValue(1) > -sim._vehicle.getSteeringValue(0) > 0
        assert abs(car.roll) < 5
    finally:
        sim.close()
