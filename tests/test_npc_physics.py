"""正常模式交通车的原生碰撞、停车唤醒与两模式边界。"""

from dataclasses import asdict, replace

import pytest
from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, TransformState, Vec3

from driving_modes import DrivingMode
from npc_physics import TrafficVehicle
from session import Session
from simulation import Simulation
from vehicle import Vehicle
from vehicle_designs import vehicle_design
from vehicle_state import FIXED_DT, Control, VehicleCommand
from world_step import advance_world, physical_substeps

CONFIG = vehicle_design('gr86-2022-premium-6mt').config


@pytest.mark.parametrize('design', ['reference-rwd', 'reference-fwd', 'reference-awd'])
def test_engineering_reference_keeps_player_aligning_and_native_traffic_independent(design):
    config = DrivingMode.GAME.configured_vehicle(base_config=vehicle_design(design).config)
    sim = Simulation(track='test', traffic_count=1, config=config,
                     input_config=DrivingMode.GAME.input_config)
    try:
        assert sim.player.config.tire_aligning_enabled
        assert not sim.npcs[0].config.tire_aligning_enabled
        assert not sim.npcs[0].config.unsprung_enabled
        assert not sim.npcs[0].config.tire_compliance
        sim.step(Control(throttle=.2))
        assert sim.snapshot().tick == 1
    finally:
        sim.close()


def test_native_request_reuse_preserves_material_and_time_scaled_braking():
    sim = Simulation(track='test', traffic_count=1, config=CONFIG,
                     input_config=DrivingMode.GAME.input_config)
    try:
        npc = sim.npcs[0]
        request = npc.prepare_command(VehicleCommand(brake=.4))
        npc.physics_stages(request, FIXED_DT / 2)
        wheel = npc._vehicle.getWheel(0)
        first_brake = wheel.getBrake()
        assert first_brake > 0
        npc.on_asphalt = lambda x, y: False
        npc.physics_stages(request, FIXED_DT / 2)
        assert wheel.getFrictionSlip() == pytest.approx(npc.config.grass_friction)
        assert wheel.getBrake() == first_brake
        npc.physics_stages(request, FIXED_DT)
        assert wheel.getBrake() == pytest.approx(2 * first_brake)
        npc.reset((0, 0, .8))
        assert npc._native_request is None
    finally:
        sim.close()


@pytest.mark.parametrize('share', [0., .5, 1.])
def test_native_traffic_preserves_drive_layout_and_recycles(share):
    config = replace(DrivingMode.GAME.vehicle_config, front_drive_share=share)
    sim = Simulation(seed=23, track='endless', traffic_count=1, config=config,
                     input_config=DrivingMode.GAME.input_config)
    try:
        npc = sim.npcs[0]
        assert type(npc) is TrafficVehicle
        assert sim.player.config is config and sim.player.config.finite_drivetrain
        assert npc.config.native_tire_forces and not npc.config.finite_drivetrain
        assert npc.config.drive_weights == config.drive_weights
        # 实际原生轮分别收到驱动与发动机制动；没有完整传动遥测冒充实体轴积分。
        npc.physics_stages((1000., 200., (0.,)*4), 1/240)
        for weight, wheel in zip(config.drive_weights, npc._vehicle.getWheels()):
            assert wheel.getEngineForce() == pytest.approx(1000.*weight/config.wheel_radius, rel=1e-6)
            assert wheel.getBrake() == pytest.approx(200.*weight/240/config.wheel_radius, rel=1e-6)
        for _ in range(30):
            sim.step(Control(throttle=.3))
        assert npc.snapshot().wheel_dynamics == ()
        npc.shift(-5000.)
        cycles = sim.traffic_cycles
        sim._update_stream()
        assert sim.traffic_cycles > cycles
        assert npc.config.drive_weights == config.drive_weights
        assert npc.config.native_tire_forces
    finally:
        sim.close()


def test_native_traffic_configuration_keeps_full_solver_guard():
    with pytest.raises(ValueError, match='不能同时'):
        replace(CONFIG, native_tire_forces=True)
    with pytest.raises(ValueError, match='旧对照'):
        replace(CONFIG, finite_drivetrain=False, front_drive_share=.5)


