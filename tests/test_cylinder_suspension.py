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
from triangle_support import TriangleSupport
from wheel_envelope import (
    _triangle,
    convex_distance,
    convex_polygon_distance,
    cylinder_box_distance,
    cylinder_support,
)
from wheel_geometry import contact_geometry


def test_low_speed_cross_face_extension_matches_independent_plane_intersection():
    slope, radius, dt = 1 / 1024, .33, 1 / 120
    origin = (100., 70., 2.)
    points = ((-2., -2., 0.), (2., -2., 0.), (-2., 0., 0.), (2., 0., 0.),
              (-2., 2., 2*slope), (2., 2., 2*slope))
    triangles = tuple(tuple(tuple(origin[a]+points[i][a] for a in range(3)) for i in indices)
                      for indices in ((0, 1, 2), (1, 3, 2), (2, 3, 4), (3, 5, 4)))
    surface = CylinderSurface((), 0., ((1.,0.,0.), (0.,1.,0.), (0.,0.,1.)),
        origin, radius, .6, .205, .01, (1.,0.,0.), crown=.003, triangles=TriangleSupport.build(triangles))
    y = -radius*slope/2 - 1e-6
    hub, direction = (.2, y, .7), (0.,0.,-1.)
    found = surface.entry(surface.local((hub[0], hub[1], hub[2]+radius)),
                          surface.local((hub[0], hub[1], hub[2]-.6)), surface.wheel_axis)
    fraction, normal, point, _face = found
    assert normal == (0.,0.,1.)
    plane = SupportPlane(hub, direction, normal, -radius+fraction*(radius+.6), surface,
                         tuple(point[a]-origin[a] for a in range(3)))
    system = SuspensionInput((.03,)*4, (.03,)*4, ((0.,)*6,)*4, (True,)*4, (1.,)*4, None, (plane,)*4)
    gradients = []
    for vy in (.0012-1e-12, .0012, .0012+1e-12):
        velocity = (0., vy, 0.)
        actual = finite_contact_system(system, velocity, (0.,)*3, dt)
        work = dt*sum(g*v for g,v in zip(actual.gradients[0], velocity+(0.,)*3))
        # 末支持面z=s*y，轮轴沿x；独立高精度平面高度给出有限胎冠的支撑行程。
        with localcontext() as context:
            context.prec = 60
            s, r = Decimal.from_float(slope), Decimal.from_float(radius)
            end_y = Decimal.from_float(y)+Decimal.from_float(dt)*Decimal.from_float(vy)
            expected = float(Decimal.from_float(hub[2])-s*end_y-r*(1+s*s).sqrt()
                             -Decimal.from_float(plane.length))
        assert work == pytest.approx(expected, rel=0., abs=2e-16)
        assert actual.touching == (True,)*4
        gradients.append(actual.gradients[0])
    assert max(abs(a-b) for a,b in zip(gradients[0], gradients[-1])) < 1e-10


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


def test_polygon_distance_checks_current_face_edge_and_opposite_side():
    polygon = ((-1., -1., 0.), (1., -1., 0.), (1., 1., 0.), (-1., 1., 0.))
    for center in ((1.3, 1.2, .8), (.7, .2, 1.1), (-1.4, -1.2, .7), (0., 1.3, .9)):
        dx = max(abs(center[0]) - 1. - .0925, 0.)
        dy = max(abs(center[1]) - 1., 0.)
        radial_gap = max(math.hypot(dy, center[2]) - .32, 0.)
        expected = math.hypot(dx, radial_gap)
        distance, normal, point = convex_polygon_distance(
            center, (1., 0., 0.), polygon, .33, .1025, .01, 0.)
        assert distance == pytest.approx(expected, abs=2e-10)
        assert sum(n*n for n in normal) == pytest.approx(1., abs=2e-12)
        assert abs(point[0]) <= 1. + 1e-12 and abs(point[1]) <= 1. + 1e-12
        assert point[2] == 0.


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


