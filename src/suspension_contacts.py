"""同一Bullet世界的轮胎支撑包络；Box/Plane/道路三角面求交，其他凸体原生扫掠。"""

import math
from dataclasses import dataclass

from panda3d.bullet import (
    BulletBoxShape,
    BulletConvexHullShape,
    BulletCylinderShape,
    BulletPlaneShape,
    BulletSphereShape,
    BulletTriangleMeshShape,
    XUp,
)
from panda3d.core import BitMask32, Mat4, NodePath, Quat, TransformState, Vec3
from wheel_contact_kernels import (
    prepared_support_candidates,
    support_candidates,
    support_coefficients,
    surface_ray_hits,
)

from suspension_geometry import BoxSurface, CylinderSurface, box_entry, sphere_box_entry
from triangle_support import TriangleSupport, triangle_entry
from wheel_envelope import cylinder_box_entry


@dataclass(frozen=True)
class RayContact:
    node: object
    fraction: float
    point: tuple
    normal: tuple
    surface: BoxSurface | None = None
    support_face: tuple | None = None


class StaticSupportShapes(tuple):
    """同一实际几何元组及其只读原生数值；不持有另一套世界状态。"""

    def __new__(cls, groups):
        value = super().__new__(cls, groups)
        value.native = support_coefficients(tuple(groups))
        return value


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


def cylinder_suspension_rays(world, chassis, rays, axes, radius, width, shoulder, crown=0., *, envelope=None, ray_origin=None,
                             candidate_cache=None, static_shapes=None):
    """轮轴和有限胎宽进入真实表面查询；不会创建第二个物理世界。"""
    mask = BitMask32.bit(0)
    # 真实形状边界筛选候选；碰撞接触测试会漏掉仍在查询盒内的薄道路面。
    # 查询盒含整条轮心路径与轮胎外廓，不施力、不生成第二个物理世界。
    origin = tuple(chassis.getTransform().getPos()) if ray_origin is None else ray_origin
    relative_rays = (rays if ray_origin is not None else
                     tuple(tuple(tuple(point[a] - origin[a] for a in range(3)) for point in ray) for ray in rays))
    world_rays = (tuple(tuple(tuple(point[a] + ray_origin[a] for a in range(3)) for point in ray) for ray in rays)
                  if ray_origin is not None else rays)
    points = tuple(point for ray in world_rays for point in ray)
    padding = radius + width / 2 + 1e-5
    low = tuple(min(p[a] for p in points) - padding for a in range(3))
    high = tuple(max(p[a] for p in points) + padding for a in range(3))
    cached = candidate_cache is not None and candidate_cache and all(
        candidate_cache['low'][a] <= low[a] and high[a] <= candidate_cache['high'][a] for a in range(3))
    if cached:
        surfaces, exact, native_needed = candidate_cache['surfaces'], candidate_cache['exact'], candidate_cache['native_needed']
    else:
        # 冻结子步内预取5cm邻域；离开覆盖范围便重新查询，实际求交不作近似。
        if candidate_cache is not None:
            low = tuple(value - .05 for value in low)
            high = tuple(value + .05 for value in high)
        surfaces, exact, native_needed = cylinder_candidates(world, chassis, mask, low, high, static_shapes=static_shapes)
        if candidate_cache is not None:
            candidate_cache.update(low=low, high=high, surfaces=surfaces, exact=exact, native_needed=native_needed)
    if envelope is None:
        envelope = wheel_sweep_shape(radius, width, shoulder, crown)
    results = []
    for (start, end), (relative_start, relative_end), axis in zip(world_rays, relative_rays, axes):
        axis = tuple(axis)
        hits = []
        if native_needed:
            transverse = math.hypot(axis[1], axis[2])
            rotation = Quat()
            if transverse:
                rotation_axis = Vec3(0., -axis[2] / transverse, axis[1] / transverse)
                rotation.setFromAxisAngleRad(math.atan2(transverse, axis[0]), rotation_axis)
            elif axis[0] < 0.:
                rotation.setFromAxisAngle(180., Vec3(0., 0., 1.))
            native = world.sweepTestClosest(envelope, TransformState.makePosQuatScale(start, rotation, Vec3(1)),
                                           TransformState.makePosQuatScale(end, rotation, Vec3(1)), mask, 0.)
            if native.hasHit() and native.getNode() != chassis and native.getNode() not in exact:
                point = tuple(native.getHitPos())
                if ray_origin is not None:
                    point = tuple(point[a] - origin[a] for a in range(3))
                hits.append(RayContact(native.getNode(), native.getHitFraction(), point, tuple(native.getHitNormal())))
        if surfaces:
            reach = math.sqrt(sum((end[a] - start[a])**2 for a in range(3))) - radius
            hits.extend(surface_ray_hits(surfaces, relative_start, relative_end, axis, origin,
                radius, reach, width, shoulder, crown, CylinderSurface, RayContact, triangle_entry, cylinder_box_entry, ray_origin is not None))
        results.append(min(hits, key=lambda hit: hit.fraction) if hits else None)
    return tuple(results)