@pytest.mark.parametrize('mode', list(DrivingMode))
def test_only_normal_traffic_uses_native_model_and_player_is_complete(mode):
    config = mode.configured_vehicle(base_config=CONFIG)
    hardware = asdict(config)
    sim = Simulation(seed=17, track='test', traffic_count=2, config=config,
                     input_config=mode.input_config)
    try:
        assert type(sim.player) is Vehicle
        assert sim.player.config is config
        assert sim.player.coupled_suspension and sim.player.config.finite_drivetrain
        assert physical_substeps(config) == (1 if mode is DrivingMode.GAME else 2)
        assert asdict(config) == hardware
        for car in sim.npcs:
            assert isinstance(car, TrafficVehicle) == (mode is DrivingMode.GAME)
            assert car._world is sim._world
            assert car._chassis.getMass() == pytest.approx(config.mass)
            assert car._chassis.hasContactResponse()
            assert not car._chassis.isStatic() and not car._chassis.isKinematic()
            assert car._chassis.getIntoCollideMask() == BitMask32.bit(1)
            assert car.coupled_suspension == (mode is DrivingMode.SIMULATION)
    finally:
        sim.close()


@pytest.fixture
def native_car():
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode('ground')
    ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0.))
    ground.setIntoCollideMask(BitMask32(7))
    world.attachRigidBody(ground)
    car = TrafficVehicle(world, lambda _x, _y: True, (0., 0., .55), config=CONFIG)
    try:
        yield world, car
    finally:
        car.close()


def park(world, car):
    for _ in range(240):
        advance_world(world, [(car, VehicleCommand(brake=1., direction=1))], substeps=2)
    assert not car._chassis.isActive()
    assert car._chassis.getLinearVelocity().length() <= .001
    assert car._chassis.getAngularVelocity().length() <= .001


def test_native_parking_is_dynamic_and_real_collision_wakes_body(native_car):
    world, car = native_car
    park(world, car)
    position = car._chassis.getTransform().getPos()
    body = BulletRigidBodyNode('impactor')
    body.setMass(1000.)
    body.setIntoCollideMask(BitMask32.bit(1))
    body.addShape(BulletBoxShape(Vec3(.5, .5, .5)))
    body.setTransform(TransformState.makePos(position + Vec3(0, -3.5, 0)))
    body.setLinearVelocity(Vec3(0, 8, 0))
    world.attachRigidBody(body)
    contact = awake = False
    for _ in range(60):
        advance_world(world, [(car, VehicleCommand(brake=1., direction=1))], substeps=2)
        contact |= world.contactTestPair(car._chassis, body).getNumContacts() > 0
        awake |= car._chassis.isActive()
    assert contact and awake
    assert (car._chassis.getTransform().getPos() - position).length() > .02
    assert car._chassis.getMass() == pytest.approx(CONFIG.mass)


def test_throttle_wakes_parked_car_and_snapshot_reads_native_pose(native_car):
    world, car = native_car
    park(world, car)
    initial = car.snapshot()
    for _ in range(60):
        advance_world(world, [(car, Control(throttle=.8))], substeps=2)
    state = car.snapshot()
    assert car._chassis.isActive()
    assert state.position[1] > initial.position[1] + .02
    assert state.velocity == tuple(car._chassis.getLinearVelocity())
    assert state.orientation == tuple(car._chassis.getTransform().getQuat())
    assert state.wheel_dynamics == () and state.powertrain_state is None
    for wheel, actual in zip(car._vehicle.getWheels(), state.wheels):
        matrix = wheel.getWorldTransform()
        expected = TransformState.makeMat(matrix)
        assert actual.position == tuple(matrix.getRow3(3))
        assert abs(sum(a*b for a,b in zip(actual.orientation, expected.getQuat()))) == pytest.approx(1., abs=2e-6)
    car.reset((0., 0., .55))
    assert car._park_quiet == 0
    assert car._chassis.isActive()
    assert car.native_dt == FIXED_DT/2


def test_airborne_braked_car_remains_awake(native_car):
    world, car = native_car
    car.reset((0., 0., 8.))
    for _ in range(60):
        advance_world(world, [(car, VehicleCommand(brake=1., direction=1))], substeps=2)
    assert car._chassis.isActive()
    assert car._park_quiet == 0
    assert car._chassis.getTransform().getPos().z > 6.


def test_automatic_normal_mode_keeps_complete_player_local_and_simulation_parallel(monkeypatch):
    monkeypatch.setattr('session.os.process_cpu_count', lambda: 16)
    session = Session(track='test', vehicle_config=CONFIG, physics_workers=None)
    try:
        assert session.physics_worker_count() == 0
        assert session.simulation._physics_workers is None
        session.set_driving_mode(DrivingMode.SIMULATION)
        assert session.physics_worker_count() == 9
    finally:
        session.stop_clock()
        session.simulation.close()
