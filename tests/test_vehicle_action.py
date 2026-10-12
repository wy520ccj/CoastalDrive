"""完整机械车辆保留真实刚体碰撞，原生Action只用于实际原生悬架/轮胎。"""

import pytest
from panda3d.core import BitMask32, Vec3

from driving_modes import DrivingMode
from simulation import Simulation
from vehicle_designs import vehicle_design
from vehicle_state import Control


@pytest.mark.parametrize('mode', list(DrivingMode))
def test_only_native_traffic_has_world_action_and_all_chassis_collide(mode):
    config = mode.configured_vehicle(base_config=vehicle_design('gr86-2022-premium-6mt').config)
    sim = Simulation(track='endless', road_shape='hills', traffic_count=2, config=config,
                     input_config=mode.input_config, traffic_input_config=mode.input_config)
    world = sim._world
    try:
        assert world.getNumVehicles() == (2 if mode is DrivingMode.GAME else 0)
        for car in [sim.player, *sim.npcs]:
            assert car._chassis in world.getRigidBodies()
            assert car._chassis.hasContactResponse()
            assert not car._chassis.isKinematic() and not car._chassis.isStatic()
            assert car._chassis.getIntoCollideMask() == BitMask32.bit(1)
            assert car._native_action == (car in sim.npcs and mode is DrivingMode.GAME)
        # 两个同一世界的真实碰撞体接触，Action是否存在不改变车身碰撞。
        second = sim.npcs[0]
        second._chassis.setTransform(sim.player._chassis.getTransform().setPos(
            sim.player._chassis.getTransform().getPos()+Vec3(.3, 0., 0.)))
        assert world.contactTestPair(sim.player._chassis, second._chassis).getNumContacts()>0
        second.reset((0., 2000., .55))
        cycles = sim.traffic_cycles
        sim._update_stream()
        assert sim.traffic_cycles > cycles
        assert second._chassis in world.getRigidBodies()
        assert world.getNumVehicles() == (2 if mode is DrivingMode.GAME else 0)
        for _ in range(120):
            sim.step(Control(throttle=.2))
        assert sim.player.snapshot().suspension_state.force_tick>0
        assert sim.player.snapshot().wheel_dynamics
        second.detach_physics()
        assert second._chassis not in world.getRigidBodies()
        second.close()
        assert not second._attached
    finally:
        sim.close()
    assert all(body.isStatic() for body in world.getRigidBodies())
    assert world.getNumVehicles() == 0
