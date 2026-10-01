"""TCS调节的方向、执行器迟滞与失去支撑的状态语义。"""

from dataclasses import replace

import pytest

from powertrain import Powertrain
from vehicle_state import FIXED_DT, WheelDynamicsState
from vehicle_traction import TractionConfig, TractionControl


def wheels(speed=10, slip=0.0, direction=1, support=True):
    return tuple(WheelDynamicsState(
        omega=direction * speed * (1 + slip) / .33,
        longitudinal_speed=direction * speed, sample_support=support, sample_tick=12,
    ) for _ in range(4))


@pytest.mark.parametrize("direction", [-1, 1])
def test_drive_slip_reduces_requested_torque_in_both_directions(direction):
    control = TractionControl(TractionConfig())
    state = control.advance(1, direction, False, wheels(slip=.6, direction=direction), .33, FIXED_DT)
    assert state.active and state.torque_scale < 1
    assert state.wheel_slips[2] == pytest.approx(.6)
    assert state.brake_requests[:2] == (0, 0)
    assert state.brake_requests[2] > 0
    assert state.feedback_ticks == (12,) * 4


def test_single_driven_wheel_can_request_braking_without_front_intervention():
    sample = list(wheels())
    sample[3] = replace(sample[3], omega=60)
    control = TractionControl(TractionConfig())
    state = control.advance(1, 1, False, sample, .33, FIXED_DT)
    assert state.brake_requests[:3] == (0, 0, 0)
    assert state.brake_requests[3] > 0


@pytest.mark.parametrize("pedal,direction,braking,support", [(0, 1, False, True),
    (1, 1, True, True), (1, 0, False, True), (1, 1, False, False)])
def test_release_braking_neutral_or_airborne_clears_controller_request(pedal, direction, braking, support):
    control = TractionControl(TractionConfig())
    control.advance(1, 1, False, wheels(slip=.8), .33, FIXED_DT)
    state = control.advance(pedal, direction, braking, wheels(slip=.8, support=support), .33, FIXED_DT)
    assert not state.active and state.torque_scale == 1
    assert state.brake_requests == (0, 0, 0, 0)


def test_disabled_controller_preserves_full_mechanical_request():
    control = TractionControl(TractionConfig(tcs_enabled=False))
    for _ in range(120):
        state = control.advance(1, 1, False, wheels(slip=2), .33, FIXED_DT)
        assert state.torque_scale == 1 and not state.active
        assert state.brake_requests == (0, 0, 0, 0)


def test_low_speed_regularization_stays_finite_and_recovery_is_finite():
    control = TractionControl(TractionConfig())
    sample = tuple(replace(wheel, omega=4, longitudinal_speed=0) for wheel in wheels())
    state = control.advance(1, 1, False, sample, .33, FIXED_DT)
    assert state.wheel_slips[2] == pytest.approx(1.32)
    reduced = state.torque_scale
    # 趋势消失后调节仍通过有限恢复率。
    control.advance(1, 1, False, wheels(), .33, FIXED_DT)
    recovered = control.advance(1, 1, False, wheels(), .33, FIXED_DT)
    assert recovered.torque_scale <= reduced + 2 * control.config.apply_rate * FIXED_DT


def test_engine_cut_acts_on_target_before_finite_torque_response():
    engine = Powertrain()
    for _ in range(120):
        engine.advance(5, 30, 1, 1, False, FIXED_DT)
    initial = engine.drive_torque
    actual, drag = engine.advance(5, 30, 1, 1, False, FIXED_DT, drive_scale=0)
    assert 0 < actual < initial and drag == 0
    # TCS削矩不通过闭油门参数制造发动机制动。
    engine.advance(5, 30, 1, 1, True, FIXED_DT, drive_scale=.1)
    assert engine.drive_torque == 0
