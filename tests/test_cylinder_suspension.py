"""胎宽外廓、独立圆柱距离与有限转动行程功。"""

import math
from dataclasses import replace
from decimal import Decimal, localcontext

import pytest
from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import Vec3

from suspension import SuspensionInput
from suspension_contacts import cylinder_suspension_rays, suspension_rays
from suspension_geometry import CylinderSurface
from suspension_kinematics import SupportPlane, finite_contact_system, rotated_path, rotation_path
from wheel_envelope import _triangle, convex_distance, cylinder_box_distance
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
    radial = math.hypot(dy, dz)
    separation = (math.copysign(dx, center[0]), math.copysign(radial_gap*dy/radial, center[1]),
                  math.copysign(radial_gap*dz/radial, center[2]))
    assert normal == pytest.approx(tuple(x/expected for x in separation), abs=2e-10)
    assert sum(n*n for n in normal) == pytest.approx(1.)
    assert all(abs(x) <= h + 1e-12 for x, h in zip(point, half))


@pytest.mark.parametrize("translation", (0., 1000.))
def test_coastal_edge_distance_matches_independent_tread_profile(translation):
    # 来自固定种子海岸道路首败；直接在轮轴截面求极小值，不调用支持函数或GJK。
    center = (-93.59128693753293, 38.14708229635807, 6.613206726773421)
    edge = ((-93.73227429138764, 37.88618899224942, 5.60507505178071),
            (-93.45093234488934, 37.9972728574051, 5.608272651732814))
    axis = (-0.9960291170409282, -0.08901549207978816, -0.0014967219054136758)
    center = tuple(x + translation for x in center)
    edge = tuple(tuple(x + translation for x in p) for p in edge)

    def minimum(function, left, right):
        ratio = (math.sqrt(5) - 1) / 2
        a, b = right - ratio*(right-left), left + ratio*(right-left)
        fa, fb = function(a), function(b)
        for _ in range(80):
            if fa < fb:
                right, b, fb = b, a, fa
                a = right - ratio*(right-left)
                fa = function(a)
            else:
                left, a, fa = a, b, fb
                b = left + ratio*(right-left)
                fb = function(b)
        return min(fa, fb, function(left), function(right))

    def squared_distance(t):
        relative = tuple(edge[0][i] - center[i] + t*(edge[1][i]-edge[0][i]) for i in range(3))
        axial = sum(x*u for x, u in zip(relative, axis))
        radial = math.sqrt(sum((relative[i] - axial*axis[i])**2 for i in range(3)))
        return minimum(lambda q: (q-axial)**2 + max(radial - (.32-.003*(q/.0925)**2), 0.)**2,
                       -.0925, .0925)

    expected = math.sqrt(minimum(squared_distance, 0., 1.))
    distance, normal, witness = convex_distance(
        center, axis, lambda direction: max(edge, key=lambda p: sum(x*d for x, d in zip(p, direction))),
        .33, .1025, .01, .003)
    assert distance == pytest.approx(expected, abs=2e-10)
    assert sum(x*x for x in normal) == pytest.approx(1.)
    fraction = (witness[0]-edge[0][0]) / (edge[1][0]-edge[0][0])
    assert 0. <= fraction <= 1.
    assert witness == pytest.approx(tuple(edge[0][i] + fraction*(edge[1][i]-edge[0][i]) for i in range(3)),
                                    abs=2e-10)


def test_thin_coastal_simplex_projection_matches_high_precision_plane():
    a = (0.22642543179541563, 0.21745668623676456, 0.6948215273261817)
    b = (-0.054921498023231236, 0.10637085348793822, 0.6916238707360074)
    c = (-0.054920441139092, 0.1063701989570704, 0.6916240502594748)
    # 按实际双精度边向量定义平面，用70位十进制独立计算原点投影。
    with localcontext() as context:
        context.prec = 70
        ab = tuple(Decimal.from_float(y-x) for x, y in zip(a, b))
        ac = tuple(Decimal.from_float(y-x) for x, y in zip(a, c))
        normal = tuple(ab[i]*ac[j]-ab[j]*ac[i] for i, j in ((1, 2), (2, 0), (0, 1)))
        height = sum(n*Decimal.from_float(x) for n, x in zip(normal, a)) / sum(n*n for n in normal)
        expected = tuple(float(height*n) for n in normal)
    point, weights = _triangle(a, b, c)
    assert point == pytest.approx(expected, rel=0., abs=1e-15)
    assert all(w > 0. for w in weights)


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
