"""同一Bullet世界的轮胎支撑包络；Box/Plane/道路三角面求交，其他凸体原生扫掠。"""

import math
from dataclasses import dataclass

from panda3d.bullet import (
    BulletBoxShape,
    BulletConvexHullShape,
    BulletCylinderShape,
    BulletPlaneShape,
    BulletRigidBodyNode,
    BulletSphereShape,
    BulletTriangleMeshShape,
    XUp,
)
from panda3d.core import BitMask32, Mat4, NodePath, Quat, TransformState, Vec3

from suspension_geometry import BoxSurface, CylinderSurface, box_entry, sphere_box_entry


@dataclass(frozen=True)
class RayContact:
    node: object
    fraction: float
    point: tuple
    normal: tuple
    surface: BoxSurface | None = None
    support_face: tuple | None = None


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


def wheel_sweep_shape(radius, width, shoulder, crown):
    """创建一次网格扫掠外廓；车辆重建时才随硬件参数重建。"""
    envelope = BulletCylinderShape(radius, width, XUp)
    if crown:
        envelope = BulletConvexHullShape()
        half = width / 2 - shoulder
        # 17轴向截面、64圆周点；内接多边形最大径向偏差约0.39mm。
        for ring in range(17):
            x = half * (ring / 8 - 1)
            r = radius - shoulder - crown * (x / half)**2
            for segment in range(64):
                theta = 2 * math.pi * segment / 64
                envelope.addPoint(Vec3(x, r * math.cos(theta), r * math.sin(theta)))
    envelope.setMargin(shoulder)
    return envelope


def cylinder_suspension_rays(world, chassis, rays, axes, radius, width, shoulder, crown=0., *, envelope=None):
    """轮轴和有限胎宽进入真实表面查询；不会创建第二个物理世界。"""
    mask = BitMask32.bit(0)
    # 未加入世界的保守查询盒使用Bullet broadphase筛选实际相交静态物体。
    # 查询盒含整条轮心路径与轮胎外廓，不施力、不生成第二个物理世界。
    points = tuple(point for ray in rays for point in ray)
    padding = radius + width / 2 + 1e-5
    low = tuple(min(p[a] for p in points) - padding for a in range(3))
    high = tuple(max(p[a] for p in points) + padding for a in range(3))
    probe = BulletRigidBodyNode("suspension-query")
    shape = BulletBoxShape(Vec3(*( (b-a)/2 for a,b in zip(low,high))))
    shape.setMargin(0.)
    probe.addShape(shape)
    probe.setTransform(TransformState.makePos(Vec3(*((a+b)/2 for a,b in zip(low,high)))))
    bodies = set()
    for contact in world.contactTest(probe).getContacts():
        other = contact.getNode1() if contact.getNode0() == probe else contact.getNode0()
        if other != chassis and other.isStatic() and not (other.getIntoCollideMask() & mask).isZero():
            bodies.add(other)
    surfaces = []
    exact = set()
    for body in sorted(bodies,key=lambda node: (node.getName(),tuple(node.getTransform().getPos()))):
        shapes = body.getShapes()
        mesh = body.getPythonTag("suspension_mesh") if body.hasPythonTag("suspension_mesh") else None
        if shapes and all(isinstance(shape, (BulletBoxShape, BulletPlaneShape)) or (
                isinstance(shape, BulletTriangleMeshShape) and mesh is not None and len(shapes) == 1) for shape in shapes):
            exact.add(body)
            body_mat = NodePath(body).getNetTransform().getMat()
            for i, shape in enumerate(shapes):
                inverse = Mat4()
                inverse.invertFrom(body.getShapeTransform(i).getMat() * body_mat)
                frame = tuple(tuple(inverse.getCell(b, a) for b in range(3)) for a in range(3))
                plane = (tuple(shape.getPlaneNormal()), shape.getPlaneConstant()) if isinstance(shape, BulletPlaneShape) else None
                half = tuple(shape.getHalfExtentsWithoutMargin()) if isinstance(shape, BulletBoxShape) else ()
                triangles = mesh if isinstance(shape,BulletTriangleMeshShape) else None
                surfaces.append((body, inverse, frame, half, shape.getMargin() if plane is None else 0., plane, triangles))
    if envelope is None:
        envelope = wheel_sweep_shape(radius, width, shoulder, crown)
    native_needed = any(body not in exact for body in bodies)
    results = []
    for (start, end), axis in zip(rays, axes):
        axis = tuple(axis)
        transverse = math.hypot(axis[1], axis[2])
        rotation = Quat()
        if transverse:
            rotation_axis = Vec3(0., -axis[2] / transverse, axis[1] / transverse)
            rotation.setFromAxisAngleRad(math.atan2(transverse, axis[0]), rotation_axis)
        elif axis[0] < 0.:
            rotation.setFromAxisAngle(180., Vec3(0., 0., 1.))
        hits = []
        if native_needed:
            native = world.sweepTestClosest(envelope, TransformState.makePosQuatScale(start, rotation, Vec3(1)),
                                           TransformState.makePosQuatScale(end, rotation, Vec3(1)), mask, 0.)
            if native.hasHit() and native.getNode() != chassis and native.getNode() not in exact:
                hits.append(RayContact(native.getNode(), native.getHitFraction(), tuple(native.getHitPos()), tuple(native.getHitNormal())))
        for body, inverse, frame, half, margin, plane, triangles in surfaces:
            reach = math.sqrt(sum((end[a] - start[a])**2 for a in range(3))) - radius
            origin = chassis.getTransform().getPos()
            offset = tuple(inverse.getCell(3, a) + sum(frame[a][b] * origin[b] for b in range(3)) for a in range(3))
            surface = CylinderSurface(half, margin, frame, offset,
                                      radius, reach, width, shoulder, axis, plane, crown, triangles)
            found = surface.entry(surface.local(tuple(start[a] - origin[a] for a in range(3))),
                                  surface.local(tuple(end[a] - origin[a] for a in range(3))), axis)
            if found is None:
                continue
            fraction, local_normal, local_point, face = found
            normal = surface.world_vector(local_normal)
            point = tuple(surface.world_vector(tuple(local_point[a] - surface.offset[a] for a in range(3)))[b]
                          + chassis.getTransform().getPos()[b] for b in range(3))
            hits.append(RayContact(body, fraction, point, normal, surface, face))
        results.append(min(hits, key=lambda hit: hit.fraction) if hits else None)
    return tuple(results)
