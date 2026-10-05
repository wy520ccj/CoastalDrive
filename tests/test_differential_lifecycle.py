"""有限限滑沿真实玩家/NPC生命周期保存配置，重建时清空热与转矩。"""

from dataclasses import replace

import pytest

from driving_modes import DrivingMode
from highway_segments import REBASE_DISTANCE, SEGMENT_LENGTH
from simulation import Simulation
from vehicle_state import VehicleCommand


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("share", (0., .5, 1.))
def test_limited_slip_player_npc_rebase_and_recycle(mode, share):
    base = mode.vehicle_config
    damping = (20. if share else 0., 20. if share < 1 else 0., 20. if 0 < share < 1 else 0.)
    config = replace(base, front_drive_share=share, differential_damping=damping,
                     differential_capacity=tuple(80. if c else 0. for c in damping))
    sim = Simulation(track="endless", traffic_count=1, config=config,
                     input_config=mode.input_config, traffic_input_config=mode.input_config)
    try:
        npc = sim.npcs[0]
        # 首步前的机械初值；此后全部轮速由同一物理步推进。
        npc.tires.omega[config.driven_wheels[0]] += 10.
        heat = 0.
        for _ in range(30):
            sim.step(VehicleCommand(throttle=.5, direction=1))
            heat += sum(npc.powertrain.snapshot().differential_heat)
        assert heat > 0.
        for car in (sim.player, npc):
            train = car.powertrain.snapshot()
            t0, t1, tc = train.differential_torques
            transfers = (-t0 - tc / 2, t0 - tc / 2, -t1 + tc / 2, t1 + tc / 2)
            for i, wheel in enumerate(car.snapshot().wheel_dynamics):
                assert wheel.drive_torque == pytest.approx(train.drive_torque * config.drive_weights[i]
                    + transfers[i] + train.downstream_wheel_torques[i], abs=1e-10)
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
        train = npc.powertrain.snapshot()
        assert train.differential_heat == train.differential_torques == (0.,) * 3
        expected = config.final_drive * npc.signed_speed() / config.wheel_radius
        assert train.downstream_omega == pytest.approx((expected, expected if share else 0.,
                                                       expected if share < 1 else 0.), abs=1e-5)
        assert train.downstream_numerical_dissipation == train.downstream_body_impulse == (0.,) * 3
        sim.reset_player((0., 0., .55))
        assert sim.player.config is config
        assert sim.player.powertrain.snapshot().differential_heat == (0.,) * 3
    finally:
        sim.close()
