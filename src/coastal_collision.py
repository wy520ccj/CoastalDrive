"""海岸实体护栏使用分段凸体，避免竖侧面内部三角边产生假接触法线。"""

from panda3d.bullet import BulletConvexHullShape
from panda3d.core import TransformState, Vec3


def add_rail_shapes(body, vertices):
    # 顶点前后两半分别是两侧，每个站点依次为底点、顶点。
    side_count = len(vertices) // 2
    for start in range(0, side_count, 2):
        end = (start + 2) % side_count
        points = [Vec3(*vertices[index]) for index in (
            start, start + 1, end, end + 1,
            start + side_count, start + 1 + side_count,
            end + side_count, end + 1 + side_count,
        )]
        center = sum(points, Vec3(0)) / 8
        shape = BulletConvexHullShape()
        for point in points:
            shape.addPoint(point - center)
        shape.setMargin(0.01)
        body.addShape(shape, TransformState.makePos(center))
