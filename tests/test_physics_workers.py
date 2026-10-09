"""完整数值并行仍保持轨迹、机械账、真实碰撞和重建/退出资源边界。"""

from dataclasses import replace
from multiprocessing.shared_memory import SharedMemory

import pytest
from panda3d.core import TransformState, Vec3

from driving_modes import DrivingMode
from simulation import Control, Simulation
from vehicle_designs import GR86_DESIGN


@pytest.mark.parametrize('mode',list(DrivingMode))
def test_parallel_complete_tire_step_matches_serial_turn_brake_and_world_reset(mode):
    config = mode.configured_vehicle(base_config=GR86_DESIGN)
    serial = Simulation(seed=17,track='coastal',traffic_count=2,config=config,input_config=mode.input_config)
    parallel = Simulation(seed=17,track='coastal',traffic_count=2,config=config,input_config=mode.input_config,physics_workers=2)
    try:
        for seed in (17,23):
            if seed==23:
                serial.reset(seed)
                parallel.reset(seed)
                assert parallel._physics_workers.reference is None
            for tick in range(40):
                control = Control(throttle=.3 if tick<24 else 0.,brake=.5 if tick>=24 else 0.,
                                  steering=.1 if tick>=16 else 0.)
                serial.step(control)
                parallel.step(control)
                assert parallel.snapshot() == serial.snapshot()
        assert parallel._physics_workers.remote_count > 0
        memory = parallel._physics_workers.reference.name
    finally:
        serial.close()
        parallel.close()
    assert not parallel._physics_workers.processes
    assert parallel._physics_workers.shapes is None
    assert parallel._physics_workers.memory is None
    with pytest.raises(FileNotFoundError):
        SharedMemory(name=memory)


def test_parallel_still_commits_real_bullet_collision_and_same_impact_events():
    serial = Simulation(seed=17,track='test',traffic_count=2)
    parallel = Simulation(seed=17,track='test',traffic_count=2,physics_workers=2)
    try:
        for sim in (serial,parallel):
            sim.player._chassis.setTransform(TransformState.makePos(Vec3(0.,0.,.55)))
            sim.player._chassis.setLinearVelocity(Vec3(6.,0.,0.))
            sim.npcs[0]._chassis.setTransform(TransformState.makePos(Vec3(2.1,0.,.55)))
            sim.npcs[0]._chassis.setLinearVelocity(Vec3(0.,0.,0.))
        collided = False
        for _ in range(16):
            serial.step(Control())
            parallel.step(Control())
            left,right = serial.snapshot(),parallel.snapshot()
            assert all(event.epoch==left.contact_epoch for event in left.impacts)
            assert all(event.epoch==right.contact_epoch for event in right.impacts)
            assert replace(left,contact_epoch=0,impacts=tuple(replace(event,epoch=0) for event in left.impacts)) == replace(
                right,contact_epoch=0,impacts=tuple(replace(event,epoch=0) for event in right.impacts))
            collided |= bool(left.collisions)
        assert collided
        assert parallel._physics_workers.remote_count > 0
    finally:
        serial.close()
        parallel.close()


def test_one_worker_handles_many_cars_without_pipe_backpressure_or_result_reordering():
    serial = Simulation(seed=17,track='coastal',traffic_count=8)
    parallel = Simulation(seed=17,track='coastal',traffic_count=8,physics_workers=1)
    try:
        for _ in range(3):
            serial.step(Control(throttle=.3))
            parallel.step(Control(throttle=.3))
            assert serial.snapshot() == parallel.snapshot()
        assert not parallel._physics_workers.in_flight
        assert not parallel._physics_workers.completed
    finally:
        serial.close()
        parallel.close()
