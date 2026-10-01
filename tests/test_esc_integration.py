"""真实执行器与轮胎接点力的ESC集成，含状态生命周期。"""

import pytest
from panda3d.core import Vec3
from physics.esc_probe import run_trial
from physics.reference_ab import _create_vehicle, _step

from driving_modes import REFERENCE_CAR
from simulation import Snapshot, interpolate
from vehicle_state import VehicleCommand


def test_split_mu_stability_changes_real_pressures_and_reduces_yaw():
    baseline, _ = run_trial("split-mu-brake", False, duration=3)
    candidate, rows = run_trial("split-mu-brake", True, duration=3)
    assert candidate["abs_yaw_error_integral_rad"] < baseline["abs_yaw_error_integral_rad"] * .5
    assert candidate["abs_sideslip_integral_rad_s"] < baseline["abs_sideslip_integral_rad_s"] * .5
    assert any(row["state.stability_state.brake_requests.0"] < .9 for row in rows[1:])
    assert any(row["state.brake_states.0.pressure"] < .9 for row in rows[60:])
    assert any(abs(row["state.wheel_dynamics.0.fx"]) > 100 for row in rows)
    assert any(row["state.stability_state.active"] for row in rows)


def test_coast_correction_uses_right_wheel_contact_force_and_preserves_memory_until_reset():
    world, car = _create_vehicle(REFERENCE_CAR)
    try:
        for _ in range(240):
            _step(world, car, VehicleCommand())
        car._chassis.setLinearVelocity(Vec3(0, 20, 0))
        car._chassis.setAngularVelocity(Vec3(0, 0, .5))
        car.tires.initialize_rolling(20)
        for tick in range(30):
            before = car.snapshot()
            _step(world, car, VehicleCommand())
            current = car.snapshot()
            right = current.wheel_dynamics[1]
            if car.stability.state.active and right.brake_torque > 100 and right.fx < -100:
                break
        else:
            pytest.fail("滑行横摆工况未通过右前轮接点制动力纠偏")
        assert current.stability_state.allocated_brake_moment < 0
        assert current.stability_state.desired_brake_moment < 0
        assert current.brake_states[1].pressure > 0
        assert current.stability_state.feedback_tick == current.wheel_dynamics[0].sample_tick - 1
        render = interpolate(Snapshot(tick, tick/120, before, ()),
                             Snapshot(tick+1, (tick+1)/120, current, ()), .5)
        assert render.player.esc_enabled
        assert render.player.stability_state == current.stability_state
        memory = current.stability_state
        car.shift(100)
        assert car.stability.state == memory
        car.reset((0, 0, .55))
        assert not car.stability.state.active
        assert car.stability.state.feedback_tick == 0
        assert car.stability.state.reference_yaw_rate == 0
    finally:
        car.close()
