"""真实碰撞的外廓、对称落地与非对称冲量；不修改运行中的姿态或速度。"""

import math
from dataclasses import replace
from itertools import pairwise, product

import pytest
from panda3d.bullet import (
    BulletBoxShape,
    BulletPlaneShape,
    BulletRigidBodyNode,
    BulletSphereShape,
    BulletWorld,
)
from panda3d.core import TransformState, Vec3
from physics import esc_probe

from driving_modes import REFERENCE_CAR, DrivingMode
from simulation import Simulation
from vehicle import Vehicle
from vehicle_collision import chassis_shapes, install_chassis_shape
from vehicle_config import CAR, body_center
from vehicle_state import FIXED_DT


@pytest.mark.parametrize("hpr", [(0, 0, 0), (37, 12, -9)])
@pytest.mark.parametrize("config", [CAR, replace(CAR, collision_half_width=1.2, collision_half_height=.5,
                                               center_of_mass_height=.6, front_weight_share=.6),
                                   replace(CAR, wheelbase=6, front_weight_share=.9)])
def test_actual_contact_distances_match_complete_nominal_box_in_body_frame(hpr, config):
    world = BulletWorld()
    car = Vehicle(world, lambda _x, _y: True, (7, 13, 3), config=config)
    try:
        car._chassis.setTransform(TransformState.makePosHpr(Vec3(7, 13, 3), Vec3(*hpr)))
        pose = car._chassis.getTransform()
        center = pose.getMat().xformPoint(Vec3(*body_center(config)))
        half = (config.collision_half_width, config.collision_half_length, config.collision_half_height)
        sphere = BulletRigidBodyNode("geometry-probe")
        sphere.addShape(BulletSphereShape(.05))
        world.attachRigidBody(sphere)
        directions = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                      (1, 1, 1), (-1, 1, -1), (1, -2, .5))
        for values in directions:
            direction = Vec3(*values).normalized()
            distance = min(half[i]/abs(direction[i]) for i in range(3) if direction[i] != 0)
            axis = pose.getQuat().xform(direction)
            # 原生接触距离核对SDF；Bullet默认射线的dist²停止尺度为1e-4，不适合20微米几何核对。
            # 复合体内部的各子体穿透距离不是整体SDF；从外侧核对实际外表面。
            for offset in (.02, .04):
                local_point = direction*(distance+offset)
                expected = math.sqrt(sum(max(abs(local_point[i])-half[i], 0)**2 for i in range(3)))-.05
                sphere.setTransform(TransformState.makePos(center+axis*(distance+offset)))
                contacts = world.contactTestPair(car._chassis, sphere).getContacts()
                assert contacts
                actual = min(contact.getManifoldPoint().getDistance() for contact in contacts)
                assert actual == pytest.approx(expected, abs=2e-5)
    finally:
        car.close()


@pytest.mark.parametrize("config", [CAR, replace(CAR, center_of_mass_height=.6, front_weight_share=.6),
                                   replace(CAR, wheelbase=6, front_weight_share=.9),
                                   replace(CAR, wheelbase=6, front_weight_share=.1)])
def test_native_partitions_fill_the_nominal_box_without_gaps_or_extra_volume(config):
    limits = []
    for shape, pose in chassis_shapes(config):
        half = shape.getHalfExtentsWithMargin()
        points = [pose.getMat().xformPoint(Vec3(*(half[i]*sign[i] for i in range(3))))
                  for sign in product((-1, 1), repeat=3)]
        limits.append(tuple((min(p[i] for p in points), max(p[i] for p in points)) for i in range(3)))
    nominal = (config.collision_half_width, config.collision_half_length, config.collision_half_height)
    center = body_center(config)
    for axis in range(3):
        assert min(part[axis][0] for part in limits) == pytest.approx(center[axis]-nominal[axis], abs=2e-5)
        assert max(part[axis][1] for part in limits) == pytest.approx(center[axis]+nominal[axis], abs=2e-5)
    assert sum(math.prod(high-low for low, high in part) for part in limits) == pytest.approx(
        math.prod(2*value for value in nominal), rel=1e-6)
    for a in range(len(limits)):
        for b in range(a+1, len(limits)):
            overlap = [min(limits[a][i][1], limits[b][i][1])-max(limits[a][i][0], limits[b][i][0]) for i in range(3)]
            assert min(overlap) <= 2e-5


@pytest.mark.parametrize("config", [CAR, REFERENCE_CAR])
@pytest.mark.parametrize("front_share", [.4, .5, .6])
def test_flat_native_impact_supports_the_actual_cg_without_spurious_rotation(config, front_share):
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("cg-plane")
    ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
    body = BulletRigidBodyNode("cg-body")
    body.setMass(config.mass)
    install_chassis_shape(body, replace(config, front_weight_share=front_share))
    body.setDeactivationEnabled(False)
    body.setTransform(TransformState.makePos(Vec3(0, 0, 2.5)))
    world.attachRigidBody(ground)
    world.attachRigidBody(body)
    impacts = []
    for _ in range(240):
        world.doPhysics(FIXED_DT, 0, FIXED_DT)
        assert max(abs(value) for value in body.getTransform().getHpr()) < .001
        for manifold in world.getManifolds():
            for point in manifold.getManifoldPoints():
                if point.getAppliedImpulse() > 0:
                    position = point.getPositionWorldOnA() if manifold.getNode0() == body else point.getPositionWorldOnB()
                    impacts.append(position)
    assert impacts
    assert abs(impacts[0].x) < 2e-5
    assert abs(impacts[0].y) < 2e-5


