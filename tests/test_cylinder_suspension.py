"""胎宽外廓、独立圆柱距离与有限转动行程功。"""

import math
from dataclasses import replace

import pytest
from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import Vec3

from suspension import SuspensionInput
from suspension_contacts import cylinder_suspension_rays, suspension_rays
from suspension_geometry import CylinderSurface
from suspension_kinematics import SupportPlane, finite_contact_system, rotated_path, rotation_path
from wheel_envelope import cylinder_box_distance
from wheel_geometry import contact_geometry


@pytest.mark.parametrize("center", ((1.3, .4, .8), (1.2, 1.5, 1.4), (.7, .2, 1.1), (-1.4, -1.2, 1.7)))
def test_axial_cylinder_distance_matches_independent_product_geometry(center):
    half, radius, half_width, shoulder = (1., 1., .05), .33, .1025, .01
    dx = max(abs(center[0]) - half[0] - half_width + shoulder, 0.)
    dy, dz = max(abs(center[1]) - half[1], 0.), max(abs(center[2]) - half[2], 0.)
    radial_gap = max(math.hypot(dy, dz) - radius + shoulder, 0.)
    expected = math.hypot(dx, radial_gap)
    distance, normal, point = cylinder_box_distance(center, (1., 0., 0.), half, radius, half_width, shoulder)
    assert distance == pytest.approx(expected, abs=2e-10)
    assert sum(n*n for n in normal) == pytest.approx(1.)
    assert all(abs(x) <= h + 1e-12 for x, h in zip(point, half))


def test_finite_width_does_not_turn_nearby_rail_into_sphere_support():
    world = BulletWorld()
    rail = BulletRigidBodyNode("rail")
    shape = BulletBoxShape(Vec3(1., 10., .05))
    shape.setMargin(0.)
    rail.addShape(shape)
    world.attachRigidBody(rail)
    chassis = BulletRigidBodyNode("query")
    path = ((Vec3(1.2, 0., 1.), Vec3(1.2, 0., -.2)),)
    sphere, = suspension_rays(world, chassis, path, .33)
    cylinder, = cylinder_suspension_rays(world, chassis, path, ((1., 0., 0.),), .33, .205, .01)
    assert sphere is not None
    assert cylinder is None
    inside = ((Vec3(.9, 0., 1.), Vec3(.9, 0., -.2)),)
    contact, = cylinder_suspension_rays(world, chassis, inside, ((1., 0., 0.),), .33, .205, .01)
    assert contact.point[2] == pytest.approx(.05, abs=1e-7)
    assert contact.fraction == pytest.approx((1 - .05 - .33) / 1.2, abs=1e-7)


@pytest.mark.parametrize("bank", (0., .25, -.4))
def test_plane_query_accounts_for_real_axial_width_and_shoulder(bank):
    world = BulletWorld()
    body = BulletRigidBodyNode("bank")
    normal = Vec3(math.sin(bank), 0., math.cos(bank))
    body.addShape(BulletPlaneShape(normal, .1))
    world.attachRigidBody(body)
    path = ((Vec3(0., .2, 1.), Vec3(0., .2, -1.)),)
    hit, = cylinder_suspension_rays(world, BulletRigidBodyNode("query"), path, ((1., 0., 0.),), .33, .205, .01)
    extent = (.1025 - .01) * abs(math.sin(bank)) + (.33 - .01) * abs(math.cos(bank)) + .01
    assert hit.fraction == pytest.approx((math.cos(bank) - .1 - extent) / (2 * math.cos(bank)), abs=1e-7)
    assert sum(normal[i] * hit.point[i] for i in range(3)) == pytest.approx(.1, abs=1e-7)


def test_finite_cylinder_rotation_has_exact_plane_extension_work():
    surface = CylinderSurface((), 0., ((1.,0.,0.), (0.,1.,0.), (0.,0.,1.)),
                              (0.,0.,0.), .33, .6, .205, .01, (1.,0.,0.), ((0.,0.,1.), 0.))
    plane = SupportPlane((.8, 1., .7), (0.,0.,-1.), (0.,0.,1.), .37, surface, (.8,1.,0.))
    system = SuspensionInput((.03,)*4, (.03,)*4, ((0.,)*6,)*4, (True,)*4, (1.,)*4, None, (plane,)*4)
    velocity, angular, dt = (.2, 3., -.1), (.3, -.2, .1), 1/240
    result = finite_contact_system(system, velocity, angular, dt)
    axis, angle, scale = rotation_path(angular, dt)
    hub, _ = rotated_path(plane.hub, axis, angle, scale)
    direction, _ = rotated_path(plane.direction, axis, angle, scale)
    wheel_axis, _ = rotated_path(surface.wheel_axis, axis, angle, scale)
    # 独立支持函数：平面法线在轮轴与径向上的投影决定实际外廓高度。
    axial = abs(wheel_axis[2])
    extent = (.1025 - .01) * axial + (.33 - .01) * math.sqrt(1 - axial**2) + .01
    expected = (hub[2] + dt * velocity[2] - extent) / -direction[2]
    work_length = dt * sum(g*v for g,v in zip(result.gradients[0], velocity + angular))
    assert work_length == pytest.approx(expected - plane.length, abs=1e-14)
    at_rest = finite_contact_system(replace(system, angular_damping=.2), (0.,)*3, (0.,)*3, dt)
    assert at_rest.gradients[0] == pytest.approx((0.,0.,1.,1.,-.8,0.), abs=1e-12)


def test_crown_contact_is_continuous_and_mechanical_radius_uses_same_profile():
    from wheel_envelope import cylinder_support
    for a in (-1e-5, 0., 1e-5):
        normal = (a, 0., math.sqrt(1-a*a))
        offset = cylinder_support(normal, (1.,0.,0.), .33, .1025, .01, .003)
        assert abs(offset[0]) < .00002
        _axis, _frame, radius, _moment = contact_geometry((1.,0.,0.), normal, (0.,0.,-.33), .33,
                                                        width=.205, shoulder=.01, crown=.003)
        expected = .32 - .003 * ((offset[0] - .01*a) / .0925)**2 + .01*math.sqrt(1-a*a)
        assert radius == pytest.approx(expected, abs=1e-14)
