"""同一Bullet世界的悬架射线；Box直接求面交点，其他形状沿用原生查询。"""

from dataclasses import dataclass

from panda3d.bullet import BulletBoxShape
from panda3d.core import Mat4, NodePath, Vec3


@dataclass(frozen=True)
class RayContact:
    node: object
    fraction: float
    point: tuple
    normal: tuple


def box_entry(start, end, half):
    """三轴区间求有限线段的入射面；内部起点不伪造新的入射接触。"""
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
    return (entry, normal) if 0. <= entry <= 1. else None


def suspension_rays(world, chassis, rays):
    """从现有刚体读取Box及变换，既修假交点，也覆盖原生漏报；不另建支撑世界。"""
    boxes = {}
    for body in world.getRigidBodies():
        if body == chassis or not body.isStatic() or body.getIntoCollideMask().isZero():
            continue
        shapes = body.getShapes()
        if shapes and all(isinstance(shape, BulletBoxShape) for shape in shapes):
            body_mat = NodePath(body).getNetTransform().getMat()
            parts = []
            for i, shape in enumerate(shapes):
                matrix = body.getShapeTransform(i).getMat() * body_mat
                inverse = Mat4()
                inverse.invertFrom(matrix)
                # Bullet射线支持函数使用含margin的Box外廓，不能改成无margin小盒。
                parts.append((tuple(shape.getHalfExtentsWithMargin()), inverse))
            boxes[body] = parts
    results = []
    for start, end in rays:
        hits = [RayContact(hit.getNode(), hit.getHitFraction(), tuple(hit.getHitPos()), tuple(hit.getHitNormal()))
                for hit in world.rayTestAll(start, end).getHits()
                if hit.getNode() != chassis and hit.getNode() not in boxes]
        for body, parts in boxes.items():
            for half, inverse in parts:
                found = box_entry(tuple(inverse.xformPoint(start)), tuple(inverse.xformPoint(end)), half)
                if found is None:
                    continue
                fraction, local_normal = found
                normal = Vec3(*(sum(inverse.getCell(a, b) * local_normal[b] for b in range(3)) for a in range(3)))
                normal.normalize()
                hits.append(RayContact(body, fraction, tuple(start + (end - start) * fraction), tuple(normal)))
        results.append(min(hits, key=lambda hit: hit.fraction) if hits else None)
    return tuple(results)
