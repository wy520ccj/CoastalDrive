"""有限控制请求与原生驾驶反馈；曲轴不由目标RPM或挡位切换重设。"""

import math
from dataclasses import replace

import pytest
from panda3d.core import Vec3
from physics.reference_ab import _create_vehicle, _step

from driving_modes import DrivingMode
from powertrain import Powertrain, engine_torque
from vehicle_config import CAR
from vehicle_state import FIXED_DT, VehicleCommand


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("rpm", (-600., 0., 600., 899., 900., 3200., 6500.))
@pytest.mark.parametrize("pedal", (0., .05, .5, .9, 1.))
def test_idle_and_driver_requests_share_available_engine_curve(mode, rpm, pedal):
    config = mode.vehicle_config
    train = Powertrain(config)
    train.rpm = rpm
    train.engine_omega = train.relative_omega = rpm * math.tau / 60
    train.throttle = pedal
    train.prepare(0., 0., pedal, 1, False, FIXED_DT, clutch=1.)
    assert 0 <= train.engine_torque_request <= engine_torque(rpm, config)
    # 受限的是实体主动转矩能力；低速/反转机械轴速与RPM都保持真实状态。
    assert train.rpm == rpm
    assert train.engine_omega == rpm * math.tau / 60


@pytest.mark.parametrize("mode", list(DrivingMode))
def test_native_insufficient_engine_torque_cannot_manufacture_idle_speed(mode):
    config = replace(mode.vehicle_config, torque_curve=((900., 20.), (6500., 20.)))
    world, vehicle = _create_vehicle(config)
    try:
        for _ in range(120):
            _step(world, vehicle, VehicleCommand(gear=0, clutch=0.))
            engine = vehicle.snapshot().powertrain_state
            assert 0 <= engine.engine_torque <= 20
            assert engine.clutch_capacity == engine.drive_torque == 0
        # 可用20Nm不足以克服怠速处24Nm损失；控制器不能凭空保持900RPM。
        assert vehicle.snapshot().rpm < config.idle_rpm
    finally:
        vehicle.close()


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("gear,speed", ((-1, 0.), (-1, -7.), (0, 60.)))
def test_explicit_gear_uses_actual_game_limits_without_direction_signal(mode, gear, speed):
    config = mode.vehicle_config
    train = Powertrain(config)
    train.gear = train.pending_gear = gear
    train.rpm = 2000.
    train.engine_omega = train.relative_omega = train.rpm * math.tau / 60
    train.throttle = 1.
    train.prepare(speed, 0., 1., 0, False, FIXED_DT, gear=gear, clutch=0.)
    if config.game_speed_limits and gear < 0:
        expected = (config.reverse_force * config.wheel_radius
                    / (config.reverse_gear_ratio * config.final_drive * config.drivetrain_efficiency))
        expected *= min(1., max(0., config.reverse_speed-abs(speed)))
    else:
        # 空挡不向道路传递动力；困难模式也没有游戏倒车软限制。
        expected = engine_torque(2000., config)
    assert train.engine_torque_request == pytest.approx(expected, rel=0, abs=1e-10)
    assert train.engine_omega == 2000. * math.tau / 60


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("gear,speed", ((-1, -7.), (1, 60.)))
def test_game_speed_cut_only_reduces_drive_request_and_keeps_idle_losses_supplied(mode, gear, speed):
    config = mode.vehicle_config
    train = Powertrain(config)
    train.gear = train.pending_gear = gear
    train.prepare(speed, 0., 0., 0, True, FIXED_DT, gear=gear, clutch=0.)
    assert train.engine_torque_request == pytest.approx(config.engine_braking, rel=0, abs=1e-10)
    assert train.capacity == 0


