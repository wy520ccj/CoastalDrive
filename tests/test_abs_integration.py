"""真实Bullet制动集成：验证锁止恢复与单轮压力的机械影响。"""

import math
from dataclasses import replace

import pytest
from panda3d.core import Vec3
from physics.abs_probe import run_trial
from physics.reference_ab import _create_vehicle, _step

from driveline_inertia import active_inertias
from driving_modes import REFERENCE_CAR
from simulation import Snapshot, interpolate
from vehicle_state import VehicleCommand
from wheel_geometry import mechanical_axis


def rotational_account(car):
    """世界坐标下车身、四轮、曲轴与实体传动轴的完整转动账。"""
    body, config = car._chassis, car.config
    orientation = body.getTransform().getQuat()
    basis = (orientation.getRight(), orientation.getForward(), orientation.getUp())
    angular, inertia = body.getAngularVelocity(), body.getInertia()
    local = tuple(sum(angular[a] * axis[a] for a in range(3)) for axis in basis)
    momentum = [sum(inertia[i] * local[i] * basis[i][a] for i in range(3))
                for a in range(3)]
    energy = .5 * sum(inertia[i] * local[i]**2 for i in range(3))
    rotors = [(config.wheel_inertia, omega, tuple(-a for a in mechanical_axis(
        basis[0], basis[1], state.steering)))
        for omega, state in zip(car.tires.omega, car.tires.states)]
    train = car.powertrain
    rotors.extend((j, omega, tuple(orientation.xform(Vec3(*axis))))
                  for j, omega, axis in (
                      (config.engine_inertia, train.engine_omega, config.engine_axis),
                      (config.input_shaft_inertia, train.shaft_omega, config.input_shaft_axis),
                      *zip(active_inertias(config.downstream_inertias, config.front_drive_share),
                           train.downstream_omega, config.downstream_axes)))
    for j, omega, axis in rotors:
        energy += .5 * j * omega**2
        for a in range(3):
            momentum[a] += j * omega * axis[a]
    return tuple(momentum), energy


@pytest.mark.parametrize("case,brake_multiplier", [
    pytest.param("asphalt", 1, id="asphalt"),
    pytest.param("asphalt", 1.5, id="asphalt-strong-brake"),
    pytest.param("low-mu", 1, id="low-mu"),
    pytest.param("split-mu", 1, id="split-mu"),
])
def test_abs_reduces_observed_wheel_lock(case, brake_multiplier):
    config = replace(REFERENCE_CAR, brake_torque=REFERENCE_CAR.brake_torque * brake_multiplier)
    baseline, baseline_rows = run_trial(case, False, vehicle_config=config)
    candidate, rows = run_trial(case, True, vehicle_config=config)
    if case == "asphalt" and brake_multiplier == 1:
        # 默认柏油制动未达到ABS介入门槛；开关不应改变机械轨迹或强制减压。
        assert sum(baseline["locked_wheel_seconds"]) == sum(candidate["locked_wheel_seconds"]) == 0
        assert all(row[f"state.brake_states.{index}.phase"] == "normal"
                   for row in rows[1:] for index in range(4))
        assert [{k: v for k, v in row.items() if k != "state.abs_enabled"}
                for row in rows] == [
                    {k: v for k, v in row.items() if k != "state.abs_enabled"}
                    for row in baseline_rows]
    else:
        assert sum(baseline["locked_wheel_seconds"]) > 0
        assert sum(candidate["locked_wheel_seconds"]) < sum(baseline["locked_wheel_seconds"])
        assert any(row["state.brake_states.2.phase"] == "release" for row in rows[1:])
    assert rows[0]["horizontal_speed_mps"] == pytest.approx(100 / 3.6)
    assert any(abs(row["state.wheel_dynamics.2.fx"]) > 0 for row in rows[1:])
    assert candidate["final_horizontal_speed_mps"] < baseline["initial_speed_mps"]
    if case == "low-mu" or brake_multiplier > 1:
        # 附着受限时，恢复滚动应比持续抱死更充分利用纵向附着。
        assert baseline["stopped"] and candidate["stopped"]
        assert candidate["path_distance_m"] < baseline["path_distance_m"]


def test_independent_requests_reach_physical_brake_torque():
    _, rows = run_trial("asphalt", False, duration=.5, wheel_brakes=(0, .5, 1, .25))
    state = rows[-1]
    pressures = [state[f"state.brake_states.{i}.pressure"] for i in range(4)]
    assert pressures[2] > pressures[1] > pressures[3] > pressures[0] == 0
    # 零请求轮没有制动容量；其它轮独立压力仍生成真实机械转矩。
    assert state["state.wheel_dynamics.0.brake_capacity"] == 0
    assert state["state.wheel_dynamics.0.brake_torque"] == 0
    assert abs(state["state.wheel_dynamics.2.brake_torque"]) > 0
    assert abs(state["state.wheel_dynamics.1.brake_torque"]) > 0
    assert state["state.wheel_dynamics.0.omega"] != state["state.wheel_dynamics.2.omega"]


def test_render_interpolation_preserves_latest_physical_abs_feedback():
    world, car = _create_vehicle(REFERENCE_CAR)
    try:
        for _ in range(240):
            _step(world, car, VehicleCommand())
        car._chassis.setLinearVelocity(Vec3(0, 100 / 3.6, 0))
        car.tires.initialize_rolling(100 / 3.6)
        for tick in range(120):
            before = car.snapshot()
            _step(world, car, VehicleCommand(brake=1))
            current = car.snapshot()
            if any(brake.abs_active for brake in current.brake_states):
                break
        else:
            pytest.fail("真实制动未产生ABS反馈")
        previous_snapshot = Snapshot(tick, tick / 120, before, ())
        current_snapshot = Snapshot(tick + 1, (tick + 1) / 120, current, ())
        for alpha in (0, .5, 1):
            render = interpolate(previous_snapshot, current_snapshot, alpha)
            assert render.player.abs_enabled
            assert render.player.brake_states == current.brake_states
            assert any(brake.abs_active for brake in render.player.brake_states)
    finally:
        car.close()


def test_airborne_brakes_slow_real_wheels_without_ground_force_or_abs():
    world, car = _create_vehicle(REFERENCE_CAR)
    try:
        car.reset((0, 0, 20))
        car._chassis.setLinearVelocity(Vec3(0, 20, 0))
        car.tires.initialize_rolling(20)
        initial = 20 / car.config.wheel_radius
        before_momentum, before_energy = rotational_account(car)
        for _ in range(24):
            _step(world, car, VehicleCommand(brake=1))
        state = car.snapshot()
        assert all(not brake.abs_active and brake.pressure > 0 for brake in state.brake_states)
        assert all(not wheel.sample_support and wheel.fx == wheel.fy == 0
                   for wheel in state.wheel_dynamics)
        assert all(abs(wheel.relative_omega) < initial for wheel in state.wheel_dynamics)
        after_momentum, after_energy = rotational_account(car)
        assert after_energy < before_energy
        # 制动为内部转矩；计入轴储能/壳体反力后，完整世界向量保持原门槛。
        assert math.dist(after_momentum, before_momentum) < 1e-3
    finally:
        car.close()
