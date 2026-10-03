"""同一车身沿CG投影分区：保留外廓与多点接触，平落地支撑经过CG。"""

from itertools import pairwise, product

from panda3d.bullet import BulletBoxShape
from panda3d.core import Mat4, TransformState, Vec3

from vehicle_config import body_center


def axis_intervals(low, high):
    boundaries = (low, 0, high) if low < 0 < high else (low, high)
    return tuple(pairwise(boundaries))


def chassis_shapes(config):
    half = Vec3(config.collision_half_width, config.collision_half_length, config.collision_half_height)
    center = Vec3(*body_center(config))
    if not config.centered_collision_support:
        return ((BulletBoxShape(half), TransformState.makePos(center)),)
    xs = axis_intervals(center.x-half.x, center.x+half.x)
    ys = axis_intervals(center.y-half.y, center.y+half.y)
    parts = []
    for (x_low, x_high), (y_low, y_high) in product(xs, ys):
        part_half = Vec3((x_high-x_low)/2, (y_high-y_low)/2, half.z)
        part_center = Vec3((x_high+x_low)/2, (y_high+y_low)/2, center.z)
        sx = -1 if part_center.x < 0 else 1
        sy = -1 if part_center.y < 0 else 1
        shape = BulletBoxShape(part_half)
        # 无margin实体覆盖名义Box；CG在外廓外时不增加切面或支撑。
        shape.setMargin(0)
        matrix = Mat4(Mat4.identMat())
        # 指定符号旋转，让向下平面的等值支撑角点靠近CG投影。
        matrix.setCell(0, 0, -sx)
        matrix.setCell(1, 1, -sy)
        matrix.setCell(2, 2, sx*sy)
        matrix.setRow(3, (part_center.x, part_center.y, part_center.z, 1))
        parts.append((shape, TransformState.makeMat(matrix)))
    return tuple(parts)


def install_chassis_shape(body, config):
    """分区前读原Box惯量，保持机械参数与配置一致。"""
    original = BulletBoxShape(Vec3(config.collision_half_width, config.collision_half_length,
                                  config.collision_half_height))
    body.addShape(original, TransformState.makePos(Vec3(*body_center(config))))
    inertia = body.getInertia()
    if config.centered_collision_support:
        body.removeShape(original)
        for shape, transform in chassis_shapes(config):
            body.addShape(shape, transform)
        body.setInertia(inertia)
    if config.body_inertia is not None:
        body.setInertia(Vec3(*config.body_inertia))
