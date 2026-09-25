"""One-time material migration for the two bundled CC0 Kenney cars.

Palette detection belongs to this authoring step, not the game's skin system.
The output embeds textures and contains explicit paint nodes.
"""
from pathlib import Path

import gltf
from panda3d.core import Filename, NodePath, loadPrcFileData


def prepare_paint(model):
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

    color = (0.8, 0.12, 0.025)
    # The GLB inputs stay untouched; the game loads only the prepared BAM files.
    for part in model.findAllMatches("**/+GeomNode"):
        if part.getName() not in ("body", "spoiler"):
            continue
        node = part.node()
        original = node.getGeom(0)
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
        child = GeomNode("paint")
        child.addGeom(geom)
        overlay = part.attachNewNode(child)
        overlay.setTextureOff(1)
        material = Material()
        material.setBaseColor(Vec4(*color, 1))
        material.setRoughness(0.45)
        overlay.setMaterial(material, 1)
        overlay.setTwoSided(True)


if __name__ == "__main__":
    loadPrcFileData("", "bam-texture-mode rawdata")
    root = Path(__file__).resolve().parents[1] / "assets/game"
    for name in ("player-car", "traffic-sedan"):
        model = NodePath(gltf.load_model(Filename.fromOsSpecific(str(root / f"{name}.glb"))))
        prepare_paint(model)
        slots = model.findAllMatches("**/paint")
        assert len(slots) > 0, name
        for slot in slots:
            slot.getMaterial().setName("vehicle-paint")
        assert model.writeBamFile(Filename.fromOsSpecific(str(root / f"{name}.bam")))
        print(name, len(slots), "paint slots")
