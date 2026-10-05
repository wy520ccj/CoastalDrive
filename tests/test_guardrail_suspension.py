"""原生护栏大轮荷工况：保持硬件与残差门槛，不要求重现旧碰撞时点。"""

from dataclasses import replace

import pytest
from panda3d.core import Vec3

from driving_modes import DrivingMode
from simulation import Control, Simulation
from vehicle_contacts import road_support


@pytest.mark.parametrize("mode", list(DrivingMode))
@pytest.mark.parametrize("centered", (False, True))
def test_high_load_curved_rail_support_converges_and_reaches_snapshot(mode, centered):
    simulation = Simulation(track="highway", traffic_count=0,
                            config=replace(mode.vehicle_config, centered_collision_support=centered))
    peak_load = 0.
    try:
        simulation.reset_player((5.8, 30, .55))
        simulation.player._chassis.setLinearVelocity(Vec3(8, 12, 0))
        simulation.player.tires.initialize_rolling(12)
        for tick in range(30):
            simulation.step(Control())
            state = simulation.snapshot().player
            support = state.suspension_state
            assert support.force_tick == state.contact_tick == tick + 1
            for _dt, step in support.substeps:
                assert abs(step.energy_residual) < 3e-9
            for contact, tire, load in zip(state.wheel_contacts, state.wheel_dynamics, support.normal_force):
                assert contact.normal_load == load
                expected = load if contact.in_contact and road_support(contact.contact_normal) else 0.
                assert tire.normal_load == expected
                assert abs(tire.force_residual) < .001
                peak_load = max(peak_load, load)
        # 此固定摆位原球体横向多占空间产生约35万N；有限胎宽须消除该假支撑。
        # 独立胎宽/距离几何见test_cylinder_suspension，生产轮荷仍不作裁剪。
        assert 0. < peak_load < 100_000.
    finally:
        simulation.close()
