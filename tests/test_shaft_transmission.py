"""实体轴的独立能量/动量账、有限同步与齿轮实际反力。"""

from itertools import product

import pytest

from shaft_transmission import (
    dot,
    shaft_brake_plans,
    shaft_brake_response,
    shaft_brake_state,
    shaft_gradients,
    synchronizer_brake_plans,
    synchronizer_brake_state,
)

INERTIAS = (300., 400., 500., .2, .04, 1.8, 1.8, 1.8, 1.8)
ENGINE_AXIS = (0., 1., 0.)
SHAFT_AXIS = (0., 1., 0.)
AXES = ((1., 0., 0.),) * 4
WEIGHTS = (.25,) * 4
DT = 1 / 240


def mechanics(ratio=3., weights=WEIGHTS, engine_axis=ENGINE_AXIS, shaft_axis=SHAFT_AXIS):
    clutch, gear, loss = shaft_gradients(engine_axis, shaft_axis, AXES, weights, ratio)
    brake = AXES[0] + (0., 0., 1., 0., 0., 0.)
    gradients = clutch, gear, loss, brake
    mobility = tuple(tuple(g[i] / INERTIAS[i] for i in range(9)) for g in gradients)
    response = tuple(tuple(dot(g, m) for m in mobility) for g in gradients)
    return gradients, mobility, response


def audit(initial, end, values, ratio, dt, *, engine_axis=ENGINE_AXIS,
          shaft_axis=SHAFT_AXIS, weights=WEIGHTS, omit_shaft=False):
    """不借端口梯度重建各实体矩、轴储能和总角动量。"""
    clutch, gear, loss, brake = values
    engine_speed = end[3] - dot(end[:3], engine_axis)
    shaft_speed = end[4] - dot(end[:3], shaft_axis)
    wheels = tuple(end[i + 5] + dot(end[:3], AXES[i]) for i in range(4))
    wheel_input = ratio * sum(weight * speed for weight, speed in zip(weights, wheels))
    assert INERTIAS[3] * (end[3] - initial[3]) == pytest.approx(-dt * clutch, abs=1e-11)
    assert INERTIAS[4] * (end[4] - initial[4]) == pytest.approx(dt * (clutch - gear), abs=1e-11)
    body = tuple((clutch * (engine_axis[a] - shaft_axis[a]) + gear * shaft_axis[a]
                  + ratio * (gear - loss) * sum(weights[i] * AXES[i][a] for i in range(4))
                  - brake * AXES[0][a]) for a in range(3))
    for a in range(3):
        assert INERTIAS[a] * (end[a] - initial[a]) == pytest.approx(dt * body[a], abs=1e-10)
    for i in range(4):
        wheel_torque = ratio * weights[i] * (gear - loss) - (brake if i == 0 else 0.)
        assert INERTIAS[i + 5] * (end[i + 5] - initial[i + 5]) == pytest.approx(dt * wheel_torque, abs=1e-10)
    heat = dt * (clutch * (engine_speed - shaft_speed) + gear * (shaft_speed - wheel_input)
                 + loss * wheel_input + brake * wheels[0])
    kinetic = sum(.5 * inertia * (end[i]**2 - initial[i]**2)
                  for i, inertia in enumerate(INERTIAS) if not (omit_shaft and i == 4))
    numerical = sum(.5 * inertia * (end[i] - initial[i])**2 for i, inertia in enumerate(INERTIAS))
    assert kinetic + numerical + heat == pytest.approx(0., abs=3e-9)
    for a in range(3):
        angular_change = (INERTIAS[a] * (end[a] - initial[a])
                          + INERTIAS[3] * (end[3] - initial[3]) * engine_axis[a]
                          + INERTIAS[4] * (end[4] - initial[4]) * shaft_axis[a]
                          - sum(INERTIAS[i + 5] * (end[i + 5] - initial[i + 5]) * AXES[i][a] for i in range(4)))
        assert angular_change == pytest.approx(0., abs=1e-10)


@pytest.mark.parametrize("modes", product((-1, 0, 1), repeat=3))
@pytest.mark.parametrize("gear_torque", (-150., 70.))
@pytest.mark.parametrize("efficiency", (.88, 1.))
def test_actual_shaft_gear_reaction_with_all_clutch_loss_brake_modes(modes, gear_torque, efficiency):
    clutch_mode, motion, brake_mode = modes
    clutch = clutch_mode * 300. if clutch_mode else 20.
    speed = motion * 50.
    slip = clutch_mode * 40.
    bounds = sorted(((1 - efficiency) * gear_torque, (1 - 1 / efficiency) * gear_torque))
    loss = bounds[1] if motion > 0 else bounds[0] if motion < 0 else sum(bounds) / 2
    brake = brake_mode * 600. if brake_mode else 10.
    wheel_speed = brake_mode * 40.
    others = (speed / 3 - WEIGHTS[0] * wheel_speed) / sum(WEIGHTS[1:])
    expected_end = (0., 0., 0., speed + slip, speed, wheel_speed, others, others, others)
    values = clutch, gear_torque, loss, brake
    gradients, mobility, response = mechanics()
    initial = tuple(expected_end[i] + DT * sum(values[j] * mobility[j][i] for j in range(4)) for i in range(9))
    free = tuple(dot(g, initial) for g in gradients)
    plans = shaft_brake_plans(response, 300., 600., efficiency)
    result, speeds, index = shaft_brake_state(free, response, DT, 300., 600., efficiency, plans)
    assert result == pytest.approx(values, abs=1e-10)
    assert speeds == pytest.approx((slip, 0., speed, wheel_speed), abs=1e-11)
    end = tuple(initial[i] - DT * sum(result[j] * mobility[j][i] for j in range(4)) for i in range(9))
    audit(initial, end, result, 3., DT)
    warmed, _speeds, _index = shaft_brake_state(free, response, DT, 300., 600., efficiency, plans,
                                               (index + 11) % len(plans))
    assert warmed == pytest.approx(result, abs=1e-10)


