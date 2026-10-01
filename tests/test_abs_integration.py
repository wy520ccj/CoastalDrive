"""真实Bullet制动集成：验证锁止恢复与单轮压力的机械影响。"""

import pytest
from panda3d.core import Vec3
from physics.abs_probe import run_trial
from physics.reference_ab import _create_vehicle, _step

from driving_modes import REFERENCE_CAR
from simulation import Snapshot, interpolate
from vehicle_state import VehicleCommand


@pytest.mark.parametrize("case", ["asphalt", "low-mu", "split-mu"])
def test_abs_reduces_observed_wheel_lock(case):
    baseline, _ = run_trial(case, False)
    candidate, rows = run_trial(case, True)
    assert sum(baseline["locked_wheel_seconds"]) > 0
    assert sum(candidate["locked_wheel_seconds"]) < sum(baseline["locked_wheel_seconds"])
    assert rows[0]["horizontal_speed_mps"] == pytest.approx(100 / 3.6)
    assert any(row["state.brake_states.2.phase"] == "release" for row in rows[1:])
    assert any(abs(row["state.wheel_dynamics.2.fx"]) > 0 for row in rows[1:])
    assert candidate["final_horizontal_speed_mps"] < baseline["initial_speed_mps"]
    if case == "low-mu":
        # 当前光滑MF低附着模型中，恢复滚动应比持续抱死更充分利用纵向附着。
        assert baseline["stopped"] and candidate["stopped"]
        assert candidate["path_distance_m"] < baseline["path_distance_m"]


def test_independent_requests_reach_physical_brake_torque():
    _, rows = run_trial("asphalt", False, duration=.5, wheel_brakes=(0, .5, 1, .25))
    state = rows[-1]
    pressures = [state[f"state.brake_states.{i}.pressure"] for i in range(4)]
    assert pressures[2] > pressures[1] > pressures[3] > pressures[0] == 0
    # 后轴另有发动机制动，零请求用前轮验证机械转矩。
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
        for _ in range(24):
            _step(world, car, VehicleCommand(brake=1))
        state = car.snapshot()
        assert all(not brake.abs_active and brake.pressure > 0 for brake in state.brake_states)
        assert all(not wheel.sample_support and wheel.fx == wheel.fy == 0
                   for wheel in state.wheel_dynamics)
        assert all(abs(wheel.relative_omega) < initial for wheel in state.wheel_dynamics)
        body = car._chassis
        body_omega = body.getAngularVelocity().dot(body.getTransform().getQuat().getRight())
        inertia = body.getInertia().x
        wheel_inertia = car.config.wheel_inertia
        before_energy = .5 * wheel_inertia * 4 * initial ** 2
        after_energy = .5 * inertia * body_omega ** 2 + .5 * wheel_inertia * sum(
            wheel.omega ** 2 for wheel in state.wheel_dynamics
        )
        assert after_energy < before_energy
        # 空中制动是内部反力矩；能量耗散而车轮/车身总轴向角动量守恒。
        after_momentum = inertia * body_omega - wheel_inertia * sum(
            wheel.omega for wheel in state.wheel_dynamics
        )
        assert after_momentum == pytest.approx(-wheel_inertia * 4 * initial, abs=1e-3)
    finally:
        car.close()
