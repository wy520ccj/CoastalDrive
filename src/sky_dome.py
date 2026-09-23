"""A sky that follows the car without entering the driving world."""

import math

from panda3d.core import (
    Filename,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
)

from paths import resource_root


def make_sky(base, parent):
    rows = 24
    columns = 48
    radius = 650
    data = GeomVertexData("sky", GeomVertexFormat.getV3t2(), Geom.UHStatic)
    vertex = GeomVertexWriter(data, "vertex")
    texcoord = GeomVertexWriter(data, "texcoord")
    for row in range(rows + 1):
        polar = math.pi * row / rows
        for column in range(columns + 1):
            angle = 2 * math.pi * column / columns
            vertex.addData3f(
                radius * math.sin(polar) * math.cos(angle),
                radius * math.sin(polar) * math.sin(angle),
                radius * math.cos(polar),
            )
            texcoord.addData2f(column / columns, 1 - row / rows)

    triangles = GeomTriangles(Geom.UHStatic)
    for row in range(rows):
        for column in range(columns):
            corner = row * (columns + 1) + column
            triangles.addVertices(corner, corner + columns + 1, corner + 1)
            triangles.addVertices(corner + 1, corner + columns + 1, corner + columns + 2)
    geometry = Geom(data)
    geometry.addPrimitive(triangles)
    node = GeomNode("sky-dome")
    node.addGeom(geometry)
    sky = parent.attachNewNode(node)
    path = resource_root() / "assets/game/sky/industrial_sunset_puresky.jpg"
    sky.setTexture(base.loader.loadTexture(Filename.fromOsSpecific(str(path))), 1)
    sky.setH(-120)
    sky.setTwoSided(True)
    sky.setBin("background", 0)
    sky.setDepthWrite(False)
    sky.setDepthTest(False)
    sky.setLightOff(1)
    sky.setFogOff(1)
    sky.setShaderOff(1)
    return sky
