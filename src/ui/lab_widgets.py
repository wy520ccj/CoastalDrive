"""实验室专用圆角卡片几何；无位图文字，控件仍由DirectGUI编辑。"""

import math
from functools import lru_cache

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    PNMImage,
    Texture,
)


def rounded_panel(parent, name, box, color, radius=.025):
    left, right, bottom, top = box
    radius = min(radius, (right-left)/2, (top-bottom)/2)
    points = [((left+right)/2, 0, (bottom+top)/2)]
    for cx, cz, angle in ((right-radius, top-radius, 0), (left+radius, top-radius, 90),
                          (left+radius, bottom+radius, 180), (right-radius, bottom+radius, 270)):
        for step in range(9):
            phase = math.radians(angle+step*90/8)
            points.append((cx+radius*math.cos(phase), 0, cz+radius*math.sin(phase)))
    data = GeomVertexData(name, GeomVertexFormat.getV3(), Geom.UHStatic)
    writer = GeomVertexWriter(data, "vertex")
    for point in points:
        writer.addData3f(*point)
    triangles = GeomTriangles(Geom.UHStatic)
    for index in range(1, len(points)):
        triangles.addVertices(0, index, 1 if index == len(points)-1 else index+1)
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    result = parent.attachNewNode(node)
    result.setColor(*color)
    result.setDepthTest(False)
    result.setDepthWrite(False)
    return result


@lru_cache(maxsize=2)
def button_textures(primary):
    """程序绘制圆角和悬停色，避免沿用旧按钮的硬边框。"""
    fills = ((.96, .49, .14), (1., .58, .22), (.88, .39, .09), (.83, .79, .70)) if primary else (
        (.985, .98, .95), (.90, .95, .94), (.85, .91, .90), (.91, .91, .87))
    textures = []
    width, height, radius = 256, 64, 10
    for index, fill in enumerate(fills):
        image = PNMImage(width, height, 4)
        border = fill if primary else (.72, .79, .78)
        for y in range(height):
            for x in range(width):
                dx = max(radius-x-.5, x+.5-(width-radius), 0.)
                dy = max(radius-y-.5, y+.5-(height-radius), 0.)
                distance = math.hypot(dx, dy)
                alpha = min(1., max(0., radius+.5-distance))
                edge = min(x+.5, width-x-.5, y+.5, height-y-.5, radius-distance)
                color = border if edge < 1.2 else fill
                image.setXelA(x, y, *color, alpha)
        texture = Texture(f"lab-button-{primary}-{index}")
        texture.load(image)
        textures.append(texture)
    return tuple(textures)
