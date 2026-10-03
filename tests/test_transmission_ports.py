"""传动端口：独立区间消元对照、定向模式覆盖和耗散符号。"""

import itertools
import random

import pytest

from transmission_ports import clutch_brake_plans, clutch_brake_state, transmission_state

RESPONSE = ((7., -2., .4), (-2., 4., -.7), (.4, -.7, 1.5))


def loss_bounds(clutch, efficiency):
    bounds = ((1 - efficiency) * clutch, (1 - 1 / efficiency) * clutch)
    return min(bounds), max(bounds)


def root(function, low, high):
    for _ in range(80):
        middle = (low + high) / 2
        if function(middle) > 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def independent_nested(free, response, dt, capacity, brake_capacity, efficiency):
    """直接消元单轮制动，再对损失/离合分别作有界单调求根。"""
    def brake(clutch, loss):
        demand = (free[2] / dt - response[2][0] * clutch - response[2][1] * loss) / response[2][2]
        return max(-brake_capacity, min(brake_capacity, demand))

    def gear(clutch):
        low, high = loss_bounds(clutch, efficiency)

        def speed(loss):
            return free[1] - dt * (response[1][0] * clutch + response[1][1] * loss
                                   + response[1][2] * brake(clutch, loss))

        if speed(low) <= 0:
            loss = low
        elif speed(high) >= 0:
            loss = high
        else:
            loss = root(speed, low, high)
        used_brake = brake(clutch, loss)
        slip = free[0] - dt * (response[0][0] * clutch + response[0][1] * loss
                               + response[0][2] * used_brake)
        return slip, loss, used_brake

    if gear(-capacity)[0] <= 0:
        clutch = -capacity
    elif gear(capacity)[0] >= 0:
        clutch = capacity
    else:
        clutch = root(lambda value: gear(value)[0], -capacity, capacity)
    _slip, loss, used_brake = gear(clutch)
    return clutch, loss, used_brake


@pytest.mark.parametrize("clutch_mode,gear_mode,brake_mode", itertools.product((-1, 0, 1), repeat=3))
@pytest.mark.parametrize("efficiency", (.88, 1.))
@pytest.mark.parametrize("dt", (1 / 240, 1 / 960))
@pytest.mark.parametrize("sign", (-1, 1))
def test_three_ports_recover_all_directed_physical_modes(clutch_mode, gear_mode, brake_mode, efficiency, dt, sign):
    clutch = clutch_mode * 300. if clutch_mode else sign * 120.
    slip = clutch_mode * 40.
    speed = gear_mode * 40.
    low, high = loss_bounds(clutch, efficiency)
    loss = high if gear_mode > 0 else low if gear_mode < 0 else (low + high) / 2
    brake = brake_mode * 600. if brake_mode else sign * 60.
    wheel_speed = brake_mode * 40.
    expected = clutch, loss, brake
    end = slip, speed, wheel_speed
    free = tuple(end[i] + dt * sum(RESPONSE[i][j] * expected[j] for j in range(3)) for i in range(3))
    plans = clutch_brake_plans(RESPONSE, 300., 600., efficiency)
    value, speeds, index = clutch_brake_state(free, RESPONSE, dt, 300., 600., efficiency, plans)
    assert value == pytest.approx(expected, abs=1e-10)
    assert speeds == pytest.approx(end, abs=1e-11)
    assert value == pytest.approx(independent_nested(free, RESPONSE, dt, 300., 600., efficiency), abs=1e-10)
    assert clutch * speeds[0] >= -1e-9
    assert loss * speeds[1] >= -1e-9
    assert brake * speeds[2] >= -1e-9
    # 预热正确/错误模式都必须重新检查真实互补条件。
    for warm in (index, (index + 11) % len(plans)):
        warmed, warmed_speeds, _index = clutch_brake_state(free, RESPONSE, dt, 300., 600., efficiency, plans, warm)
        assert warmed == pytest.approx(value, abs=1e-10)
        assert warmed_speeds == pytest.approx(speeds, abs=1e-11)


@pytest.mark.parametrize("capacity,brake_capacity", ((0., 0.), (0., 600.), (300., 0.), (300., 600.)))
@pytest.mark.parametrize("efficiency", (.88, 1.))
def test_three_ports_random_free_speeds_and_zero_capacities(capacity, brake_capacity, efficiency):
    rng = random.Random(20261003)
    plans = clutch_brake_plans(RESPONSE, capacity, brake_capacity, efficiency)
    for _ in range(24):
        free = tuple(rng.uniform(-15., 15.) for _ in range(3))
        value, speeds, _index = clutch_brake_state(free, RESPONSE, 1 / 240, capacity, brake_capacity, efficiency, plans)
        expected = independent_nested(free, RESPONSE, 1 / 240, capacity, brake_capacity, efficiency)
        assert value == pytest.approx(expected, abs=1e-10)
        assert all(torque * speed >= -1e-9 for torque, speed in zip(value, speeds))


@pytest.mark.parametrize("capacity", (0., 50., 300.))
@pytest.mark.parametrize("efficiency", (.88, 1.))
def test_two_ports_match_independent_elimination(capacity, efficiency):
    response = ((7., -2.), (-2., 4.))
    uncoupled_brake = ((7., -2., 0.), (-2., 4., 0.), (0., 0., 1.))
    rng = random.Random(20261004)
    for _ in range(40):
        free = tuple(rng.uniform(-15., 15.) for _ in range(2))
        value, speeds = transmission_state(free, response, 1 / 240, capacity, efficiency)
        expected = independent_nested(free + (0.,), uncoupled_brake, 1 / 240, capacity, 0., efficiency)
        assert value == pytest.approx(expected[:2], abs=1e-10)
        assert all(torque * speed >= -1e-9 for torque, speed in zip(value, speeds))
