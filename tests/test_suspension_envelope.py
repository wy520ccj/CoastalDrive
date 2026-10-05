"""有限轮半径的面/棱/角几何与虚功；独立解析期望，不复用生产求交作期望。"""

import math

import numpy as np
import pytest
from panda3d.bullet import (
    BulletBoxShape,
    BulletPlaneShape,
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
    BulletWorld,
)
from panda3d.core import BitMask32, Vec3

from suspension import contact_gradient
from suspension_contacts import sphere_box_entry, suspension_rays


@pytest.mark.parametrize("point,normal", (
    ((0., 0., 1.), (0., 0., 1.)),
    ((1., 0., 1.), (1 / math.sqrt(2), 0., 1 / math.sqrt(2))),
    ((1., 1., 1.), (1 / math.sqrt(3),) * 3),
))
def test_sphere_first_entry_at_face_edge_corner(point, normal):
    radius = .33
    start = tuple(point[a] + .8 * normal[a] for a in range(3))
    end = tuple(point[a] - .2 * normal[a] for a in range(3))
    fraction, actual_normal = sphere_box_entry(start, end, (1.,) * 3, radius)
    center = tuple(start[a] + fraction * (end[a] - start[a]) for a in range(3))
    assert fraction == pytest.approx(.47, abs=1e-14)
    assert actual_normal == pytest.approx(normal, abs=1e-14)
    assert tuple(center[a] - radius * actual_normal[a] for a in range(3)) == pytest.approx(point, abs=1e-14)


def test_finite_footprint_detects_edge_missed_by_center_ray_and_has_continuous_normal():
    world = BulletWorld()
    body = BulletRigidBodyNode("platform")
    shape = BulletBoxShape(Vec3(1., 1., .05))
    shape.setMargin(0.)
    body.addShape(shape)
    world.attachRigidBody(body)
    for x in (.99, 1., 1.001, 1.05, 1.2):
        path = ((Vec3(x, 0., 1.), Vec3(x, 0., -.2)),)
        contact, = suspension_rays(world, BulletRigidBodyNode("chassis"), path, .33)
        dx = max(x - 1., 0.)
        dz = math.sqrt(.33 ** 2 - dx ** 2)
        assert contact.fraction == pytest.approx((1. - .05 - dz) / 1.2, abs=1e-7)
        assert contact.normal == pytest.approx((dx / .33, 0., dz / .33), abs=2e-7)
        assert contact.point == pytest.approx((min(x, 1.), 0., .05), abs=2e-7)
        if x > 1.:
            point_hit, = suspension_rays(world, BulletRigidBodyNode("chassis"), path)
            assert point_hit is None


def test_plane_sphere_point_and_oblique_length_match_actual_radius():
    world = BulletWorld()
    body = BulletRigidBodyNode("bank")
    n = Vec3(-.2, 0., 1.).normalized()
    body.addShape(BulletPlaneShape(n, .2))
    world.attachRigidBody(body)
    start, end = Vec3(0., .3, 1.), Vec3(0., .3, -1.)
    hit, = suspension_rays(world, BulletRigidBodyNode("chassis"), ((start, end),), .33)
    expected = (float(n.dot(start)) - .2 - .33) / -float(n.dot(end - start))
    assert hit.fraction == pytest.approx(expected, abs=1e-8)
    assert sum(n[a] * hit.point[a] for a in range(3)) == pytest.approx(.2, abs=1e-7)
    assert hit.normal == pytest.approx(tuple(n), abs=1e-7)
    assert tuple(start + (end - start) * hit.fraction) == pytest.approx(tuple(hit.point[a] + .33 * hit.normal[a] for a in range(3)), abs=1e-7)


