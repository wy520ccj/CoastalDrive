"""真实驾驶路径的输入轴、有限同步和状态生命周期。"""

from dataclasses import replace

import pytest
from physics.reference_ab import _create_vehicle, _step

from driving_modes import DrivingMode
from highway_segments import REBASE_DISTANCE, SEGMENT_LENGTH
from powertrain import Powertrain
from simulation import Simulation
from vehicle_state import FIXED_DT, VehicleCommand


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("clutch", (0., 1.))
def test_native_neutral_clutch_spins_real_input_shaft(mode, clutch):
    world, car = _create_vehicle(mode.vehicle_config)
    try:
        for _ in range(50):
            _step(world, car, VehicleCommand(gear=0, clutch=clutch))
        state = car.snapshot().powertrain_state
        assert state.gear == 0 and state.drive_torque == 0.
        assert state.shaft_omega == car.powertrain.shaft_omega
        if clutch:
            assert state.shaft_relative_omega > 10.
            assert state.engine_relative_omega > 10.
            assert abs(state.clutch_slip) < 1e-9
        else:
            assert state.shaft_omega == 0.
        before = car.powertrain.snapshot(), tuple(car.tires.omega)
        car.shift(1000.)
        assert (car.powertrain.snapshot(), tuple(car.tires.omega)) == before
        car.reset((0., 0., .55), speed=12.)
        assert car.powertrain.shaft_omega == pytest.approx(car.powertrain.ratio * 12. / car.config.wheel_radius)
        assert car.powertrain.synchronizer_heat == 0.
        assert car.powertrain.shaft_body_impulse == (0.,) * 3
    finally:
        car.close()


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("share", (0., .5, 1.))
def test_native_shift_waits_for_real_finite_synchronization(mode, share):
    config = replace(mode.vehicle_config, front_drive_share=share, input_shaft_inertia=.04,
                     synchronizer_capacity=20.)
    world, car = _create_vehicle(config)
    try:
        car.reset((0., 0., .55), speed=18.)
        heat, pending_ticks = 0., 0
        gears = []
        for _ in range(100):
            _step(world, car, VehicleCommand(gear=2, clutch=0.))
            state = car.snapshot().powertrain_state
            gears.append(state.gear)
            heat += state.synchronizer_heat
            if state.shift_phase == "synchronizing":
                pending_ticks += 1
                assert state.gear == 0 and state.pending_gear == 2
                assert abs(state.synchronizer_torque) <= config.synchronizer_capacity + 1e-11
            if state.gear == 2:
                assert abs(state.synchronizer_slip) < 1e-11
                break
        else:
            pytest.fail("原生输入轴有限同步未完成挂挡")
        assert pending_ticks > 5 and heat > 0. and set(gears) == {0, 2}
        assert abs(state.gear_reaction - state.clutch_torque) > 0.
    finally:
        car.close()


@pytest.mark.parametrize("mode", list(DrivingMode))
def test_preparation_and_interrupted_sync_preserve_all_physical_shaft_speeds(mode):
    train = Powertrain(mode.vehicle_config)
    train.engine_omega, train.shaft_omega = 450., 350.
    train.gear = 0
    train.pending_gear = 2
    train.shift_phase = "synchronizing"
    train.prepare(18., 50., .2, 1, False, FIXED_DT, gear=3, clutch=1.)
    assert train.pending_gear == 3 and train.gear == 0
    assert train.synchronizing
    assert train.engine_omega == 450. and train.shaft_omega == 350.
    assert train.capacity == 0.
    assert train.mechanical_ratio == pytest.approx(train.config.gear_ratios[2] * train.config.final_drive)
    train.prepare(18., 50., .2, 1, False, FIXED_DT, gear=0, clutch=1.)
    assert train.gear == train.pending_gear == 0
    assert not train.synchronizing
    assert train.engine_omega == 450. and train.shaft_omega == 350.


@pytest.mark.parametrize("field,value", (("input_shaft_inertia", 0.), ("input_shaft_inertia", float("inf")),
                                      ("synchronizer_capacity", -1.), ("input_shaft_axis", (0., 2., 0.))))
def test_input_shaft_config_boundary_rejects_nonphysical_parameters(field, value):
    with pytest.raises(ValueError):
        replace(DrivingMode.SIMULATION.vehicle_config, **{field: value})


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("share", (0., .5, 1.))
def test_native_npc_input_shaft_rebase_and_recycle(mode, share):
    config = replace(mode.vehicle_config, front_drive_share=share)
    sim = Simulation(track="endless", traffic_count=1, config=config,
                     input_config=mode.input_config, traffic_input_config=mode.input_config)
    try:
        npc = sim.npcs[0]
        for _ in range(30):
            sim.step(VehicleCommand(throttle=.5, direction=1))
        assert npc.powertrain.shaft_omega != 0.
        mechanical = npc.powertrain.snapshot(), tuple(npc.tires.omega)
        for car in (sim.player, npc):
            car.shift(-(REBASE_DISTANCE + SEGMENT_LENGTH))
        sim._rebase()
        assert sim.rebases == 1
        assert (npc.powertrain.snapshot(), tuple(npc.tires.omega)) == mechanical
        npc.shift(-5000.)
        cycles = sim.traffic_cycles
        sim._update_stream()
        assert sim.traffic_cycles > cycles
        assert npc.config is config
        assert npc.powertrain.shaft_omega == pytest.approx(
            npc.powertrain.ratio * npc.signed_speed() / config.wheel_radius, abs=1e-4)
        assert npc.powertrain.synchronizer_heat == 0.
        assert npc.powertrain.shaft_body_impulse == (0.,) * 3
    finally:
        sim.close()
