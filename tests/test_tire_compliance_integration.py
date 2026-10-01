"""真实Bullet四轮变形、坐标生命周期与坡停的物理观测。"""

import math
from dataclasses import replace

import pytest
from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import Vec3

from driver_assist import SIMULATION_INPUT
from simulation import Control, Simulation
from tire_compliance import deformation_frame, project_deformation, world_deformation
from vehicle import Vehicle
from vehicle_config import CAR
from vehicle_state import FIXED_DT, VehicleCommand

CONFIG = replace(CAR, tire_compliance=True)


def test_real_strain_energy_shift_and_reset_lifecycle():
    sim = Simulation(track="test", traffic_count=0, config=CONFIG)
    try:
        for _ in range(240):
            sim.step(Control())
        for _ in range(120):
            sim.step(Control(throttle=1))
        car = sim.player
        state = car.snapshot()
        assert any(w.elastic_energy > .001 for w in state.wheel_dynamics)
        assert all(w.force_mode.startswith("compliant-") for w in state.wheel_dynamics)
        for index, wheel in enumerate(state.wheel_dynamics):
            expected = .5 * CONFIG.tire_contact_stiffness * sum(v * v for v in car.tires.deformation[index])
            assert wheel.elastic_energy == pytest.approx(expected, abs=1e-10)
        strain = list(car.tires.deformation)
        car.shift(2000)
        assert car.tires.deformation == strain
        car.reset((95, 0, 20))
        assert car.tires.deformation == [(0, 0, 0)] * 4
        assert all(w.elastic_energy == 0 for w in car.snapshot().wheel_dynamics)
        sim.step(Control())
        assert all(w.fx == w.fy == 0 for w in car.snapshot().wheel_dynamics)
    finally:
        sim.close()


def test_airborne_contact_force_zero_but_previous_strain_relaxes():
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    car = Vehicle(world, lambda x, y: True, (0, 0, 20), config=CONFIG)
    try:
        car.tires.deformation = [(.01, .02, 0)] * 4
        previous = car._chassis.getLinearVelocity()
        car.apply_command(VehicleCommand())
        world.doPhysics(FIXED_DT, 0, FIXED_DT)
        car.after_step(previous)
        state = car.snapshot()
        ratio = CONFIG.tire_contact_damping / (CONFIG.tire_contact_damping + CONFIG.tire_contact_stiffness * FIXED_DT / CONFIG.tire_substeps)
        for wheel in state.wheel_dynamics:
            assert wheel.fx == wheel.fy == wheel.road_dissipation == 0
            assert wheel.elastic_energy == pytest.approx(.5 * CONFIG.tire_contact_stiffness * .0005 * ratio ** (2 * CONFIG.tire_substeps))
            assert wheel.material_dissipation > 0
    finally:
        car.close()


def test_real_five_degree_slope_parking_balances_force_with_finite_strain():
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    slope = math.radians(5)
    ground = BulletRigidBodyNode("柔性轮胎坡停")
    ground.addShape(BulletPlaneShape(Vec3(0, -math.sin(slope), math.cos(slope)), 0))
    world.attachRigidBody(ground)
    car = Vehicle(world, lambda x, y: True, (0, 0, .55), pitch=5, config=CONFIG)
    try:
        def step():
            previous = car._chassis.getLinearVelocity()
            car.apply_command(VehicleCommand(brake=1))
            world.doPhysics(FIXED_DT, 0, FIXED_DT)
            car.after_step(previous)
        for _ in range(600):
            step()
        start = car.snapshot().position
        previous = start
        forces = []
        for _ in range(1200):
            step()
            state = car.snapshot()
            assert math.dist(state.position, previous) < .001
            forces.append(sum(w.longitudinal_impulse for w in state.wheel_dynamics) / FIXED_DT)
            previous = state.position
        assert math.dist(start, car.snapshot().position) < .01
        assert sum(forces) / len(forces) == pytest.approx(CONFIG.mass * 9.81 * math.sin(slope), rel=.01)
        assert all(w.force_mode == "compliant-sticking" and w.deformation_x > 0
                   for w in car.snapshot().wheel_dynamics)
    finally:
        car.close()


def test_single_precision_contact_axes_do_not_create_deformation_energy():
    previous = (.009, -.015, .002)
    before = .5 * CONFIG.tire_contact_stiffness * sum(v * v for v in previous)
    for _ in range(1000):
        frame = deformation_frame(tuple(Vec3(.1, .9, -.02).normalized()), tuple(Vec3(.02, .02, 1).normalized()))
        local, loss = project_deformation(previous, frame, CONFIG.tire_contact_stiffness)
        after = world_deformation(local, frame)
        energy = .5 * CONFIG.tire_contact_stiffness * sum(v * v for v in after)
        assert energy + loss == pytest.approx(before, abs=1e-11)
        previous, before = after, energy


@pytest.mark.parametrize("speed", [-.1, .1])
def test_real_low_speed_braking_settles_after_elastic_recoil(speed):
    sim = Simulation(track="test", traffic_count=0, config=CONFIG, input_config=SIMULATION_INPUT)
    try:
        for _ in range(240):
            sim.step(Control())
        car = sim.player
        car._chassis.setLinearVelocity(Vec3(0, speed, 0))
        car._chassis.setAngularVelocity(Vec3(0))
        car.tires.initialize_rolling(speed)
        for _ in range(120):
            sim.step(Control(brake=1))
        state = car.snapshot()
        assert abs(car.signed_speed()) < .01
        assert all(abs(w.relative_omega) < .01 for w in state.wheel_dynamics)
        assert all(w.force_mode == "compliant-sticking" for w in state.wheel_dynamics)
    finally:
        sim.close()
