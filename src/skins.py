"""Palette choices affect appearance only, never the vehicle's handling."""

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Skin:
    name: str
    color: tuple[float, float, float] | None


SKINS = (
    Skin("原厂橙", None),
    Skin("海湾蓝", (0.08, 0.38, 0.8)),
    Skin("赛车红", (0.75, 0.07, 0.05)),
    Skin("松林绿", (0.1, 0.46, 0.25)),
    Skin("珍珠白", (0.86, 0.89, 0.91)),
)


def traffic_models(seed, count):
    return tuple(
        random.Random(seed + 141).choices(("traffic-sedan.glb", "player-car.glb"), k=count)
    )


def traffic_skins(seed, count):
    return tuple(random.Random(seed + 812).choices(range(len(SKINS)), k=count))


def apply_skin(model, index):
    # Tint only painted triangles; windows, tyres and trim keep their original materials.
    from panda3d.core import (
        Geom,
        GeomNode,
        GeomTriangles,
        GeomVertexReader,
        Material,
        TextureAttrib,
        Vec4,
    )

    color = SKINS[index].color
    for old in model.findAllMatches("**/skin-paint"):
        old.removeNode()
    # Original body geometry is retained so changing skins never compounds a tint.
    for part in model.findAllMatches("**/+GeomNode"):
        if part.getName() not in ("body", "spoiler"):
            continue
        node = part.node()
        if not part.hasPythonTag("original-geom"):
            part.setPythonTag("original-geom", node.getGeom(0).makeCopy())
        original = part.getPythonTag("original-geom")
        node.setGeom(0, original.makeCopy())
        if color is None:
            continue
        data = original.getVertexData()
        texture = node.getGeomState(0).getAttrib(TextureAttrib)
        if texture is None:
            continue
        from panda3d.core import PNMImage

        pixels = PNMImage()
        texture.getOnTexture(texture.getOnStage(0)).store(pixels)
        uv = GeomVertexReader(data, "texcoord.0")
        painted = []
        while not uv.isAtEnd():
            u, v = uv.getData2f()
            r, g, b = pixels.getXel(
                min(pixels.getXSize() - 1, int(u * pixels.getXSize())),
                min(pixels.getYSize() - 1, int((1 - v) * pixels.getYSize())),
            )
            # The two bundled cars share this orange palette; red lamps stay red.
            painted.append(r > b * 1.3 and 0.12 * r < g < 0.20 * r)
        keep, paint = GeomTriangles(Geom.UHStatic), GeomTriangles(Geom.UHStatic)
        for primitive in original.getPrimitives():
            triangles = primitive.decompose()
            for i in range(triangles.getNumPrimitives()):
                ids = [
                    triangles.getVertex(j)
                    for j in range(triangles.getPrimitiveStart(i), triangles.getPrimitiveEnd(i))
                ]
                target = paint if all(painted[j] for j in ids) else keep
                target.addVertices(*ids)
        unchanged = Geom(data)
        unchanged.addPrimitive(keep)
        node.setGeom(0, unchanged)
        geom = Geom(data)
        geom.addPrimitive(paint)
        child = GeomNode("skin-paint")
        child.addGeom(geom)
        overlay = part.attachNewNode(child)
        overlay.setTextureOff(1)
        material = Material()
        material.setBaseColor(Vec4(*color, 1))
        material.setRoughness(0.45)
        overlay.setMaterial(material, 1)
        overlay.setTwoSided(True)
