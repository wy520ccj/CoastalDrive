"""已计算法线的地表直接写入索引网格，避免展开三角形后再覆写各顶点。"""

from array import array
from functools import lru_cache

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    InternalName,
    NodePath,
)


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
    data = GeomVertexData(name, GeomVertexFormat.getV3n3c4t2(), Geom.UHStatic)
    data.setNumRows(len(vertices))
    # Panda内置格式的颜色是4个uint8，其余为float32。
    import struct

    packed = bytearray()
    for p, n, c, t in zip(vertices, normals, colors, uv):
        packed.extend(struct.pack("=6f4B2f", *p, *n,
                                  *(round(max(0,min(1,v))*255) for v in c), *t))
    data.modifyArray(0).modifyHandle().setData(bytes(packed))
    triangles = GeomTriangles(Geom.UHStatic)
    triangles.setIndexType(Geom.NTUint32)
    indices = array("I", (i for face in faces for i in face))
    triangles.modifyVertices().modifyHandle().setData(indices.tobytes())
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    return NodePath(node)