@pytest.mark.parametrize("gear,speed", ((-1, -7.), (1, 60.)))
def test_native_game_speed_cut_does_not_starve_unloaded_idle(gear, speed):
    world, vehicle = _create_vehicle(CAR)
    try:
        # 超过游戏驱动限速仅在试验开始设置；自由曲轴仍须以真实怠速请求平衡损失。
        vehicle._chassis.setLinearVelocity(Vec3(0., speed, 0.))
        vehicle.tires.initialize_rolling(speed)
        for _ in range(120):
            _step(world, vehicle, VehicleCommand(gear=gear, clutch=0.))
            assert vehicle.snapshot().rpm > .9 * CAR.idle_rpm
            assert vehicle.powertrain.capacity == 0
    finally:
        vehicle.close()


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("gear,direction", ((-1, 0), (-1, 1), (1, 0), (1, -1)))
def test_explicit_gear_overrides_automatic_direction_for_native_tcs(mode, gear, direction):
    config = replace(mode.vehicle_config, road_friction=.35)
    worlds_and_cars = [_create_vehicle(config) for _ in range(2)]
    active_ticks = 0
    try:
        for world, vehicle in worlds_and_cars:
            for _ in range(240):
                _step(world, vehicle, VehicleCommand(brake=1.))
        for _ in range(120):
            states = []
            for (world, vehicle), selector in zip(worlds_and_cars, (direction, gear)):
                _step(world, vehicle, VehicleCommand(throttle=1., gear=gear, clutch=1., direction=selector))
                states.append(vehicle.snapshot())
            # gear已明确选择传动，自动方向信号不能再改变TCS或真实整车输出。
            assert states[0] == states[1]
            active_ticks += states[0].traction_state.active
        assert active_ticks > 0
    finally:
        for _world, vehicle in worlds_and_cars:
            vehicle.close()


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("direction", (-1, 1))
def test_manual_neutral_does_not_apply_tcs_to_unloaded_engine(mode, direction):
    world, vehicle = _create_vehicle(mode.vehicle_config)
    try:
        for _ in range(240):
            _step(world, vehicle, VehicleCommand(gear=0, clutch=0., brake=1.))
        assert vehicle.snapshot().gear == 0
        # 真空挡落定后只初始化一次残余轮转，不能由自动方向重新制造驱动请求。
        vehicle.tires.initialize_rolling(8.)
        for _ in range(120):
            _step(world, vehicle, VehicleCommand(throttle=1., gear=0, clutch=0., direction=direction))
            state = vehicle.snapshot()
            assert not state.traction_state.active
            assert state.traction_state.torque_scale == 1.
            assert state.traction_state.brake_requests == (0.,) * 4
            assert state.powertrain_state.drive_torque == 0.
    finally:
        vehicle.close()


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("gear", (-1, 1))
def test_automatic_held_gear_uses_actual_direction_for_native_tcs(mode, gear):
    config = replace(mode.vehicle_config, road_friction=.12)
    worlds_and_cars = [_create_vehicle(config) for _ in range(2)]
    active_ticks = 0
    try:
        for world, vehicle in worlds_and_cars:
            for _ in range(240):
                _step(world, vehicle, VehicleCommand(brake=1., gear=gear))
            assert vehicle.powertrain.gear == gear
        for _ in range(120):
            states = []
            for (world, vehicle), selector in zip(worlds_and_cars, (0, gear)):
                _step(world, vehicle, VehicleCommand(throttle=1., direction=selector))
                states.append(vehicle.snapshot())
            # 不请求换挡和再次选择同挡位具有相同机械作用，TCS应读实际传动。
            assert states[0] == states[1]
            active_ticks += states[0].traction_state.active
        assert active_ticks > 0
    finally:
        for _world, vehicle in worlds_and_cars:
            vehicle.close()


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("direction", (-1, 1))
def test_automatic_shift_from_neutral_waits_for_actual_gear_before_tcs(mode, direction):
    config = replace(mode.vehicle_config, road_friction=.12)
    world, vehicle = _create_vehicle(config)
    try:
        for _ in range(240):
            _step(world, vehicle, VehicleCommand(gear=0, brake=1.))
        for _ in range(60):
            _step(world, vehicle, VehicleCommand(gear=0))
        # 仅设置一次试验初态，再采样真实残余轮转；运行中不重设轮速。
        vehicle.tires.initialize_rolling(direction * 8.)
        _step(world, vehicle, VehicleCommand(gear=0))
        assert any(w.sample_support and direction * w.kappa > .2
                   for w in vehicle.snapshot().wheel_dynamics[2:])
        for _ in range(40):
            assert vehicle.powertrain.gear == 0
            _step(world, vehicle, VehicleCommand(throttle=1., direction=direction))
            state = vehicle.snapshot()
            assert not state.traction_state.active
            assert state.traction_state.torque_scale == 1.
            assert state.traction_state.brake_requests == (0.,) * 4
            train = state.powertrain_state
            assert train.clutch_capacity == train.clutch_torque == 0.
            if train.gear == 0:
                pending_ratio = vehicle.powertrain.gear_ratio(train.pending_gear)
                assert train.drive_torque == pytest.approx(pending_ratio * train.synchronizer_torque, abs=1e-9)
            else:
                assert train.drive_torque == pytest.approx(train.ratio * (train.gear_reaction - train.gear_loss_torque), abs=1e-9)
            if state.gear != 0:
                break
        assert state.gear == direction
    finally:
        vehicle.close()