@pytest.mark.parametrize("front_share", [.1, .9])
def test_cg_outside_body_keeps_real_edge_support_and_tipping(front_share):
    config = replace(REFERENCE_CAR, wheelbase=6, front_weight_share=front_share)
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("outside-cg-plane")
    ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
    body = BulletRigidBodyNode("outside-cg-body")
    body.setMass(config.mass)
    install_chassis_shape(body, config)
    assert body.getNumShapes() == 2
    body.setDeactivationEnabled(False)
    body.setTransform(TransformState.makePos(Vec3(0, 0, 2.5)))
    world.attachRigidBody(ground)
    world.attachRigidBody(body)
    for _ in range(120):
        world.doPhysics(FIXED_DT, 0, FIXED_DT)
        points = [point for manifold in world.getManifolds() for point in manifold.getManifoldPoints()
                  if point.getAppliedImpulse() > 0]
        if points:
            expected_y = body_center(config)[1]+(config.collision_half_length if front_share > .5
                                                else -config.collision_half_length)
            manifold = next(m for m in world.getManifolds() if any(p.getAppliedImpulse() > 0
                                                                 for p in m.getManifoldPoints()))
            position = points[0].getPositionWorldOnA() if manifold.getNode0() == body else points[0].getPositionWorldOnB()
            assert position.y == pytest.approx(expected_y, abs=2e-5)
            assert abs(body.getAngularVelocity().x) > .1
            assert body.getAngularVelocity().x*expected_y > 0
            break
    else:
        pytest.fail("Body never contacted its real supporting edge")


def test_legacy_shape_and_reference_inertia_are_explicit():
    assert len(chassis_shapes(replace(CAR, centered_collision_support=False))) == 1
    assert len(chassis_shapes(CAR)) == 4
    assert all(isinstance(shape, BulletBoxShape) for shape, _pose in chassis_shapes(CAR))
    world = BulletWorld()
    car = Vehicle(world, lambda _x, _y: True, (0, 0, 3), config=REFERENCE_CAR)
    try:
        assert tuple(car._chassis.getInertia()) == pytest.approx(REFERENCE_CAR.body_inertia)
        assert all(car._chassis.getShape(i).getMargin() == 0 for i in range(4))
    finally:
        car.close()


@pytest.mark.parametrize("config", [CAR, REFERENCE_CAR,
                                   replace(CAR, collision_half_width=1.2, collision_half_height=.5),
                                   replace(CAR, front_weight_share=.6),
                                   replace(CAR, wheelbase=6, front_weight_share=.9)])
def test_support_representation_preserves_the_original_native_inertia(config):
    world = BulletWorld()
    legacy = Vehicle(world, lambda _x, _y: True, (0, 0, 3),
                     config=replace(config, centered_collision_support=False))
    candidate = Vehicle(world, lambda _x, _y: True, (0, 0, 3), config=config)
    try:
        assert tuple(candidate._chassis.getInertia()) == tuple(legacy._chassis.getInertia())
    finally:
        candidate.close()
        legacy.close()


def test_symmetric_airborne_braking_preserves_symmetry_as_tire_step_refines():
    trials = [esc_probe.run_trial("airborne-recontact", True, 6, "simulation",
              vehicle_config=replace(REFERENCE_CAR, tire_substeps=steps))[0] for steps in (2, 4, 8, 16)]
    for trial in trials:
        assert trial["peak_abs_unwrapped_heading_deg"] < .001
        assert trial["esc_active_seconds"] == 0
        assert trial["stopped"]
    differences = [abs(b["path_distance_m"]-a["path_distance_m"]) for a, b in pairwise(trials)]
    assert differences[2] < differences[1] < differences[0]
    assert abs(trials[-1]["time_to_stop_s"]-trials[-2]["time_to_stop_s"]) <= FIXED_DT


@pytest.mark.parametrize("roll", [-5, 5])
def test_actual_tilted_impact_keeps_off_center_contact_and_rotation(roll):
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -9.81))
    ground = BulletRigidBodyNode("impact-plane")
    ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
    body = BulletRigidBodyNode("tilted-body")
    body.setMass(REFERENCE_CAR.mass)
    install_chassis_shape(body, REFERENCE_CAR)
    body.setDeactivationEnabled(False)
    body.setTransform(TransformState.makePosHpr(Vec3(0, 0, 2.5), Vec3(0, 0, roll)))
    body.setLinearVelocity(Vec3(0, 20, 0))
    world.attachRigidBody(ground)
    world.attachRigidBody(body)
    found = False
    for _ in range(120):
        world.doPhysics(FIXED_DT, 0, FIXED_DT)
        for manifold in world.getManifolds():
            for point in manifold.getManifoldPoints():
                if point.getAppliedImpulse() > 0:
                    position = point.getPositionWorldOnA() if manifold.getNode0() == body else point.getPositionWorldOnB()
                    assert abs(position.x) > .5
                    assert abs(body.getAngularVelocity().y) > .1
                    assert math.isfinite(body.getAngularVelocity().length())
                    found = True
        if found:
            break
    assert found


@pytest.mark.parametrize("mode", list(DrivingMode))
def test_player_npc_reset_keep_the_same_native_collision_representation(mode):
    sim = Simulation(track="coastal", traffic_count=1, config=mode.vehicle_config)
    try:
        for car in (sim.player, *sim.npcs):
            assert car.config.centered_collision_support
            shapes = tuple(car._chassis.getShape(i) for i in range(car._chassis.getNumShapes()))
            assert len(shapes) == 4 and all(isinstance(shape, BulletBoxShape) for shape in shapes)
            car.reset(car.spawn)
            assert tuple(car._chassis.getShape(i) for i in range(4)) == shapes
    finally:
        sim.close()
