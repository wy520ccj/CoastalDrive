"""暖机耗油观察的单位、断油、分步和旧完整记录兼容。"""

import math
from dataclasses import replace

import pytest
from physics_packet_kernels import encode

from fuel import ENERGY_PER_LITRE, FuelMeter, fuel_efficiency
from powertrain import Powertrain
from simulation import Simulation
from snapshot_wire import _pre_fuel_layout, decode_snapshots, encode_snapshots
from vehicle_state import Control


def test_idle_consumes_without_motion_and_overrun_is_not_free_revving():
    meter = FuelMeter(900., 6500.)
    omega = 900*math.tau/60
    meter.accept(0., omega, omega, 100., 1., coupled=False)
    assert meter.snapshot().litres == pytest.approx(.7/3600)
    before = meter.litres
    omega = 3000*math.tau/60
    meter.accept(0., omega, omega, 200., 1., coupled=True)
    assert meter.cutoff and meter.rate_lph == 0. and meter.litres == before
    meter.accept(0., omega, omega, 200., 1., coupled=False)
    assert not meter.cutoff and meter.litres > before


def test_positive_active_work_consumes_even_without_wheel_output():
    meter = FuelMeter(900., 6500.)
    rpm, torque = 3250., 150.
    omega = rpm*math.tau/60
    work = torque*omega
    meter.accept(work, omega, omega, 200., 1., coupled=False)
    assert meter.litres == pytest.approx(work/(.34*ENERGY_PER_LITRE))
    assert meter.rate_lph == pytest.approx(meter.litres*3600)
    assert not meter.cutoff


def test_same_accepted_work_and_state_have_same_integral_across_substeps():
    states = []
    for count in (1, 2, 4, 120):
        meter = FuelMeter(900., 6500.)
        for _ in range(count):
            meter.accept(20_000/count, 300., 300., 200., 1/count, coupled=True)
        states.append(meter.litres)
    assert states == pytest.approx([states[0]]*4, rel=1e-13)


def test_efficiency_map_is_continuous_at_cells_and_saturates_outside_design_domain():
    assert fuel_efficiency(.5, .75) == .34
    assert fuel_efficiency(.5-1e-10, .75) == pytest.approx(fuel_efficiency(.5+1e-10, .75))
    assert fuel_efficiency(2., 3.) == fuel_efficiency(1., 1.2)
    assert fuel_efficiency(-1., -1.) == fuel_efficiency(.15, 0.)


def test_fuel_is_in_real_snapshot_and_native_wire_old_record_keeps_missing_value():
    sim = Simulation(track='test', traffic_count=0)
    try:
        for _ in range(20):
            sim.step(Control(throttle=.5))
        state = sim.snapshot()
        fuel = state.player.powertrain_state.fuel
        assert fuel.litres > 0 and fuel.rate_lph > 0
        assert decode_snapshots(encode_snapshots((state,)))[0] == state
        old_payload = encode(_pre_fuel_layout, (state,))
        old = decode_snapshots(old_payload)[0]
        assert old.player.powertrain_state.fuel is None
        assert replace(old.player.powertrain_state, fuel=fuel) == state.player.powertrain_state
        assert old.player.position == state.player.position
    finally:
        sim.close()


def test_snapshot_reads_do_not_advance_consumption():
    train = Powertrain()
    assert train.snapshot() == train.snapshot()
    assert train.snapshot().fuel.litres == 0.


def test_fuel_observer_does_not_modify_complete_mechanical_trajectory(monkeypatch):
    def drive():
        sim = Simulation(track='test', traffic_count=0)
        trace = []
        try:
            for tick in range(96):
                sim.step(Control(throttle=.5 if tick < 72 else 0.,
                                 steering=.15 if 48 <= tick < 72 else 0.,
                                 brake=.4 if tick >= 72 else 0.))
                state = sim.snapshot()
                train = replace(state.player.powertrain_state, fuel=None)
                trace.append(replace(state, contact_epoch=0,
                                     player=replace(state.player, powertrain_state=train)))
            return encode_snapshots(tuple(trace))
        finally:
            sim.close()

    observed = drive()
    monkeypatch.setattr(FuelMeter, 'accept', lambda *args, **kwargs: None)
    assert drive() == observed

