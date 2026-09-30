"""研究请求绕过输入辅助，仍受同一执行器、轮胎和固定步约束。"""

import pytest

from driver_assist import steering_limit
from simulation import Simulation
from test_track import TEST_SPAWN
from vehicle_config import CAR
from vehicle_state import FIXED_DT, Control, VehicleCommand


@pytest.fixture
def sim():
    simulation = Simulation(track="test")
    simulation.reset_player(TEST_SPAWN)
    for _ in range(240):
        simulation.step(Control())
    yield simulation
    simulation.close()


def test_direct_throttle_bypasses_keyboard_ramp_but_keeps_torque_response(sim):
    sim.step(VehicleCommand(throttle=1, direction=1))
    assert sim.snapshot().player.throttle == 1
    assert sim.player.assist.throttle == 0
    assert 0 < sim.player.powertrain.drive_torque < 1000 * .33
    assert 0 < sim.snapshot().player.speed < .1


def test_direct_steering_bypasses_speed_envelope_but_keeps_rack_motion(sim):
    sim._chassis.setLinearVelocity(sim._chassis.getTransform().getQuat().getForward() * 100 / 3.6)
    previous = 0
    for _ in range(180):
        sim.step(VehicleCommand(steering=90))
        angle = sim.snapshot().player.steering
        assert abs(angle - previous) <= CAR.steering_rate * FIXED_DT + 1e-12
        assert 0 <= angle <= CAR.steering_degrees
        previous = angle
    assert angle > 20
    assert steering_limit(100 / 3.6) < 2


def test_explicit_brake_does_not_turn_into_reverse_throttle(sim):
    for _ in range(120):
        sim.step(VehicleCommand(brake=1))
    car = sim.snapshot().player
    assert car.throttle == 0
    assert car.brake == 1
    assert car.gear == 1
    assert abs(car.speed) < .05
    assert sim.player.assist.reverse_wait == 0


def test_direct_reverse_requests_real_reverse_gear_and_resets_all_actuators(sim):
    for _ in range(120):
        sim.step(VehicleCommand(throttle=1, direction=-1, steering=10))
    car = sim.snapshot().player
    assert car.gear == -1
    assert car.speed < -1
    assert car.steering > 0
    sim.reset_player(TEST_SPAWN)
    car = sim.snapshot().player
    assert car.steering == car.throttle == car.brake == car.speed == 0
    assert car.gear == 1
    assert sim.player.powertrain.drive_torque == 0
