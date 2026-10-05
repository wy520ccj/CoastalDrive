"""同一Bullet世界的有限轮半径支撑包络；Box/Plane精确求交，网格用原生扫掠。"""

import math
from dataclasses import dataclass

from panda3d.bullet import BulletBoxShape, BulletPlaneShape, BulletSphereShape
from panda3d.core import BitMask32, Mat4, NodePath, TransformState

from suspension_geometry import BoxSurface, box_entry, sphere_box_entry


@dataclass(frozen=True)
class RayContact:
    node: object
    fraction: float
    point: tuple
    normal: tuple
    surface: BoxSurface | None = None


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
                surface = None
                if radius and isinstance(shape, BulletBoxShape):
                    axes = tuple(tuple(inverse.getCell(b, a) for b in range(3)) for a in range(3))
                    reach = math.sqrt(sum((end[a] - start[a])**2 for a in range(3))) - radius
                    surface = BoxSurface(tuple(shape.getHalfExtentsWithoutMargin()), radius + shape.getMargin(),
                                         axes, tuple(inverse.xformPoint(chassis.getTransform().getPos())), radius, reach)
                hits.append(RayContact(body, fraction, point, normal, surface))
        results.append(min(hits, key=lambda hit: hit.fraction) if hits else None)
    return tuple(results)
