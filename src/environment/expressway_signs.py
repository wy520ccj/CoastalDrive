"""高速标志的单层牌面与动态公里数；不依赖运行期字体或图像库。"""

import math

from panda3d.core import Filename, GeomVertexWriter, PNMImage, Texture, Vec4

from paths import resource_root

SIGN_NAMES = ("speed-limit", "curve-left", "curve-right", "hill-warning", "wind-warning",
              "route-direction", "bridge-advance")
SIGN_MODELS = (*SIGN_NAMES, "gantry", "advance-sign", "kilometer")


def image(name):
    source = PNMImage()
    path = resource_root() / "assets/game/expressway/signs" / f"{name}.png"
    if not source.read(Filename.fromOsSpecific(str(path))):
        raise FileNotFoundError(f"缺少高速标志牌面：{path}")
    return source


def face(root, name, points, y, picture):
    """正面只有一个不透明深度面；薄板背面与边缘不覆盖此面。"""
    from scene import make_mesh

    vertices = [(x, y, z) for x, z in points]
    faces = [(0, i, i+1) for i in range(1, len(points)-1)]
    node = make_mesh(name, vertices, faces, Vec4(1))
    left, right = min(x for x,z in points), max(x for x,z in points)
    bottom, top = min(z for x,z in points), max(z for x,z in points)
    uv = GeomVertexWriter(node.node().modifyGeom(0).modifyVertexData(), "texcoord")
    for triangle in faces:
        for i in triangle:
            x, z = points[i]
            uv.setData2f((x-left)/(right-left), (z-bottom)/(top-bottom))
    texture = Texture(name)
    texture.load(picture)
    texture.setFormat(Texture.FSrgb)
    texture.setMinfilter(Texture.FTLinearMipmapLinear)
    texture.setMagfilter(Texture.FTLinear)
    texture.setWrapU(Texture.WMClamp)
    texture.setWrapV(Texture.WMClamp)
    texture.setAnisotropicDegree(4)
    node.setTexture(texture)
    node.reparentTo(root)
    return node


def panel(root, name, x, y, z, width, height, picture):
    return face(root, name, [(x-width/2,z-height/2), (x+width/2,z-height/2),
                            (x+width/2,z+height/2), (x-width/2,z+height/2)], y, picture)


def kilometer_face(root, distance, base, digits):
    """绝对里程烘入同一牌面；S18编号与公里数保持一张纹理。"""
    picture = PNMImage(base)
    value = str(max(0, math.floor(distance / 1000)))
    strip = PNMImage(len(value)*96, 128)
    for i, digit in enumerate(value):
        strip.copySubImage(digits, i*96, 0, int(digit)*96, 0, 96, 128)
    scaled = PNMImage(min(206, len(value)*70), 128)
    scaled.quickFilterFrom(strip)
    picture.copySubImage(scaled, (256-scaled.getXSize())//2, 208)
    return panel(root, "kilometer-face", 0, -.13, 1.30, .64, .85, picture)
