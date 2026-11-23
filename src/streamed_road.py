"""Loaded road segments in one Bullet world; segment identities are global."""

from panda3d.bullet import (
    BulletBoxShape,
    BulletRigidBodyNode,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
)
from panda3d.core import BitMask32, TransformState, Vec3

import curve_mesh
from career_courses import CareerCourse
from highway_segments import SEGMENT_LENGTH, indices_around, segment, segment_index, surface_meshes
from triangle_support import TriangleSupport

# 普通发行 SDK 尚未公开内部边接口。本地修正 SDK 通过启动器加载。
_enable_internal_edges = getattr(BulletTriangleMeshShape, "enable_internal_edge_adjustment", None)
ROAD_EDGE_ADJUSTMENT_AVAILABLE = _enable_internal_edges is not None


class StreamedRoad:
    def __init__(self, world, seed, curve=None):
        self.world = world
        self.seed = seed
        self.segments = {}
        self.curve = curve
        self.meshes = {}
        self.shapes = {}
        self.supports = {}
        self._curve_shapes = {}
        for name, (vertices, triangles) in surface_meshes().items():
            mesh = BulletTriangleMesh()
            for triangle in triangles:
                mesh.addTriangle(*(Vec3(*vertices[i]) for i in triangle))
            shape = BulletTriangleMeshShape(mesh, dynamic=False)
            shape.setMargin(0.01)
            self.shapes[name] = shape
            self.supports[name] = TriangleSupport.build(tuple(tuple(vertices[i] for i in triangle) for triangle in triangles))

    def update(self, global_y, origin, occupied):
        wanted = set(indices_around(global_y))
        # A stopped or straddling car must keep its floor, even outside the view range.
        for y in occupied:
            wanted.update((segment_index(y - 4), segment_index(y + 4)))
        for index in sorted(wanted - self.segments.keys()):
            self.add(index, origin)
        for index in self.segments.keys() - wanted:
            for body in self.segments.pop(index):
                self.world.removeRigidBody(body)
            self.meshes.pop(index, None)

    def add(self, index, origin):
        start = index * SEGMENT_LENGTH - origin
        bodies = []
        shapes = self.shapes
        supports = self.supports
        base = (0, start, 0)
        adjust_edges = ROAD_EDGE_ADJUSTMENT_AVAILABLE and isinstance(self.curve, CareerCourse)
        if self.curve:
            x, y, z = curve_mesh.anchor(self.curve, index)
            base = (x, y - origin, z)
            self.meshes[index] = curve_mesh.surfaces(self.curve, index)
            shapes = {}
            supports = {}
            for name, (vertices, triangles) in self.meshes[index].items():
                # 终点外相邻条带常为完全相同的局部几何，复用不可变形状和支撑索引。
                # 每种地表只记上一份；顶点/索引逐值相等才复用，刚体和世界变换仍独立。
                signature = tuple(vertices), tuple(triangles)
                if name in self._curve_shapes and self._curve_shapes[name][0] == signature:
                    _signature, shape, support = self._curve_shapes[name]
                else:
                    mesh = BulletTriangleMesh()
                    for triangle in triangles:
                        mesh.addTriangle(*(Vec3(*vertices[i]) for i in triangle))
                    shape = BulletTriangleMeshShape(mesh, dynamic=False)
                    shape.setMargin(0.01)
                    if adjust_edges and name == "road" and not _enable_internal_edges(shape):
                        raise RuntimeError("无法为赛道路面建立三角形邻接")
                    support = TriangleSupport.build(tuple(tuple(vertices[i] for i in triangle) for triangle in triangles))
                    self._curve_shapes[name] = signature, shape, support
                shapes[name] = shape
                supports[name] = support
        for name, shape in shapes.items():
            body = BulletRigidBodyNode(f"segment-{index}-{name}")
            body.addShape(shape)
            if adjust_edges and name == "road":
                body.notifyCollisions(True)
            body.setPythonTag("suspension_mesh", supports[name])
            body.setTransform(TransformState.makePos(Vec3(*base)))
            body.setIntoCollideMask(BitMask32(7))
            self.world.attachRigidBody(body)
            bodies.append(body)
        for n, (x, y, scale, heading) in enumerate(segment(self.seed, index).trees):
            position = Vec3(x, start + y, -0.32 + 0.7 * scale)
            if self.curve:
                p = self.curve.sample(index * SEGMENT_LENGTH + y, x)
                position = Vec3(p.x, p.y - origin, p.z - 0.32 + 0.7 * scale)
            body = BulletRigidBodyNode(f"segment-{index}-tree-{n}")
            body.addShape(BulletBoxShape(Vec3(0.09, 0.09, 0.65) * scale))
            body.setTransform(
                TransformState.makePosHpr(
                    position, Vec3(heading, 0, 0)
                )
            )
            body.setIntoCollideMask(BitMask32(7))
            self.world.attachRigidBody(body)
            bodies.append(body)
        self.segments[index] = bodies

    def shift(self, amount):
        for bodies in self.segments.values():
            for body in bodies:
                pose = body.getTransform()
                self.world.removeRigidBody(body)
                body.setTransform(
                    TransformState.makePosHpr(pose.getPos() - Vec3(0, amount, 0), pose.getHpr())
                )
                # Refresh the broadphase now, before same-frame camera and reset queries.
                self.world.attachRigidBody(body)
