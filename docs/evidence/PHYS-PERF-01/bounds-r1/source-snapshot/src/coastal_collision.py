"""海岸实体护栏使用分段凸体，避免竖侧面内部三角边产生假接触法线。"""

from panda3d.bullet import BulletConvexHullShape
from panda3d.core import TransformState, Vec3


def add_rail_shapes(body, vertices):
    # 顶点前后两半分别是两侧，每个站点依次为底点、顶点。
    side_count = len(vertices) // 2
    bounds = []
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
        body.addShape(shape, TransformState.makePos(center))
        margin = shape.getMargin()
        bounds.append((tuple(min(point[a] for point in local_points) - margin for a in range(3)),
                       tuple(max(point[a] for point in local_points) + margin for a in range(3))))
    # 与真实凸体共用这些原顶点；包围球会把细护栏横向扩成1.5m宽的候选。
    body.setPythonTag("suspension_shape_bounds", tuple(bounds))