def test_box_sphere_uses_native_core_and_margin_instead_of_expanded_sharp_corner():
    world = BulletWorld()
    body = BulletRigidBodyNode("box")
    shape = BulletBoxShape(Vec3(1., 1., 1.))
    shape.setMargin(.04)
    body.addShape(shape)
    world.attachRigidBody(body)
    start, end = Vec3(1.8, 0., 1.8), Vec3(.8, 0., .8)
    hit, = suspension_rays(world, BulletRigidBodyNode("chassis"), ((start, end),), .33)
    core, margin = shape.getHalfExtentsWithoutMargin().x, shape.getMargin()
    expected_center = core + (.33 + margin) / math.sqrt(2)
    expected_point = core + margin / math.sqrt(2)
    assert hit.fraction == pytest.approx((start.x - expected_center) / (start.x - end.x), abs=2e-8)
    assert hit.point == pytest.approx((expected_point, 0., expected_point), abs=1e-7)
    assert hit.normal == pytest.approx((1 / math.sqrt(2), 0., 1 / math.sqrt(2)), abs=1e-7)


def test_surface_query_mask_excludes_chassis_without_disabling_rigid_collision():
    world = BulletWorld()
    chassis = BulletRigidBodyNode("chassis")
    chassis.setMass(1200.)
    chassis.addShape(BulletBoxShape(Vec3(1.)))
    chassis.setIntoCollideMask(BitMask32.bit(1))
    world.attachRigidBody(chassis)
    body = BulletRigidBodyNode("ground")
    body.addShape(BulletPlaneShape(Vec3(0., 0., 1.), -1.))
    body.setIntoCollideMask(BitMask32(7))
    world.attachRigidBody(body)
    mask_before = chassis.getIntoCollideMask()
    hit, = suspension_rays(world, chassis, ((Vec3(0., 0., 2.), Vec3(0., 0., -2.)),), .33)
    assert hit.node == body
    assert hit.point[2] == pytest.approx(-1., abs=1e-7)
    assert chassis.getIntoCollideMask() == mask_before
    assert world.filterTest(chassis, body)


def test_native_triangle_mesh_sweep_detects_finite_radius_before_center_ray():
    world = BulletWorld()
    body = BulletRigidBodyNode("mesh-platform")
    mesh = BulletTriangleMesh()
    a, b, c, d = Vec3(-1., -1., 0.), Vec3(1., -1., 0.), Vec3(1., 1., 0.), Vec3(-1., 1., 0.)
    mesh.addTriangle(a, b, c)
    mesh.addTriangle(a, c, d)
    shape = BulletTriangleMeshShape(mesh, dynamic=False)
    shape.setMargin(0.)
    body.addShape(shape)
    world.attachRigidBody(body)
    path = ((Vec3(1.1, 0., 1.), Vec3(1.1, 0., -1.)),)
    point_hit, = suspension_rays(world, BulletRigidBodyNode("chassis"), path)
    sphere_hit, = suspension_rays(world, BulletRigidBodyNode("chassis"), path, .33)
    assert point_hit is None
    assert sphere_hit.node == body
    assert sphere_hit.point == pytest.approx((1., 0., 0.), abs=1e-5)
    # 原生扫掠按GJK阈值收敛；保留其实际几何误差，而非要求解析精度。
    assert sphere_hit.fraction == pytest.approx((1. - math.sqrt(.33 ** 2 - .1 ** 2)) / 2, abs=1e-4)


def test_spherical_edge_extension_gradient_matches_independent_virtual_work():
    origin = np.array([0., 0., .5])
    hub = np.array([1.5, .2, 1.5])
    direction = np.array([-1., 0., -1.]) / math.sqrt(2)
    edge = np.array([1., .2, 1.])
    radius = .33
    distance = np.linalg.norm(hub - edge) - radius
    center = hub + distance * direction
    normal = (center - edge) / radius
    gradient = np.array(contact_gradient(normal, direction, edge - origin))
    epsilon = 1e-7
    numerical = []
    for a in range(6):
        distances = []
        for sign in (-1., 1.):
            delta = np.eye(6)[a] * epsilon * sign
            rotation = delta[3:]
            moved_hub = hub + delta[:3] + np.cross(rotation, hub - origin)
            moved_direction = direction + np.cross(rotation, direction)
            difference = moved_hub - edge
            qa = moved_direction @ moved_direction
            qb = difference @ moved_direction
            qc = difference @ difference - radius * radius
            distances.append((-qb - math.sqrt(qb * qb - qa * qc)) / qa)
        numerical.append((distances[1] - distances[0]) / (2 * epsilon))
    assert gradient == pytest.approx(numerical, abs=2e-7)
