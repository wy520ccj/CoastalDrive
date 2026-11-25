"""海岸实体护栏使用分段凸体，避免竖侧面内部三角边产生假接触法线。"""

from panda3d.bullet import BulletConvexHullShape, BulletRigidBodyNode
from panda3d.core import TransformState, Vec3


def _rail_hull_entries(vertices):
    # 顶点前后两半分别是两侧，每个站点依次为底点、顶点。
    side_count = len(vertices) // 2
    entries = []
    for start in range(0, side_count, 2):
        end = (start + 2) % side_count
        points = [Vec3(*vertices[index]) for index in (
            start, start + 1, end, end + 1,
            start + side_count, start + 1 + side_count,
            end + side_count, end + 1 + side_count,
        )]
        center = sum(points, Vec3(0)) / 8
        shape = BulletConvexHullShape()
        local_points = tuple(point - center for point in points)
        for point in local_points:
            shape.addPoint(point)
        shape.setMargin(0.01)
        margin = shape.getMargin()
        bound = (tuple(min(point[a] for point in local_points) - margin for a in range(3)),
                 tuple(max(point[a] for point in local_points) + margin for a in range(3)))
        entries.append((shape, center, tuple(tuple(point) for point in local_points), bound))
    return entries


def _attach_rail_entries(body, entries):
    bounds = []
    hull_vertices = []
    for shape, center, local_points, bound in entries:
        body.addShape(shape, TransformState.makePos(center))
        hull_vertices.append(local_points)
        bounds.append(bound)
    # 与真实凸体共用这些原顶点；包围球会把细护栏横向扩成1.5m宽的候选。
    body.setPythonTag("suspension_shape_bounds", tuple(bounds))
    body.setPythonTag("suspension_hull_shapes", tuple(body.getShapes()))
    body.setPythonTag("suspension_hull_vertices", tuple(hull_vertices))


def add_rail_shapes(body, vertices):
    _attach_rail_entries(body, _rail_hull_entries(vertices))


def build_rail_bodies(name, vertices, *, chunk_size=16):
    """按沿线小段拆分护栏刚体，保留完全相同的凸体几何与命名，避免全岛大包围盒拖慢 Bullet 粗检。"""
    entries = _rail_hull_entries(vertices)
    bodies = []
    for offset in range(0, len(entries), chunk_size):
        body = BulletRigidBodyNode(name)
        _attach_rail_entries(body, entries[offset:offset + chunk_size])
        bodies.append(body)
    return bodies
