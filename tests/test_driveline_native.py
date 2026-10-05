"""真实Bullet驾驶中的输出/前/后轴读回及重定位/reset。"""

from dataclasses import replace

import pytest
from physics.reference_ab import _create_vehicle, _step

from driving_modes import DrivingMode
from powertrain import Powertrain
from vehicle_state import VehicleCommand


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("share", (0., .5, 1.))
def test_native_neutral_rolling_rotors_and_lifecycle(mode, share):
    config = replace(mode.vehicle_config, front_drive_share=share)
    world, car = _create_vehicle(config)
    try:
        car.reset((0., 0., .55), speed=12.)
        inertias = (config.downstream_inertias[0], config.downstream_inertias[1] if share else 0.,
                    config.downstream_inertias[2] if share < 1 else 0.)
        initial_speed = config.final_drive * 12. / config.wheel_radius
        expected = tuple(initial_speed if j else 0. for j in inertias)
        assert car.powertrain.downstream_omega == pytest.approx(expected, abs=1e-12)
        for _ in range(40):
            _step(world, car, VehicleCommand(gear=0, clutch=0., brake=.3, steering=5.))
        state = car.snapshot()
        assert state.gear == 0 and state.powertrain_state.drive_torque == 0.
        assert state.powertrain_state.downstream_omega == car.powertrain.downstream_omega
        assert car.powertrain.downstream_omega != expected
        assert sum(state.powertrain_state.downstream_kinetic_energy) > 0.
        assert sum(state.powertrain_state.downstream_numerical_dissipation) > 0.
        assert any(abs(value) > 0. for value in state.powertrain_state.downstream_body_impulse)
        assert max(w.force_residual for w in state.wheel_dynamics) < .001
        assert any(abs(w.drive_torque) > 0. for w in state.wheel_dynamics)
        before = state.powertrain_state
        car.shift(1000.)
        assert car.snapshot().powertrain_state == before
        car.reset((0., 0., .55), speed=8.)
        assert car.powertrain.downstream_omega == pytest.approx(tuple(
            config.final_drive * 8. / config.wheel_radius if j else 0. for j in inertias))
        assert car.powertrain.downstream_numerical_dissipation == (0.,) * 3
        assert car.powertrain.downstream_body_impulse == (0.,) * 3
    finally:
        car.close()


@pytest.mark.parametrize("field,value", [
    ("downstream_inertias", (0., .01, .02)),
    ("downstream_inertias", (.01, float("nan"), .02)),
    ("downstream_axes", ((0., 2., 0.),) * 3),
    ("downstream_axes", ((0., 1., 0.),) * 2),
])
def test_downstream_hardware_configuration_boundary(field, value):
    with pytest.raises(ValueError):
        replace(DrivingMode.GAME.vehicle_config, **{field: value})


def test_frozen_mechanism_disables_downstream_rotors():
    for config in (replace(DrivingMode.GAME.vehicle_config, input_shaft_enabled=False),
                   replace(DrivingMode.GAME.vehicle_config, downstream_inertia_enabled=False)):
        train = Powertrain(config)
        train.initialize_rolling(12.)
        assert not train.downstream_active
        assert train.downstream_omega == train.snapshot().downstream_omega == ()
