"""真实子步姿态、120Hz控制时钟、整拍机械账和早期子步碰撞。"""

from dataclasses import replace

import pytest
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode
from panda3d.core import BitMask32, TransformState, Vec3
from physics.reference_ab import _create_vehicle, _step

from driving_modes import DrivingMode
from simulation import Simulation
from tire_drivetrain import DrivetrainInput
from vehicle_state import FIXED_DT, VehicleCommand


def test_all_vehicle_states_are_read_before_solving_and_impulses_are_committed_afterward(monkeypatch):
    sim = Simulation(track="coastal", traffic_count=2, seed=17)
    events = []
    original_solve = DrivetrainInput.solve

    def trace(car):
        original_query, original_tires = car.suspension.prepare, car.tires.advance_stages

        def query(*args, **kwargs):
            events.append("read")
            return original_query(*args, **kwargs)

        def tires(*args, **kwargs):
            result = yield from original_tires(*args, **kwargs)
            events.append("commit")
            return result

        monkeypatch.setattr(car.suspension, "prepare", query)
        monkeypatch.setattr(car.tires, "advance_stages", tires)

    cars = (sim.player, *sim.npcs)
    for car in cars:
        trace(car)

    def solve(request):
        before = tuple((tuple(car._chassis.getLinearVelocity()), tuple(car._chassis.getAngularVelocity()),
                        car.tires.states, tuple(car.tires.omega)) for car in cars)
        events.append("solve")
        result = original_solve(request)
        after = tuple((tuple(car._chassis.getLinearVelocity()), tuple(car._chassis.getAngularVelocity()),
                       car.tires.states, tuple(car.tires.omega)) for car in cars)
        assert after == before
        return result

    monkeypatch.setattr(DrivetrainInput, "solve", solve)
    try:
        sim.step(VehicleCommand(throttle=.3, gear=1))
        assert events == (["read"] * 3 + ["solve"] * 3 + ["commit"] * 3) * 2
    finally:
        sim.close()


@pytest.mark.parametrize("mode", list(DrivingMode))
def test_actual_pose_advances_between_mechanics_with_one_control_tick(mode, monkeypatch):
    sim = Simulation(track="test", traffic_count=0, config=mode.vehicle_config, input_config=mode.input_config)
    car = sim.player
    poses, prepares, tire_parts = [], [], []
    original_query, original_prepare, original_tires = car.suspension.prepare, car.powertrain.prepare, car.tires.advance_stages

    def query(*args):
        poses.append(tuple(car._chassis.getTransform().getPos()))
        return original_query(*args)

    def prepare(*args, **kwargs):
        prepares.append(args)
        return original_prepare(*args, **kwargs)

    def tires(*args, **kwargs):
        result = yield from original_tires(*args, **kwargs)
        tire_parts.append(tuple(car.tires.states))
        return result

    monkeypatch.setattr(car.suspension, "prepare", query)
    monkeypatch.setattr(car.powertrain, "prepare", prepare)
    monkeypatch.setattr(car.tires, "advance_stages", tires)
    try:
        car._chassis.setLinearVelocity(Vec3(0, 12., 0))  # 一次性试验初速。
        car.tires.initialize_rolling(12.)
        sim.step(VehicleCommand(throttle=.3, steering=3., gear=1))
        state = sim.snapshot()
        assert len(poses) == 2 and poses[1][1] > poses[0][1] + .04
        assert len(prepares) == 1
        assert state.tick == state.player.contact_tick == state.player.suspension_state.force_tick == 1
        assert state.time == FIXED_DT
        suspension = state.player.suspension_state
        assert len(suspension.substeps) == 2
        assert sum(dt for dt, _step in suspension.substeps) == FIXED_DT
        assert suspension.step.body_work == sum(part.body_work for _dt, part in suspension.substeps)
        for first, final in zip(tire_parts[0], tire_parts[1]):
            assert final.longitudinal_impulse == pytest.approx(first.longitudinal_impulse + final.fx * FIXED_DT / 2, abs=1e-12)
            assert final.lateral_impulse == pytest.approx(first.lateral_impulse + final.fy * FIXED_DT / 2, abs=1e-12)
        assert all(w.force_contact_tick == 1 and w.force_residual < .001 for w in state.player.wheel_dynamics)
    finally:
        sim.close()


def test_external_force_is_integrated_for_the_complete_fixed_tick():
    config = replace(DrivingMode.SIMULATION.vehicle_config, drag_coefficient=0., rolling_coefficient=0.)
    world, car = _create_vehicle(config)
    try:
        world.setGravity(Vec3(0, 0, 0))
        car._chassis.setTransform(TransformState.makePos(Vec3(0, 0, 20)))
        car._chassis.applyCentralForce(Vec3(300, 0, 0))
        _step(world, car, VehicleCommand(gear=0))
        assert car._chassis.getLinearVelocity().x == pytest.approx(300 * FIXED_DT / config.mass, abs=1e-9)
        assert car.snapshot().contact_tick == 1
    finally:
        car.close()


def test_first_substep_impact_survives_contact_ending_before_final_substep(monkeypatch):
    sim = Simulation(track="test", traffic_count=0)
    wall = BulletRigidBodyNode("transient-wall")
    wall.addShape(BulletBoxShape(Vec3(.05, 3., 2.)))
    wall.setTransform(TransformState.makePos(Vec3(1.1, 0, 20)))
    wall.setIntoCollideMask(BitMask32.bit(1))
    sim._world.attachRigidBody(wall)
    calls = []
    original = sim._count_player_collisions

    def count():
        original()
        calls.append(sim.player_collisions)
        if len(calls) == 1:
            # 生命周期试验：第一子步真实碰撞后障碍物撤下，不能漏掉已发生的冲量。
            sim._world.removeRigidBody(wall)

    monkeypatch.setattr(sim, "_count_player_collisions", count)
    try:
        sim.player._chassis.setTransform(TransformState.makePos(Vec3(0, 0, 20)))
        sim.player._chassis.setLinearVelocity(Vec3(30, 0, 0))
        sim.step(VehicleCommand(gear=0))
        state = sim.snapshot()
        assert calls == [1, 1]
        assert len(state.impacts) == 1
        assert state.impacts[0].raw_impulse > 0.
        assert state.impacts[0].tick == 1
        assert state.contacts[0].contact_age_ticks == 1
    finally:
        sim.close()