def static_support_shapes(world, chassis, mask, *, cache=None, packet_cache=None):
    """每子步读取世界资格/变换；未改变的静态分区复用原数值几何。"""
    groups = []
    bodies = (body for body in world.getRigidBodies() if body != chassis and body.isStatic()
              and not (body.getIntoCollideMask() & mask).isZero())
    for body in sorted(bodies,key=lambda node: (node.getName(),tuple(node.getTransform().getPos()))):
        shapes = body.getShapes()
        mesh = body.getPythonTag("suspension_mesh") if body.hasPythonTag("suspension_mesh") else None
        shape_bounds = body.getPythonTag("suspension_shape_bounds") if body.hasPythonTag("suspension_shape_bounds") else None
        supported = bool(shapes) and all(isinstance(shape, (BulletBoxShape, BulletPlaneShape)) or (
            isinstance(shape, BulletTriangleMeshShape) and mesh is not None and len(shapes) == 1) for shape in shapes)
        pose = NodePath(body).getNetTransform()
        shape_poses = tuple(body.getShapeTransform(i) for i in range(len(shapes)))
        margins = tuple(shape.getMargin() for shape in shapes)
        # 原生Hull等可在同一shape上增点；其实际边界也必须进入变更判据。
        mutable_bounds = tuple(collision_shape_bounds(shape, None)
                               if shape_bounds is None and isinstance(shape, BulletConvexHullShape)
                               else None for shape in shapes)
        signature = pose, tuple(shapes), shape_poses, margins, id(mesh), id(shape_bounds), mutable_bounds
        previous = cache.get(body) if cache is not None else None
        if previous is not None and previous[0] == signature:
            groups.append(previous[1])
            continue
        body_mat = pose.getMat()
        parts = []
        for i, shape in enumerate(shapes):
            inverse = Mat4()
            inverse.invertFrom(shape_poses[i].getMat() * body_mat)
            frame = tuple(tuple(inverse.getCell(b, a) for b in range(3)) for a in range(3))
            triangles = mesh if isinstance(shape,BulletTriangleMeshShape) and len(shapes) == 1 else None
            bounds = collision_shape_bounds(shape, triangles) if shape_bounds is None else shape_bounds[i]
            translation = tuple(inverse.getCell(3,a) for a in range(3))
            plane = (tuple(shape.getPlaneNormal()), shape.getPlaneConstant()) if isinstance(shape, BulletPlaneShape) else None
            half = tuple(shape.getHalfExtentsWithoutMargin()) if isinstance(shape, BulletBoxShape) else ()
            parts.append((inverse, frame, translation, half, margins[i] if plane is None else 0., plane, triangles, bounds))
        group = body, supported, tuple(parts)
        groups.append(group)
        if cache is not None:
            cache[body] = signature, group
    if cache is not None:
        active = {group[0] for group in groups}
        for body in cache.keys() - active:
            del cache[body]
    groups = tuple(groups)
    if packet_cache is None:
        return groups
    if packet_cache.get('groups') != groups:
        packet_cache['groups'] = groups
        packet_cache['prepared'] = StaticSupportShapes(groups)
    return packet_cache['prepared']


def cylinder_candidates(world, chassis, mask, low, high, *, static_shapes=None):
    """以真实形状边界筛选覆盖盒；独立查询读取当前世界，prepare查询复用本子步几何。"""
    if static_shapes is None:
        static_shapes = static_support_shapes(world, chassis, mask)
    surfaces, exact, native_needed = [], set(), False
    candidates = (prepared_support_candidates(static_shapes.native, low, high)
                  if isinstance(static_shapes, StaticSupportShapes) else support_candidates(static_shapes, low, high))
    for body, supported, parts in candidates:
        if supported:
            for part, local_center, local_half in parts:
                inverse, frame, translation, half, margin, plane, triangles, _bounds = part
                if triangles is not None:
                    # 只预取覆盖盒内原三角面，保留原索引遍历次序；每条射线仍作原精确筛选。
                    selected = tuple(triangles.candidates(local_center, local_center,
                                                         tuple(value+margin for value in local_half)))
                    triangles = TriangleSupport(triangles.low, triangles.high, selected)
                surfaces.append((body, inverse, frame, half, margin, plane, triangles, translation))
            exact.add(body)
        else:
            native_needed = True
    return surfaces, exact, native_needed


def collision_shape_bounds(shape, triangles):
    """原碰撞形状的局部保守边界；有限面仍由后续真实几何判断。"""
    if isinstance(shape, BulletPlaneShape):
        return None
    if isinstance(shape, BulletBoxShape):
        half = tuple(shape.getHalfExtentsWithMargin())
        return tuple(-value for value in half), half
    if triangles is not None:
        margin = shape.getMargin()
        return tuple(value-margin for value in triangles.low), tuple(value+margin for value in triangles.high)
    bounds = shape.getShapeBounds()
    if bounds.isInfinite():
        return None
    center, radius = tuple(bounds.getCenter()), bounds.getRadius()
    return tuple(value-radius for value in center), tuple(value+radius for value in center)
