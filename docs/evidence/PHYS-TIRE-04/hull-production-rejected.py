"""车身凸体的原生Bullet碰撞表示；面和边支撑不预选某一侧角点。"""

from itertools import product

from panda3d.bullet import BulletBoxShape, BulletConvexHullShape
from panda3d.core import TransformState, Vec3

from vehicle_config import body_center


def chassis_shape(config):
    half = (config.collision_half_width, config.collision_half_length, config.collision_half_height)
    original = BulletBoxShape(Vec3(*half))
    if not config.centered_collision_support:
        return original
    shape = BulletConvexHullShape()
    # 保留Box的内核和圆角margin；通用GJK支持函数与外廓不变。
    inner = original.getHalfExtentsWithoutMargin()
    shape.setMargin(original.getMargin())
    points = (point for point in product((-1, 0, 1), repeat=3) if point != (0, 0, 0))
    # 冗余面/边中点不改变凸包。等支撑值时先给对称中点，实际倾斜仍选择角点。
    for point in sorted(points, key=lambda point: sum(value != 0 for value in point)):
        shape.addPoint(Vec3(*(inner[axis]*point[axis] for axis in range(3))))
    return shape


def install_chassis_shape(body, config):
    """支撑表示替换前读原Box惯量，避免凸包AABB近似额外增大车身惯量。"""
    original = BulletBoxShape(Vec3(config.collision_half_width, config.collision_half_length,
                                  config.collision_half_height))
    transform = TransformState.makePos(Vec3(*body_center(config)))
    body.addShape(original, transform)
    inertia = body.getInertia()
    if config.centered_collision_support:
        body.removeShape(original)
        body.addShape(chassis_shape(config), transform)
        body.setInertia(inertia)
    if config.body_inertia is not None:
        body.setInertia(Vec3(*config.body_inertia))