@pytest.mark.parametrize("next_gear", (-1, 0, 2, 4))
def test_shifting_releases_to_zero_before_ratio_change_without_resetting_engine(next_gear):
    # 冻结八维控制器只推进执行器；实体轴同步另由原生共同积分验证。
    train = Powertrain(replace(CAR, input_shaft_enabled=False))
    train.clutch_position = 1.
    train.engine_omega, train.relative_omega, train.rpm = 250., 250., 250. * 60 / math.tau
    previous = train.clutch_position
    changed = False
    for _ in range(40):
        train.prepare(15., 45., .5, 0, False, FIXED_DT, gear=next_gear, clutch=1.)
        assert train.engine_omega == 250.
        assert abs(train.clutch_position - previous) <= FIXED_DT / min(CAR.clutch_release_time, CAR.clutch_engage_time) + 1e-12
        if not changed and train.gear == next_gear:
            assert train.capacity == 0.
            changed = True
        previous = train.clutch_position
    assert changed
    assert train.gear == next_gear
    assert train.clutch_position == 1.


def test_interrupted_forward_reverse_request_uses_latest_direction():
    # 冻结八维控制器只推进执行器；实体轴同步另由原生共同积分验证。
    train = Powertrain(replace(CAR, input_shaft_enabled=False))
    train.clutch_position = 1.
    train.prepare(0., 0., .5, -1, False, FIXED_DT)
    assert train.pending_gear == -1 and train.gear == 1
    for _ in range(30):
        train.prepare(0., 0., .5, 1, False, FIXED_DT)
        assert train.gear == 1
    assert train.pending_gear == 1


@pytest.mark.parametrize("gear", (-2, 6, 1.5))
def test_gear_request_boundary_rejects_nonexistent_ratios(gear):
    train = Powertrain(CAR)
    with pytest.raises(ValueError):
        train.prepare(0., 0., 0., 0, False, FIXED_DT, gear=gear)


def test_redline_cuts_request_without_clamping_true_omega():
    train = Powertrain(CAR)
    train.rpm = 7000.
    train.engine_omega = train.relative_omega = 7000 * math.tau / 60
    train.prepare(0., 0., 1., 0, False, FIXED_DT, gear=0)
    assert train.engine_torque_request == 0.
    assert train.engine_omega == 7000 * math.tau / 60
    assert train.rpm == 7000.


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("compliance", (True, False))
@pytest.mark.parametrize("rotor", (True, False))
def test_native_start_neutral_shift_and_snapshot_report_one_true_engine(mode, compliance, rotor):
    config = replace(mode.vehicle_config, finite_drivetrain=True, tire_compliance=compliance,
                     wheel_rotor_transport=rotor)
    world, vehicle = _create_vehicle(config)
    try:
        for _ in range(60):
            _step(world, vehicle, VehicleCommand(brake=1.))
        for _ in range(180):
            _step(world, vehicle, VehicleCommand(throttle=1., direction=1))
        car = vehicle.snapshot()
        assert car.speed > 3.
        assert car.powertrain_state.clutch_capacity > 0.
        assert car.powertrain_state.engine_omega != car.wheel_dynamics[2].omega * vehicle.powertrain.ratio
        assert car.powertrain_state.clutch_heat >= -1e-7
        assert car.powertrain_state.gear_heat >= -1e-7
        axis = vehicle._chassis.getTransform().getQuat().xform(Vec3(*config.engine_axis))
        relative = vehicle.powertrain.engine_omega - vehicle._chassis.getAngularVelocity().dot(axis)
        assert car.rpm == pytest.approx(relative * 60 / math.tau, abs=1e-10)
        assert car.powertrain_state.engine_relative_omega == relative
        # 保存真正曲轴，空挡请求只能先卸载容量，不能立即重设转速。
        before_gear = car.gear
        for _ in range(30):
            _step(world, vehicle, VehicleCommand(throttle=0., gear=0))
            car = vehicle.snapshot()
            if car.gear != before_gear:
                assert car.powertrain_state.clutch_capacity == 0.
            before_gear = car.gear
        assert car.gear == 0 and car.powertrain_state.drive_torque == 0.
        assert all(w.force_residual < .001 for w in car.wheel_dynamics)
        for i, wheel in enumerate(car.wheel_dynamics):
            share = config.front_brake_share if i < 2 else 1 - config.front_brake_share
            assert wheel.brake_capacity == pytest.approx(
                config.brake_torque * vehicle.brakes.states[i].pressure * share / 2, abs=1e-12)
        engine = car.powertrain_state.engine_omega
        vehicle.shift(100.)
        assert vehicle.powertrain.engine_omega == engine
        vehicle.reset(vehicle.spawn)
        reset = vehicle.snapshot()
        assert reset.powertrain_state.engine_omega == config.idle_rpm * math.tau / 60
        assert reset.powertrain_state.clutch_capacity == 0.
        assert reset.powertrain_state.engine_work == 0.
    finally:
        vehicle.close()
