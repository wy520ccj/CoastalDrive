"""展示镜头使用实际被绘制的网格顶点，不让空包围盒角点缩小车身。"""

import numpy as np
from panda3d.core import GeomVertexReader


def mesh_vertices(root, scene):
    points = set()
    for part in root.findAllMatches('**/+GeomNode'):
        transform = part.getMat(scene)
        for geom in part.node().getGeoms():
            reader = GeomVertexReader(geom.getVertexData(), 'vertex')
            used = {index for primitive in geom.getPrimitives() for index in primitive.getVertexList()}
            for index in used:
                reader.setRow(index)
                points.add(tuple(transform.xformPoint(reader.getData3f())))
    return np.column_stack((np.asarray(tuple(points)), np.ones(len(points))))


def project_vertices(vertices, scene, camera):
    lens = camera.node().getLens()
    clip = vertices @ np.asarray(scene.getMat(camera)*lens.getProjectionMat())
    # 二分取景的近端可能位于车内，先移远镜头再计算投影。
    if np.any(clip[:, 3] <= lens.getNear()):
        return None
    return clip[:, :2]/clip[:, 3:4]