@pytest.mark.parametrize("capacity", (0., 300.))
def test_neutral_clutch_loads_real_input_inertia(capacity):
    gradients, mobility, response = mechanics(0.)
    ports = (0, 1, 3)
    reduced = tuple(tuple(response[i][j] for j in ports) for i in ports)
    capacities = capacity, 0., 0.
    plans = synchronizer_brake_plans(reduced, capacities)
    initial = (0., 0., 0., 100., 0., 0., 0., 0., 0.)
    free = tuple(dot(gradients[i], initial) for i in ports)
    values, _speeds, _index = synchronizer_brake_state(free, reduced, 1 / 120, capacities, plans)
    full_values = values[0], values[1], 0., values[2]
    end = tuple(initial[i] - 1 / 120 * sum(full_values[j] * mobility[j][i] for j in range(4)) for i in range(9))
    assert end[3] == pytest.approx(100. - capacity / 120 / .2, abs=1e-12)
    assert end[4] == pytest.approx(capacity / 120 / .04, abs=1e-12)
    assert end[5:] == (0.,) * 4
    audit(initial, end, full_values, 0., 1 / 120)
    if capacity:
        with pytest.raises(AssertionError):
            audit(initial, end, full_values, 0., 1 / 120, omit_shaft=True)


@pytest.mark.parametrize("ratio", (-3., 2.))
@pytest.mark.parametrize("shaft_axis", ((0., 1., 0.), (0., 0., 1.)))
def test_finite_synchronizer_reaches_speed_match_by_real_impulses(ratio, shaft_axis):
    gradients, mobility, response = mechanics(ratio, shaft_axis=shaft_axis)
    ports = (0, 1, 3)
    reduced = tuple(tuple(response[i][j] for j in ports) for i in ports)
    capacities = 0., 20., 0.
    plans = synchronizer_brake_plans(reduced, capacities)
    state = (0., 0., 0., 100., 80., 0., 0., 0., 0.)
    heat, saturated_steps = 0., 0
    for tick in range(240):
        free = tuple(dot(gradients[i], state) for i in ports)
        values, speeds, _index = synchronizer_brake_state(free, reduced, DT, capacities, plans)
        full_values = values[0], values[1], 0., values[2]
        end = tuple(state[i] - DT * sum(full_values[j] * mobility[j][i] for j in range(4)) for i in range(9))
        audit(state, end, full_values, ratio, DT, shaft_axis=shaft_axis)
        assert values[1] * speeds[1] >= -1e-11
        heat += DT * values[1] * speeds[1]
        saturated_steps += int(abs(values[1]) == 20.)
        state = end
        if abs(speeds[1]) < 1e-11:
            break
    else:
        pytest.fail("有限同步器未达到真实轴速匹配")
    assert saturated_steps > 5 and tick > 5 and heat > 0.
    assert state[3] == 100.
    assert max(abs(w) for w in state[5:]) > 0.


def test_loss_follows_gear_reaction_even_with_clutch_open():
    gradients, mobility, response = mechanics()
    initial = (0., 0., 0., 0., 120., 0., 0., 0., 0.)
    plans = shaft_brake_plans(response, 0., 0., .88)
    values, speeds, index = shaft_brake_state(tuple(dot(g, initial) for g in gradients), response,
                                             DT, 0., 0., .88, plans)
    assert values[0] == 0. and values[1] > 0. and values[2] > 0.
    assert values[2] == pytest.approx(.12 * values[1], abs=1e-10)
    end = tuple(initial[i] - DT * sum(values[j] * mobility[j][i] for j in range(4)) for i in range(9))
    audit(initial, end, values, 3., DT)
    direction = (.5, -.7, 1.1, -.3)
    derivative = shaft_brake_response(direction, response, plans[index])
    step = 1e-5
    free = tuple(dot(g, initial) for g in gradients)
    shifted, _speeds, _index = shaft_brake_state(tuple(free[i] + DT * step * direction[i] for i in range(4)),
                                                response, DT, 0., 0., .88, plans)
    assert tuple((shifted[i] - values[i]) / step for i in range(4)) == pytest.approx(derivative, abs=1e-6)
    assert speeds[1] == pytest.approx(0., abs=1e-11)
