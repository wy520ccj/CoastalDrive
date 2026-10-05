"""同一Bullet世界的有限轮半径支撑包络；Box/Plane精确求交，网格用原生扫掠。"""

import math
from dataclasses import dataclass
from itertools import pairwise

from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletSphereShape
from panda3d.core import BitMask32, Mat4, NodePath, TransformState


@dataclass(frozen=True)
class RayContact:
    node: object
    fraction: float
    point: tuple
    normal: tuple


def box_interval(start, end, half):
    """三轴区间给出直线进入/离开Box的时刻及入射面。"""
    entry, exit_time, normal = float("-inf"), float("inf"), None
    for axis in range(3):
        speed = end[axis] - start[axis]
        if speed == 0.:
            if abs(start[axis]) > half[axis]:
                return None
            continue
        near, far = (-half[axis] - start[axis]) / speed, (half[axis] - start[axis]) / speed
        sign = -1. if speed > 0. else 1.
        if near > far:
            near, far = far, near
        if near > entry:
            entry, normal = near, tuple(sign if i == axis else 0. for i in range(3))
        exit_time = min(exit_time, far)
        if entry > exit_time:
            return None
    return entry, exit_time, normal


def box_entry(start, end, half):
    """有限线段入射；内部起点不伪造新的入射接触。"""
    interval = box_interval(start, end, half)
    return (interval[0], interval[2]) if interval is not None and 0. <= interval[0] <= 1. else None


def sphere_box_entry(start, end, half, radius):
    """Box与球的Minkowski包络：面/圆柱棱/球角均按真实距离求首个交点。"""
    interval = box_interval(start, end, tuple(h + radius for h in half))
    if interval is None:
        return None
    low, high = max(0., interval[0]), min(1., interval[1])
    if low > high or sum(max(abs(x) - h, 0.) ** 2 for x, h in zip(start, half)) < radius * radius:
        return None
    speed = tuple(b - a for a, b in zip(start, end))
    knots = {low, high}
    for axis in range(3):
        if speed[axis] != 0.:
            for bound in (-half[axis], half[axis]):
                crossing = (bound - start[axis]) / speed[axis]
                if low < crossing < high:
                    knots.add(crossing)
    for left, right in pairwise(sorted(knots)):
        middle = tuple(start[a] + (left + right) * speed[a] / 2 for a in range(3))
        axes = [a for a in range(3) if abs(middle[a]) > half[a]]
        offsets = {a: start[a] - math.copysign(half[a], middle[a]) for a in axes}
        quadratic = sum(speed[a] ** 2 for a in axes)
        if quadratic == 0.:
            continue
        linear = sum(offsets[a] * speed[a] for a in axes)
        constant = sum(value * value for value in offsets.values()) - radius * radius
        discriminant = linear * linear - quadratic * constant
        if discriminant < 0.:
            continue
        entry = (-linear - math.sqrt(discriminant)) / quadratic
        if left - 1e-12 <= entry <= right + 1e-12:
            center = tuple(start[a] + entry * speed[a] for a in range(3))
            difference = tuple(center[a] - max(-half[a], min(half[a], center[a])) for a in range(3))
            length = math.sqrt(sum(value * value for value in difference))
            return entry, tuple(value / length for value in difference)
    return None


def suspension_rays(world, chassis, rays, radius=0.):
    """radius为设计参考车的球形支撑包络；查询不增加实体或改变刚体碰撞掩码。"""
    exact = {}
    mask = BitMask32.bit(0) if radius else BitMask32.allOn()
    for body in world.getRigidBodies():
        if body == chassis or not body.isStatic() or (body.getIntoCollideMask() & mask).isZero():
            continue
        shapes = body.getShapes()
        kinds = (BulletBoxShape, BulletPlaneShape) if radius else (BulletBoxShape,)
        if shapes and all(isinstance(shape, kinds) for shape in shapes):
            body_mat = NodePath(body).getNetTransform().getMat()
            parts = []
            for i, shape in enumerate(shapes):
                matrix = body.getShapeTransform(i).getMat() * body_mat
                inverse = Mat4()
                inverse.invertFrom(matrix)
                parts.append((shape, inverse))
            exact[body] = parts
    results = []
    envelope = BulletSphereShape(radius) if radius else None
    for start, end in rays:
        if radius:
            result = world.sweepTestClosest(envelope, TransformState.makePos(start), TransformState.makePos(end), mask, 0.)
            native = (result,) if result.hasHit() else ()
        else:
            native = world.rayTestAll(start, end, mask).getHits()
        hits = [RayContact(hit.getNode(), hit.getHitFraction(), tuple(hit.getHitPos()), tuple(hit.getHitNormal()))
                for hit in native if hit.getNode() != chassis and hit.getNode() not in exact]
        for body, parts in exact.items():
            for shape, inverse in parts:
                local_start, local_end = tuple(inverse.xformPoint(start)), tuple(inverse.xformPoint(end))
                if isinstance(shape, BulletPlaneShape):
                    n = shape.getPlaneNormal()
                    distance = sum(n[a] * local_start[a] for a in range(3)) - shape.getPlaneConstant() - radius
                    speed = sum(n[a] * (local_end[a] - local_start[a]) for a in range(3))
                    found = (-distance / speed, tuple(n)) if speed < 0. and distance >= 0. and distance + speed <= 0. else None
                elif radius:
                    found = sphere_box_entry(local_start, local_end, tuple(shape.getHalfExtentsWithoutMargin()), radius + shape.getMargin())
                else:
                    # 点射线仍沿用Bullet含margin的Box支持函数外廓。
                    found = box_entry(local_start, local_end, tuple(shape.getHalfExtentsWithMargin()))
                if found is None:
                    continue
                fraction, local_normal = found
                normal = tuple(sum(inverse.getCell(a, b) * local_normal[b] for b in range(3)) for a in range(3))
                norm = math.sqrt(sum(value * value for value in normal))
                normal = tuple(value / norm for value in normal)
                point = tuple(start[a] + (end[a] - start[a]) * fraction - normal[a] * radius for a in range(3))
                hits.append(RayContact(body, fraction, point, normal))
        results.append(min(hits, key=lambda hit: hit.fraction) if hits else None)
    return tuple(results)
