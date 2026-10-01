"""制动器的有限响应、反馈符号与分轮压力；运动状态只读。"""

import math
from dataclasses import asdict, replace

import pytest

from vehicle_brakes import BrakeConfig, Brakes
from vehicle_state import FIXED_DT, VehicleCommand, WheelDynamicsState

RADIUS = .33


def observed_wheel(speed=20, slip=0, *, supported=True, tick=1):
    return WheelDynamicsState(
        omega=speed * (1 - slip) / RADIUS, longitudinal_speed=speed,
        sample_support=supported, sample_tick=tick,
    )


def test_hydraulic_step_reaches_time_constant_and_releases_independently():
    brakes = Brakes(BrakeConfig(abs_enabled=False))
    wheels = (observed_wheel(),) * 4
    requests = (1, .5, .25, 0)
    for _ in range(3):
        pressures = brakes.advance(requests, wheels, RADIUS, FIXED_DT)
    # 25ms时间常数：三步后为稳态压力的1-exp(-1)，不是瞬时写入请求。
    assert pressures == pytest.approx(tuple(value * (1 - math.exp(-1)) for value in requests))
    before = pressures
    for _ in range(3):
        pressures = brakes.advance((0,) * 4, wheels, RADIUS, FIXED_DT)
    assert pressures == pytest.approx(tuple(value * math.exp(-1) for value in before))
    assert all(state.commanded == 0 for state in brakes.states)


def test_explicit_ideal_actuator_reproduces_instantaneous_legacy_requests():
    brakes = Brakes(BrakeConfig(response_time=0, abs_enabled=False))
    assert brakes.advance((0, .2, .7, 1), (observed_wheel(),) * 4, RADIUS, FIXED_DT) == (0, .2, .7, 1)


@pytest.mark.parametrize("speed", [-20, 20])
def test_abs_reads_completed_sample_and_modulates_only_slipping_wheel(speed):
    brakes = Brakes(BrakeConfig())
    brakes.advance((1,) * 4, (observed_wheel(speed),) * 4, RADIUS, FIXED_DT)
    wheels = (observed_wheel(speed, .4, tick=2),) + (observed_wheel(speed, tick=2),) * 3
    before = tuple(asdict(wheel) for wheel in wheels)
    brakes.advance((1,) * 4, wheels, RADIUS, FIXED_DT)
    assert brakes.states[0].braking_slip == pytest.approx(.4)
    assert brakes.states[0].abs_active and brakes.states[0].phase == "release"
    assert brakes.states[0].commanded < brakes.states[1].commanded == 1
    assert all(state.feedback_tick == 2 for state in brakes.states)
    assert tuple(asdict(wheel) for wheel in wheels) == before


@pytest.mark.parametrize("wheel", [
    observed_wheel(.5, 1), observed_wheel(20, 1, supported=False),
])
def test_low_speed_and_airborne_wheels_exit_abs_without_canceling_brakes(wheel):
    brakes = Brakes(BrakeConfig())
    brakes.advance((1,) * 4, (observed_wheel(),) * 4, RADIUS, FIXED_DT)
    brakes.advance((1,) * 4, (observed_wheel(20, 1),) * 4, RADIUS, FIXED_DT)
    assert all(state.abs_active for state in brakes.states)
    brakes.advance((.7,) * 4, (wheel,) * 4, RADIUS, FIXED_DT)
    assert all(not state.abs_active and state.braking_slip is None for state in brakes.states)
    assert all(state.commanded == .7 and state.pressure > 0 for state in brakes.states)


def test_released_pedal_clears_abs_and_finite_pressure_dissipates():
    brakes = Brakes(BrakeConfig())
    wheels = (observed_wheel(20, .5),) * 4
    brakes.advance((1,) * 4, wheels, RADIUS, FIXED_DT)
    for _ in range(60):
        brakes.advance((0,) * 4, wheels, RADIUS, FIXED_DT)
    assert all(not state.abs_active and state.commanded == 0 for state in brakes.states)
    assert all(0 <= state.pressure < 1e-8 for state in brakes.states)


def test_slip_trend_distinguishes_imminent_lock_from_recovery():
    commands = []
    for previous_slip in (.06, .18):
        brakes = Brakes(BrakeConfig())
        brakes.states = tuple(replace(state, commanded=.6, pressure=.6,
                                      abs_active=True, braking_slip=previous_slip)
                              for state in brakes.states)
        brakes.advance((1,) * 4, (observed_wheel(20, .12),) * 4, RADIUS, FIXED_DT)
        commands.append(brakes.states[0].commanded)
    assert commands[0] < .6 < commands[1]


@pytest.mark.parametrize("requests", [(0, 1), (0, 0, 0, -1), (0, 0, 0, float("nan"))])
def test_invalid_research_wheel_requests_are_rejected_at_command_boundary(requests):
    with pytest.raises(ValueError, match="分轮制动"):
        VehicleCommand(wheel_brakes=requests)
