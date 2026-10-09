"""完整数值并行仍保持轨迹、机械账、真实碰撞和重建/退出资源边界。"""

from dataclasses import replace
from multiprocessing.shared_memory import SharedMemory

import pytest
from panda3d.bullet import (
    BulletBoxShape,
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
)
from panda3d.core import BitMask32, TransformState, Vec3

from driving_modes import DrivingMode
from session import GameMode, Phase, Session
from simulation import Control, Simulation
from vehicle_designs import GR86_DESIGN


@pytest.mark.parametrize('mode',list(DrivingMode))
def test_preload_initializes_geometry_and_workers_without_advancing_world(mode):
    config = mode.configured_vehicle(base_config=GR86_DESIGN)
    serial = Simulation(seed=17,track='coastal',traffic_count=2,config=config,input_config=mode.input_config)
    parallel = Simulation(seed=17,track='coastal',traffic_count=2,config=config,input_config=mode.input_config,physics_workers=2)
    try:
        for seed in (17,23):
            if seed==23:
                serial.reset(seed)
                parallel.reset(seed)
            before = parallel.snapshot()
            count = parallel._physics_workers.remote_count
            parallel.prepare_physics()
            assert parallel.snapshot() == before
            assert parallel._physics_workers.remote_count == count
            assert parallel._physics_workers.identifier == count
            assert len(parallel._physics_workers.processes) == 2
            assert parallel._physics_workers.preparation_seconds > 0.
            assert all(id(config) in values for values in parallel._physics_workers.worker_configurations)
            assert not parallel._physics_workers.in_flight
            for _ in range(3):
                serial.step(Control(throttle=.3,steering=.1))
                parallel.step(Control(throttle=.3,steering=.1))
                assert serial.snapshot() == parallel.snapshot()
    finally:
        serial.close()
        parallel.close()


def test_single_vehicle_does_not_start_unused_workers():
    sim = Simulation(track='test',traffic_count=0,physics_workers=2)
    try:
        sim.prepare_physics()
        assert not sim._physics_workers.processes
        assert sim._physics_workers.reference is None
        assert sim.snapshot().tick == 0
    finally:
        sim.close()


def test_session_prepares_physics_before_countdown_or_driving(monkeypatch):
    observed = []
    session = Session(seed=17,physics_workers=0)
    try:
        def prepare(simulation, *, background=False):
            observed.append((session.phase,simulation.snapshot().tick,background))
        monkeypatch.setattr(Simulation,'prepare_physics',prepare)
        session.start(mode=GameMode.FREE_DRIVE,countdown=True)
        assert observed == [(Phase.LOADING,0,True)]
        assert session.phase == Phase.COUNTDOWN
    finally:
        session.close()


def test_background_preparation_staggers_workers_then_finishes_without_world_step():
    sim = Simulation(track='coastal',traffic_count=2,physics_workers=4)
    try:
        before = sim.snapshot()
        sim.prepare_physics(background=True)
        pool = sim._physics_workers
        assert len(pool.processes) == 4
        assert pool.preparation_next == 2
        pool.next_prepare_start = float('inf')
        assert not sim.physics_ready()
        assert pool.preparation_next == 2
        pool.next_prepare_start = 0.
        assert not sim.physics_ready()
        assert pool.preparation_next == 3
        pool.finish_preparation()
        assert sim.physics_ready()
        assert len(pool.processes) == 4
        assert pool.remote_count == 0
        assert sim.snapshot() == before
        # 世界重开必须收完旧准备消息，不能把准备确认当成下次子步结果。
        sim.reset(23)
        sim.prepare_physics(background=True)
        sim.reset(17)
        sim.step(Control(throttle=.3))
        assert sim.snapshot().tick == 1
    finally:
        sim.close()


