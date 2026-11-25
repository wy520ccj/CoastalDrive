"""已计算法线的地表直接写入索引网格，避免展开三角形后再覆写各顶点。"""

from functools import lru_cache

from panda3d.core import (
    ConfigVariableBool,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    InternalName,
    NodePath,
    SceneGraphReducer,
)


def flatten_steps(root):
    """按原生flattenStrong顺序分摊合并；节点须在全部完成后再挂入实时场景。"""
    reducer, node = SceneGraphReducer(), root.node()
    reducer.applyAttribs(node)
    yield 'mesh-batch-attributes'
    reducer.flatten(node, ~0)
    yield 'mesh-batch-nodes'
    if ConfigVariableBool('flatten-geoms').getValue():
        reducer.makeCompatibleState(node)
        yield 'mesh-batch-compatible'
        reducer.collectVertexData(node, ~(SceneGraphReducer.CVDFormat | SceneGraphReducer.CVDName
                                          | SceneGraphReducer.CVDAnimationType))
        yield 'mesh-batch-vertices'
        reducer.unify(node, False)
        yield 'mesh-batch-primitives'


@lru_cache(maxsize=8)
def rail_shadow_format(original):
    format = GeomVertexFormat(original)
    extra = GeomVertexArrayFormat()
    extra.addColumn(InternalName.make("rail_shadow_coord"), 2, Geom.NTFloat32, Geom.COther)
    format.addArray(extra)
    return GeomVertexFormat.registerFormat(format)


def set_rail_shadow_coordinates(node, coordinates, faces=None, geom_index=0):
    """只追加固定遮蔽坐标，原路面顶点、法线、贴图与三角形保持。"""
    data = node.node().modifyGeom(geom_index).modifyVertexData()
    data.setFormat(rail_shadow_format(data.getFormat()))
    writer = GeomVertexWriter(data, "rail_shadow_coord")
    indices = (i for face in faces for i in face) if faces is not None else range(len(coordinates))
    for index in indices:
        writer.addData2f(*coordinates[index])


def surface_mesh(name, vertices, faces, normals, colors, uv):
    import numpy as np

    count = len(vertices)
    data = GeomVertexData(name, GeomVertexFormat.getV3n3c4t2(), Geom.UHStatic)
    data.setNumRows(count)
    # Panda内置格式的颜色是4个uint8，其余为float32。
    dtype = np.dtype([('p', '<f4', 3), ('n', '<f4', 3), ('c', 'u1', 4), ('uv', '<f4', 2)])
    packed = np.empty(count, dtype=dtype)
    if count:
        packed['p'] = vertices
        packed['n'] = normals
        packed['c'] = np.rint(np.clip(np.asarray(colors, dtype=np.float64), 0.0, 1.0) * 255.0).astype(np.uint8)
        packed['uv'] = uv
    data.modifyArray(0).modifyHandle().setData(packed.tobytes())
    triangles = GeomTriangles(Geom.UHStatic)
    triangles.setIndexType(Geom.NTUint32)
    indices = np.asarray(faces, dtype='<u4').reshape(-1)
    triangles.modifyVertices().modifyHandle().setData(indices.tobytes())
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)
