"""驱动布局在真实玩家/NPC重定位及回收中保持，控制记忆按实体reset清空。"""

from dataclasses import replace

import pytest

from driving_modes import DrivingMode
from highway_segments import REBASE_DISTANCE, SEGMENT_LENGTH
from simulation import Simulation
from vehicle_state import VehicleCommand, WheelDynamicsState


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("share", (0., .5, 1.))
def test_layout_survives_player_npc_rebase_and_recycle(mode, share):
    config = replace(mode.vehicle_config, front_drive_share=share)
    sim = Simulation(track="endless", traffic_count=1, config=config,
                     input_config=mode.input_config, traffic_input_config=mode.input_config)
    try:
        for _ in range(60):
            sim.step(VehicleCommand(throttle=.5, direction=1))
        npc = sim.npcs[0]
        for car in (sim.player, npc):
            assert car.config is config
            assert car.traction.driven_wheels == config.driven_wheels
            snapshot = car.snapshot()
            for i, wheel in enumerate(snapshot.wheel_dynamics):
                assert wheel.drive_torque == pytest.approx(snapshot.powertrain_state.drive_torque
                    * (share if i < 2 else 1 - share) / 2
                    + snapshot.powertrain_state.downstream_wheel_torques[i], abs=1e-10)
        mechanical = npc.powertrain.snapshot(), tuple(npc.tires.omega)
        for car in (sim.player, npc):
            car.shift(-(REBASE_DISTANCE + SEGMENT_LENGTH))
        sim._rebase()
        assert sim.rebases == 1
        assert (npc.powertrain.snapshot(), tuple(npc.tires.omega)) == mechanical
        # 独立控制初值只用于验证回收清空记忆；随后走实际退役/重建路径。
        feedback = tuple(WheelDynamicsState(omega=60., longitudinal_speed=10.,
                         sample_support=True, sample_tick=60) for _ in range(4))
        npc.traction.advance(1., 1, False, feedback, config.wheel_radius, 1 / 120)
        assert npc.traction.state.active
        npc.shift(-5000.)
        cycles = sim.traffic_cycles
        sim._update_stream()
        assert sim.traffic_cycles > cycles
        assert "traffic_recycled:0" in sim._events
        assert npc.config is config and npc.traction.driven_wheels == config.driven_wheels
        assert not npc.traction.state.active
        assert npc.traction.state.brake_requests == (0.,) * 4
        assert all(w.drive_torque == 0. for w in npc.tires.states)
        train = npc.powertrain.snapshot()
        expected = config.final_drive * npc.signed_speed() / config.wheel_radius
        assert train.downstream_omega == pytest.approx((expected, expected if share else 0.,
                                                       expected if share < 1 else 0.), abs=1e-5)
        assert train.downstream_body_impulse == train.downstream_numerical_dissipation == (0.,) * 3
        assert train.downstream_wheel_torques == (0.,) * 4
    finally:
        sim.close()
