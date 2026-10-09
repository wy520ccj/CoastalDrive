"""真实静态凸体的原Bullet数值查询；不创建世界，不积分或施力。"""

import math
from dataclasses import dataclass, field
from functools import lru_cache

from convex_cast_kernels import cast, hull
from panda3d.core import Quat, Vec3


def native_transform(pose):
    """复现Panda到Bullet的矩阵→四元数转换，保留单精度转换次序。"""
    pose = pose.setScale(1.)
    matrix = pose.getMat()
    rotation = Quat()
    rotation.setFromMatrix(matrix.getUpper3())
    return (*matrix.getRow3(3),rotation.getR(),rotation.getI(),rotation.getJ(),rotation.getK())


@dataclass(frozen=True)
class HullGeometry:
    vertices: tuple
    margin: float
    body_pose: tuple
    shape_pose: tuple
    native: object = field(init=False,repr=False,compare=False)

    def __post_init__(self):
        object.__setattr__(self,'native',hull(self.vertices,self.margin))

    def __reduce__(self):
        return type(self),(self.vertices,self.margin,self.body_pose,self.shape_pose)

    def entry(self, wheel, start, end, ceiling=1.):
        return cast(wheel,self.native,start,end,self.body_pose+self.shape_pose,ceiling)


@lru_cache(maxsize=32)
def wheel_hull(radius, width, shoulder, crown):
    """原17×64胎冠顶点完整保留，仅加速其支持顶点定位。"""
    if not crown:
        return None
    half = width / 2 - shoulder
    vertices = []
    for ring in range(17):
        x = half * (ring / 8 - 1)
        r = radius - shoulder - crown * (x / half)**2
        for segment in range(64):
            theta = 2 * math.pi * segment / 64
            vertices.append(tuple(Vec3(x,r*math.cos(theta),r*math.sin(theta))))
    return hull(tuple(vertices),shoulder,True)
