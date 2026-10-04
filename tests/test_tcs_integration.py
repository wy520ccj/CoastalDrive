"""真实轮端转矩、制动压力与TCS采样反馈，不以标志代替机械效果。"""

import math
from dataclasses import replace
from itertools import pairwise

import pytest
from physics.reference_ab import _create_vehicle, _step
from physics.tcs_probe import run_trial

from driving_modes import REFERENCE_CAR
from simulation import Snapshot, interpolate
from vehicle_state import FIXED_DT, VehicleCommand


@pytest.mark.parametrize("case", ["low-mu", "split-mu"])
@pytest.mark.parametrize("input_shaft_enabled", [False, True])
def test_tcs_reduces_real_excess_drive_slip_with_actual_actuators(case, input_shaft_enabled):
    baseline, _ = run_trial(case, False, duration=3, input_shaft_enabled=input_shaft_enabled)
    candidate, rows = run_trial(case, True, duration=3, input_shaft_enabled=input_shaft_enabled)
    assert sum(candidate["supported_excess_slip_integral_s"][2:]) < sum(
        baseline["supported_excess_slip_integral_s"][2:])
    assert any(row["state.traction_state.torque_scale"] < .9 for row in rows)
    # 均匀路面的左右轮也可能因真实车身响应分化，验证实际受控驱动轮。
    braking_wheels = (3,) if case == "split-mu" else (2, 3)
    assert any(row[f"state.brake_states.{i}.pressure"] > 0
               and abs(row[f"state.wheel_dynamics.{i}.brake_torque"]) > 0
               for row in rows for i in braking_wheels)
    if not input_shaft_enabled and case == "low-mu":
        assert any(row["state.brake_states.2.pressure"] > 0 for row in rows)
    if case == "split-mu":
        assert all(row["state.brake_states.2.pressure"] == 0 for row in rows)
    assert any(abs(row["state.wheel_dynamics.2.fx"]) > 0 for row in rows)
    for row in rows[1:]:
        assert row["state.traction_state.feedback_ticks.2"] == row["tick"] + 239
        assert row["state.brake_states.2.feedback_tick"] == row["tick"] + 239
    assert candidate["tcs_active_seconds"] > 0


def test_disabled_controller_and_releasing_driver_requests_reach_actuators():
    for enabled in (False, True):
        _, rows = run_trial("driver-brake", enabled, duration=3)
        for previous, row in pairwise(rows[240:]):
            assert row["state.throttle"] == row["command.throttle"] == 1
            assert row["state.brake"] == row["command.brake"] == 1
            assert not row["state.traction_state.active"]
            assert row["state.traction_state.torque_scale"] == 1
            capacity = row["state.powertrain_state.clutch_capacity"]
            expected = max(0., previous["state.powertrain_state.clutch_capacity"]
                           - REFERENCE_CAR.clutch_capacity * FIXED_DT / REFERENCE_CAR.clutch_release_time)
            assert capacity == pytest.approx(expected, rel=0, abs=1e-11)
            ratio = row["state.powertrain_state.ratio"]
            torque = row["state.wheel_dynamics.2.drive_torque"]
            clutch = row["state.powertrain_state.clutch_torque"]
            assert abs(clutch) <= capacity + 1e-11
            gear = row["state.powertrain_state.gear_reaction"]
            loss = row["state.powertrain_state.gear_loss_torque"]
            assert row["state.powertrain_state.drive_torque"] == pytest.approx(ratio * (gear - loss), abs=1e-9)
            assert torque == pytest.approx(ratio * (gear - loss) / 2, abs=1e-9)
            if capacity == 0:
                assert clutch == 0
        release_ticks = math.ceil(REFERENCE_CAR.clutch_release_time / FIXED_DT)
        assert rows[240 + release_ticks]["state.powertrain_state.clutch_capacity"] == 0
        if not enabled:
            assert all(row["state.traction_state.torque_scale"] == 1 for row in rows)
    _, rows = run_trial("lift-off", True, duration=3)
    assert all(not row["state.traction_state.active"] for row in rows[241:])
    assert rows[-1]["state.brake_states.2.pressure"] < 1e-12


def test_actual_tcs_interpolation_reset_and_origin_shift():
    config = replace(REFERENCE_CAR, road_friction=.3)
    world, car = _create_vehicle(config)
    try:
        for _ in range(240):
            _step(world, car, VehicleCommand())
        for tick in range(120):
            before = car.snapshot()
            _step(world, car, VehicleCommand(throttle=1, direction=1))
            current = car.snapshot()
            if current.traction_state.active:
                break
        else:
            pytest.fail("真实低附着起步未产生TCS反馈")
        render = interpolate(Snapshot(tick, tick/120, before, ()),
                             Snapshot(tick+1, (tick+1)/120, current, ()), .5)
        assert render.player.tcs_enabled
        assert render.player.traction_state == current.traction_state
        assert render.player.brake_states == current.brake_states
        car.shift(100)
        assert car.traction.state == current.traction_state
        car.reset((0, 0, .55))
        assert not car.traction.state.active and car.traction.state.torque_scale == 1
        assert car.traction.state.feedback_ticks == (0, 0, 0, 0)
    finally:
        car.close()
