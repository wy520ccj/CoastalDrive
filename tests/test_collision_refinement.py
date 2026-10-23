"""真实撞击回归：细分碰撞拍，普通驾驶仍沿用原积分。"""

from dataclasses import asdict

import pytest
from panda3d.core import Vec3

import simulation as simulation_module
from driving_modes import DrivingMode
from simulation import FIXED_DT, Control, Simulation
from vehicle_designs import vehicle_design


@pytest.mark.parametrize('design,vx,vy', [
    ('game-tuned', 8., 12.), ('subaru-wrx-sti', 22., 35.), ('subaru-wrx-sti', 35., 0.)])
@pytest.mark.parametrize('braking', [False, True])
def test_real_rail_impact_completes_with_unchanged_tick_and_hardware(design, vx, vy, braking, monkeypatch):
    config = DrivingMode.GAME.configured_vehicle(base_config=vehicle_design(design).config)
    simulation = Simulation(track='highway', traffic_count=0, config=config)
    calls, impacts = [], []
    advance = simulation_module.advance_world

    def observed(*args, **kwargs):
        calls.append(kwargs['substeps'])
        return advance(*args, **kwargs)

    monkeypatch.setattr(simulation_module, 'advance_world', observed)
    try:
        simulation.reset_player((5.8, 30., .55))
        simulation.player._chassis.setLinearVelocity(Vec3(vx, vy, 0))
        simulation.player.tires.initialize_rolling(vy)
        for _ in range(240):
            simulation.step(Control(brake=float(braking), throttle=float(not braking)))
            impacts.extend(simulation.snapshot().impacts)
        state = simulation.snapshot()
        assert impacts and any(event.raw_impulse > 0 for event in impacts)
        assert state.tick == 240 and state.time == 240*FIXED_DT
        assert max(calls) == 4 and simulation.config is config
        assert simulation.player_collisions > 0
    finally:
        simulation.close()


def test_clear_road_keeps_original_single_step_trajectory(monkeypatch):
    config = DrivingMode.GAME.configured_vehicle(base_config=vehicle_design('game-tuned').config)
    states = []
    for predict in (False, True):
        simulation = Simulation(track='highway', traffic_count=0, config=config)
        try:
            if not predict:
                monkeypatch.setattr(simulation, '_approaching_body_contact', lambda: False)
            for _ in range(240):
                simulation.step(Control(throttle=1.))
            state = asdict(simulation.snapshot())
            state.pop('contact_epoch')
            states.append(state)
            assert simulation._collision_refinement_ticks == 0
        finally:
            simulation.close()
    assert states[0] == states[1]
