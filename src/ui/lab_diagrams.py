"""工坊的车辆、道路与长度图解；只绘制传入的展示数据。"""

import math

from panda3d.core import (
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexWriter,
    LineSegs,
)

from ui import theme
from ui.lab_widgets import rounded_panel


def line(parent, points, color=theme.SEA, width=2.):
    drawing = LineSegs()
    drawing.setColor(*color)
    drawing.setThickness(width)
    drawing.moveTo(points[0][0], 0, points[0][1])
    for x, z in points[1:]:
        drawing.drawTo(x, 0, z)
    return parent.attachNewNode(drawing.create())


def car(parent, x, z, width=.8, color=theme.SEA):
    """侧视教学示意，车头朝右；不表示实际车型或机械尺寸。"""
    node = parent.attachNewNode('teaching-car')
    node.setPos(x, 0, z)
    node.setScale(width)
    def polygon(name, points, fill):
        data = GeomVertexData(name, GeomVertexFormat.getV3(), Geom.UHStatic)
        writer = GeomVertexWriter(data, 'vertex')
        for px, pz in points:
            writer.addData3f(px, 0, pz)
        triangles = GeomTriangles(Geom.UHStatic)
        for index in range(1, len(points)-1):
            triangles.addVertices(0, index, index+1)
        geometry = Geom(data)
        geometry.addPrimitive(triangles)
        shape = GeomNode(name)
        shape.addGeom(geometry)
        part = node.attachNewNode(shape)
        part.setColor(*fill)
        part.setTwoSided(True)
        return part

    polygon('sedan-profile', [(-.49, .055), (.48, .055), (.50, .11), (.46, .16),
        (.26, .185), (.10, .29), (-.15, .30), (-.34, .18), (-.48, .16)], color)
    polygon('rear-window', [(-.28, .185), (-.13, .27), (-.035, .27), (-.035, .185)],
            (.66, .80, .83, 1))
    polygon('front-window', [(-.01, .185), (-.01, .27), (.085, .265), (.22, .185)],
            (.76, .88, .90, 1))
    line(node, [(-.46, .075), (.47, .075)], theme.INK, 1.)
    line(node, [(-.015, .17), (-.015, .075)], theme.INK, 1.)
    rounded_panel(node, 'handle', (.025, .065, .151, .162), theme.PAPER_LIGHT, .003)
    polygon('headlamp', [(.38, .143), (.465, .132), (.48, .110), (.41, .12)], theme.PAPER_LIGHT)
    polygon('rear-lamp', [(-.48, .14), (-.43, .135), (-.43, .115), (-.48, .12)], theme.ORANGE)
    for axle in (-.31, .31):
        rounded_panel(node, 'tire', (axle-.075, axle+.075, -.025, .125), theme.INK, .075)
        rounded_panel(node, 'hub', (axle-.044, axle+.044, .006, .094), (.77, .83, .82, 1), .044)
        rounded_panel(node, 'hub-center', (axle-.014, axle+.014, .036, .064), color, .014)
    return node


def course(parent, box, kind):
    """课题图标只表达目标，实际道路回放另用原始轨迹。"""
    left, right, bottom, top = box
    width, height = right-left, top-bottom
    if kind == 'corner':
        points = [(left+width*t/40, bottom+height*(.45+.30*math.sin(t/40*math.pi*2)))
                  for t in range(41)]
        for offset in (-.035, .035):
            line(parent, [(x, z+offset) for x, z in points], (.72, .79, .78, 1), 2.)
        line(parent, points, theme.SEA, 3.)
        car(parent, left+width*.3, bottom+height*.35, width*.38)
    else:
        z = bottom+height*.3
        line(parent, [(left, z), (right, z)], (.72, .79, .78, 1), 2.)
        car(parent, left+width*.33, z+.035, width*.52)
        end = right-width*.12
        line(parent, [(end, z-.03), (end, z+height*.55)], theme.ORANGE, 3.)
        if kind == 'stop':
            rounded_panel(parent, 'target-zone', (end-width*.13, end+width*.06, z+.015, z+.10),
                          (.80, .89, .84, 1), .005)


def lengths(parent, a, b, *, left=-1.32, right=.32, top=.20, gap=.27, vehicles=True):
    """两根长度共用零点和比例；保留符号，不把不同条件写成收益。"""
    maximum = max(abs(a), abs(b), .001)
    for value, z, color in ((a, top, theme.SEA), (b, top-gap, theme.ORANGE)):
        end = left+(right-left)*abs(value)/maximum
        rounded_panel(parent, 'distance-track', (left, right, z-.012, z+.012),
                      (.87, .90, .87, 1), .008)
        if value:
            rounded_panel(parent, 'distance', (left, end, z-.012, z+.012), color, .008)
        line(parent, [(end, z-.04), (end, z+.11)], color, 2.)
        if vehicles:
            car(parent, end-.15, z+.025, .30, color)
    line(parent, [(left, top-gap-.07), (left, top+.15)], theme.MUTED, 1.)
