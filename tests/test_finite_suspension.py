"""独立末姿态平面交点、离散虚功及实际Bullet转动路径。"""

import math

import numpy as np
import pytest
from panda3d.bullet import BulletRigidBodyNode, BulletSphereShape, BulletWorld
from panda3d.core import Vec3

from suspension import SuspensionInput
from suspension_kinematics import SupportPlane, finite_contact_system, rotated_path, rotation_path


def endpoint_length(plane, velocity, angular, dt, damping=0.):
    """独立Rodrigues矩阵后按末姿态的球心/平面交点求长度；常规角度不触及原生限制。"""
    spin = np.asarray(angular) * (1 - damping)**dt * dt
    theta = np.linalg.norm(spin)
    rotation = np.eye(3)
    if theta:
        x, y, z = spin / theta
        skew = np.array(((0., -z, y), (z, 0., -x), (-y, x, 0.)))
        rotation += math.sin(theta) * skew + (1 - math.cos(theta)) * (skew @ skew)
    n = np.asarray(plane.normal)
    a0 = -n @ np.asarray(plane.direction)
    a1 = -n @ (rotation @ np.asarray(plane.direction))
    p1 = a0 * plane.length + n @ (dt * np.asarray(velocity) + rotation @ np.asarray(plane.hub) - np.asarray(plane.hub))
    return p1 / a1


@pytest.mark.parametrize("bank", (-55., 0., 60.))
@pytest.mark.parametrize("angular", ((0., 0., 0.), (4., -.7, .3), (-3., 1., -2.)))
@pytest.mark.parametrize("dt", (1/120, 1/240))
@pytest.mark.parametrize("damping", (0., .2))
def test_finite_length_difference_equals_six_dimensional_conjugate_work(bank, angular, dt, damping):
    angle = math.radians(bank)
    plane = SupportPlane((-.84, 1.2, .23), (math.sin(angle), 0., -math.cos(angle)), (0., 0., 1.), .34)
    system = SuspensionInput((.06,) * 4, (.06,) * 4, ((0.,) * 6,) * 4,
                             (True,) * 4, (math.cos(angle),) * 4, None, (plane,) * 4, damping)
    velocity = (.7, 2., -.2)
    actual = finite_contact_system(system, velocity, angular, dt)
    length = endpoint_length(plane, velocity, angular, dt, damping)
    work = dt * sum(a * b for a, b in zip(actual.gradients[0], velocity + angular))
    assert work == pytest.approx(length - plane.length, abs=2e-15)
    # 法向线冲量仍沿真实法线；平移不会引入额外的路面切向支撑。
    assert actual.gradients[0][:2] == (0., 0.)
    assert all(actual.touching)


@pytest.mark.parametrize("angular", ((0., 0., 0.), (.0001, -.0002, .0003), (4., -.7, .3), (300., 90., -30.)))
@pytest.mark.parametrize("damping", (0., .2))
def test_rotation_path_matches_actual_native_bullet_transform(angular, damping):
    world = BulletWorld()
    world.setGravity(Vec3(0))
    body = BulletRigidBodyNode("isotropic-rotation-test")
    body.setMass(1.)
    body.setAngularDamping(damping)
    body.addShape(BulletSphereShape(.1))
    body.setAngularVelocity(Vec3(*angular))
    world.attachRigidBody(body)
    dt, vector = 1/120, (.3, -.7, .2)
    native_angular = tuple(body.getAngularVelocity())
    axis, theta, scale = rotation_path(native_angular, dt, body.getAngularDamping())
    expected, average = rotated_path(vector, axis, theta, scale)
    world.doPhysics(dt, 0, dt)
    actual = tuple(body.getTransform().getQuat().xform(Vec3(*vector)))
    assert actual == pytest.approx(expected, abs=3e-7)
    transport = np.asarray(expected) - vector
    assert transport == pytest.approx(dt * np.cross(native_angular, average), abs=2e-15)


def test_endpoint_leaving_grazing_support_uses_free_wheel_equation():
    angle = math.radians(83.)
    plane = SupportPlane((-.84, 1.2, .23), (math.sin(angle), 0., -math.cos(angle)), (0., 0., 1.), .34)
    system = SuspensionInput((.06,) * 4, (.06,) * 4, ((0.,) * 6,) * 4,
                             (True,) * 4, (math.cos(angle),) * 4, None, (plane,) * 4)
    result = finite_contact_system(system, (0.,) * 3, (0., -5., 0.), 1/120)
    assert result.touching == (False,) * 4
    assert result.gradients == ((0.,) * 6,) * 4