@pytest.mark.parametrize('mode',list(DrivingMode))
def test_loading_settles_real_suspension_before_countdown_and_go(mode):
    config = mode.configured_vehicle(base_config=GR86_DESIGN)
    session = Session(seed=17,driving_mode=mode,vehicle_config=config,physics_workers=2)
    try:
        session.start(mode=GameMode.FREE_DRIVE,countdown=True,settle_initial=True)
        initial = session.current
        assert initial.tick == 60
        assert session.simulation.initialisation_ticks == 0
        assert session.race.snapshot.elapsed == 0.
        for _ in range(360):
            session.tick()
        assert session.phase == Phase.DRIVING
        settled = session.current
        assert initial.tick<settled.tick<=360
        assert session.simulation.initialisation_ticks == settled.tick
        assert abs(settled.player.velocity[2])<=.001
        assert session.race.snapshot.elapsed == 0.
        heights = [settled.player.position[2]]
        for _ in range(24):
            session.tick()
            heights.append(session.current.player.position[2])
        # GO后0.2秒的高度变化小于0.5mm，不能再出现出生时的厘米级落地弹跳。
        assert max(heights)-min(heights)<.0005
        assert session.current.tick == settled.tick+24
    finally:
        session.close()


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


def test_geometry_versions_reuse_only_unchanged_meshes_and_rebuild_actual_replacements():
    from triangle_support import TriangleSupport

    serial = Simulation(seed=17,track='coastal',traffic_count=2)
    parallel = Simulation(seed=17,track='coastal',traffic_count=2,physics_workers=4)
    try:
        parallel.prepare_physics()
        pool = parallel._physics_workers
        initial = dict(pool.mesh_payloads)
        assert initial
        count = pool.mesh_identifier
        for sim in (serial,parallel):
            body = BulletRigidBodyNode('added-geometry')
            body.addShape(BulletBoxShape(Vec3(1.,1.,.1)))
            body.setIntoCollideMask(BitMask32.bit(0))
            body.setTransform(TransformState.makePos(Vec3(0.,0.,10.)))
            sim._world.attachRigidBody(body)
        for _ in range(3):
            serial.step(Control(throttle=.3))
            parallel.step(Control(throttle=.3))
            assert serial.snapshot() == parallel.snapshot()
        assert pool.version >= 2
        assert pool.mesh_identifier == count
        assert all(pool.mesh_payloads[key][2] is value[2] for key,value in initial.items())
        for sim in (serial,parallel):
            body = next(body for body in sim._world.getRigidBodies() if body.hasPythonTag('suspension_mesh'))
            old = body.getPythonTag('suspension_mesh')
            def collect(mesh):
                return mesh.triangles+tuple(triangle for child in mesh.children for triangle in collect(child))
            triangles = tuple(tuple((x,y,z+.02) for x,y,z in triangle) for triangle in collect(old))
            native = BulletTriangleMesh()
            for triangle in triangles:
                native.addTriangle(*(Vec3(*point) for point in triangle))
            margin = body.getShape(0).getMargin()
            body.removeShape(body.getShape(0))
            shape = BulletTriangleMeshShape(native,dynamic=False)
            shape.setMargin(margin)
            body.addShape(shape)
            body.setPythonTag('suspension_mesh',TriangleSupport.build(triangles))
            body.clearPythonTag('suspension_shape_bounds')
            if sim is parallel:
                replaced_key = id(old)
        for _ in range(4):
            serial.step(Control(throttle=.3))
            parallel.step(Control(throttle=.3))
            assert serial.snapshot() == parallel.snapshot()
        assert pool.mesh_identifier > count
        assert replaced_key not in pool.mesh_payloads
        # 新进程没有读过前两个版本，必须直接从当前完整网格载荷进入。
        pool.count = 5
        parallel.prepare_physics()
        for _ in range(2):
            serial.step(Control())
            parallel.step(Control())
            assert serial.snapshot() == parallel.snapshot()
        # 重开丢弃旧世界支持面，原生网格资源随实际进程/当前版本释放。
        serial.reset(23)
        parallel.reset(23)
        assert pool.mesh_payloads == {}
        parallel.prepare_physics()
        serial.step(Control())
        parallel.step(Control())
        assert serial.snapshot() == parallel.snapshot()
    finally:
        serial.close()
        parallel.close()
    assert pool.mesh_payloads == {}
