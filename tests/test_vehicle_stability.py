"""横摆制动力矩分配的几何符号、可达边界与真值反馈。"""

from dataclasses import replace

import pytest
from panda3d.bullet import BulletRigidBodyNode
from panda3d.core import Vec3

from driving_modes import REFERENCE_CAR
from vehicle_stability import StabilityControl, allocate_brakes
from vehicle_state import FIXED_DT, WheelContactState, WheelDynamicsState


@pytest.mark.parametrize("prefer_rear", [False, True])
@pytest.mark.parametrize("target", [-5000, -800, 0, 800, 5000])
def test_allocation_reaches_target_or_physical_saturation(target, prefer_rear):
    limits = (1000, 700, 800, 600)
    arms = (1, -1, 1, -1)
    base = (900, 700, 700, 500)
    forces = allocate_brakes(base, limits, arms, target, prefer_rear)
    assert all(0 <= force <= limit for force, limit in zip(forces, limits))
    moment = sum(force * arm for force, arm in zip(forces, arms))
    assert moment == pytest.approx(max(-1300, min(1800, target)))


def test_full_pedal_correction_can_release_opposing_brakes():
    forces = allocate_brakes((1000,) * 4, (1000,) * 4, (1, -1, 1, -1), 700, False)
    assert forces[0] == forces[2] == forces[3] == 1000
    assert forces[1] == 300


@pytest.mark.parametrize("prefer_rear,index", [(False, 0), (True, 2)])
def test_front_or_rear_selection_adds_real_positive_yaw_moment(prefer_rear, index):
    forces = allocate_brakes((0,) * 4, (1000,) * 4, (1, -1, 1, -1), 700, prefer_rear)
    assert forces[index] == 700
    assert sum(forces) == 700


def feedback(speed=20, yaw=0, side_speed=0, support=True, mu=1.1):
    config = replace(REFERENCE_CAR, road_friction=mu)
    body = BulletRigidBodyNode("stability-test")
    body.setMass(config.mass)
    body.setInertia(Vec3(*config.body_inertia))
    body.setLinearVelocity(Vec3(side_speed, speed, 0))
    body.setAngularVelocity(Vec3(0, 0, yaw))
    wheels = tuple(WheelDynamicsState(longitudinal_speed=speed, sample_support=support,
                                      sample_tick=47) for _ in range(4))
    contacts = tuple(WheelContactState(support, (x, y, 0), (0, 0, 1), 0, 3000,
                                      0, 0, None, "asphalt")
                     for x, y in ((-1, 1), (1, 1), (-1, -1), (1, -1)))
    return config, body, wheels, contacts


@pytest.mark.parametrize("speed", [-20, 20])
def test_steering_reference_and_brake_geometry_reverse_consistently(speed):
    config, body, wheels, contacts = feedback(speed=speed)
    control = StabilityControl(config)
    state = control.advance(body, wheels, contacts, (0,) * 4, 10, FIXED_DT)
    assert state.unlimited_yaw_rate * speed < 0
    # 前进右转的制动力矩为负；倒车右转为正，均选择右侧制动。
    for _ in range(100):
        state = control.advance(body, wheels, contacts, (0,) * 4, 10, FIXED_DT)
    assert state.active and state.brake_requests[3] > 0
    assert state.allocated_brake_moment * speed < 0
    assert state.feedback_tick == 47


@pytest.mark.parametrize("speed", [-20, 20])
def test_coasting_sideslip_correction_depends_on_travel_direction(speed):
    config, body, wheels, contacts = feedback(speed=speed, side_speed=5)
    state = StabilityControl(config).advance(body, wheels, contacts, (0,) * 4, 0, FIXED_DT)
    assert state.active
    assert state.desired_brake_moment * speed < 0
    assert state.allocated_brake_moment * speed < 0


@pytest.mark.parametrize("speed,support", [(0.2, True), (20, False)])
def test_low_speed_and_airborne_do_not_create_electronic_requests(speed, support):
    config, body, wheels, contacts = feedback(speed=speed, yaw=2, support=support)
    requests = (.7,) * 4
    state = StabilityControl(config).advance(body, wheels, contacts, requests, 10, FIXED_DT)
    assert state.brake_requests == requests and state.torque_scale == 1
    assert not state.active


def test_disabled_esc_keeps_incoming_pressure_and_drive_request():
    config, body, wheels, contacts = feedback(yaw=2)
    config = replace(config, stability=replace(config.stability, esc_enabled=False))
    requests = (.4, .9, .7, .6)
    state = StabilityControl(config).advance(body, wheels, contacts, requests, 10, FIXED_DT)
    assert state.brake_requests == requests and state.torque_scale == 1
    assert not state.active


def test_reference_uses_tire_grip_not_brake_hardware_capacity():
    config, body, wheels, contacts = feedback(mu=1.1)
    weak_brakes = replace(config, brake_torque=10)
    outputs = []
    for vehicle in (config, weak_brakes):
        control = StabilityControl(vehicle)
        for _ in range(240):
            state = control.advance(body, wheels, contacts, (0,) * 4, 20, FIXED_DT)
        outputs.append(state.reference_yaw_rate)
    assert outputs[0] == pytest.approx(outputs[1])
    capacity = 13200 * (3000 / (config.mass * 9.81 / 4)) ** (config.tire_peak_load_exponent - 1)
    assert abs(outputs[0]) == pytest.approx(capacity / (config.mass * 20), rel=1e-5)