def test_captured_finite_coastal_face_matches_high_precision_profile_extent():
    center = (-93.05844027821882, 28.190793624421552, 6.316604717301158)
    axis = (-0.9499677633195276, -0.3123054792652478, -0.005151337166024413)
    polygon = ((-93.26712958881015, 28.0644303113319, 5.302476043023418),
               (-92.85155395674252, 28.561646462325694, 5.312669994825364),
               (-92.85155395674252, 28.387922700622653, 5.307924046279813),
               (-93.26712958881015, 28.561646462325694, 5.316059459854257))
    # 70位静态面方程加抛物胎冠的解析最大高度，不用生产距离查询。
    with localcontext() as context:
        context.prec = 70
        a, b, c = (tuple(Decimal.from_float(x) for x in p) for p in polygon[:3])
        ab, ac = tuple(y-x for x, y in zip(a, b)), tuple(y-x for x, y in zip(a, c))
        normal = tuple(ab[i]*ac[j] - ab[j]*ac[i] for i, j in ((1, 2), (2, 0), (0, 1)))
        norm = sum(n*n for n in normal).sqrt()
        normal = tuple(n/norm for n in normal)
        if sum(n*(Decimal.from_float(x)-y) for n, x, y in zip(normal, center, a)) < 0:
            normal = tuple(-n for n in normal)
        axial = sum(n*Decimal.from_float(u) for n, u in zip(normal, axis))
        radial = (1 - axial*axial).sqrt()
        radius, half, crown = Decimal(".32"), Decimal(".0925"), Decimal(".003")
        q = max(-half, min(half, axial*half*half / (2*crown*radial)))
        extent = q*axial + radial*(radius - crown*(q/half)**2)
        expected = float(sum(n*(Decimal.from_float(x)-y) for n, x, y in zip(normal, center, a)) - extent)
        expected_normal = tuple(float(n) for n in normal)
    distance, normal, _point = convex_distance(center, axis,
        lambda d: max(polygon, key=lambda p: sum(x*y for x, y in zip(p, d))), .33, .1025, .01, .003)
    assert distance == pytest.approx(expected, rel=0., abs=1e-14)
    assert normal == pytest.approx(expected_normal, rel=0., abs=1e-14)


def test_rotated_cap_keeps_axial_extent_and_actual_corner_distance():
    axis = (.9398454188243761, -.34157626571707533, .004030311850328373)
    norm = math.sqrt(math.fsum(x*x for x in axis))
    unit = tuple(x/norm for x in axis)
    # 此轴的范数平方比1少一个舍入位；真实端面不能把该误差解释成胎径。
    for sign in (-1., 1.):
        offset = cylinder_support(tuple(sign*x for x in axis), axis, .33, .1025, .01, .003)
        extent = math.fsum(x*u for x, u in zip(offset, unit))
        assert sign*extent == pytest.approx(.1025, rel=0., abs=2e-15)
        assert offset == pytest.approx(tuple(sign*.1025*u for u in unit), rel=0., abs=2e-15)
    center = (99.08800894185853, 14.050510012143128, .047717814869382646)
    corner = (99.3, 14.120750419027639, -.046897439629641796)
    relative = tuple(x-y for x, y in zip(corner, center))
    axial = math.fsum(x*u for x, u in zip(relative, unit))
    radial = math.sqrt(math.fsum((relative[i]-axial*unit[i])**2 for i in range(3)))
    assert radial < .32-.003
    distance, normal, point = convex_distance(center, axis, lambda _d: corner, .33, .1025, .01, .003)
    assert distance == pytest.approx(axial-.0925, rel=0., abs=2e-15)
    assert normal == pytest.approx(tuple(-u for u in unit), rel=0., abs=2e-15)
    assert point == corner


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
    for a in (-1e-5, 0., 1e-5):
        normal = (a, 0., math.sqrt(1-a*a))
        offset = cylinder_support(normal, (1.,0.,0.), .33, .1025, .01, .003)
        assert abs(offset[0]) < .00002
        _axis, _frame, radius, _moment = contact_geometry((1.,0.,0.), normal, (0.,0.,-.33), .33,
                                                        width=.205, shoulder=.01, crown=.003)
        expected = .32 - .003 * ((offset[0] - .01*a) / .0925)**2 + .01*math.sqrt(1-a*a)
        assert radius == pytest.approx(expected, abs=1e-14)
