"""四块无margin原生Box覆盖名义外廓；平面等值支持点共用面中心。"""

from itertools import product

from panda3d.bullet import BulletBoxShape
from panda3d.core import Mat4, TransformState, Vec3

from vehicle_config import body_center


def install(body, config):
    original = BulletBoxShape(Vec3(config.collision_half_width, config.collision_half_length,
                                  config.collision_half_height))
    center = Vec3(*body_center(config))
    pose = TransformState.makePos(center)
    body.addShape(original, pose)
    inertia = body.getInertia()
    body.removeShape(original)
    half = Vec3(config.collision_half_width/2, config.collision_half_length/2,
                config.collision_half_height)
    for sx, sy in product((-1, 1), repeat=2):
        shape = BulletBoxShape(half)
        shape.setMargin(0)
        matrix = Mat4.identMat()
        matrix = Mat4(matrix)
        # 精确符号旋转使向下平面的等值支持角点落在共同的内侧中心。
        matrix.setCell(0, 0, -sx)
        matrix.setCell(1, 1, -sy)
        matrix.setCell(2, 2, sx*sy)
        matrix.setRow(3, (center.x+sx*half.x, center.y+sy*half.y, center.z, 1))
        body.addShape(shape, TransformState.makeMat(matrix))
    body.setInertia(Vec3(*config.body_inertia) if config.body_inertia is not None else inertia)
