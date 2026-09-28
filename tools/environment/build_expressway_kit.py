"""离线制作原创快速路模块；尺寸源即为可编辑美术源文件。"""

import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, NodePath, PNMImage, TextNode, Vec4

from scene import make_box, make_mesh

OUT = ROOT / "assets/game/expressway"
STONE = (0.48, 0.51, 0.49, 1)
STEEL = (0.32, 0.41, 0.43, 1)
WHITE = (0.86, 0.88, 0.80, 1)
GREEN = (0.025, 0.25, 0.21, 1)


def box(root, name, pos, size, color=STONE):
    part = make_box(name, tuple(v / 2 for v in size), Vec4(*color))
    part.reparentTo(root)
    part.setPos(*pos)
    return part


def label(root, text, x, y, z, size):
    node = TextNode(text)
    node.setText(text)
    node.setAlign(TextNode.ACenter)
    node.setTextColor(*WHITE)
    path = root.attachNewNode(node.generate())
    path.setPos(x, y, z)
    path.setScale(size)


def beam(root, a, b, width=0.10):
    # 箱梁本地Z轴沿两端点，避免依赖美术软件的坐标约定。
    length = math.dist(a, b)
    part = box(root, "brace", tuple((x + y) / 2 for x, y in zip(a, b)),
               (width, width, length), STEEL)
    dx, dy, dz = (y - x for x, y in zip(a, b))
    part.setHpr(math.degrees(math.atan2(-dx, dy)),
                math.degrees(math.atan2(dz, math.hypot(dx, dy))) - 90, 0)


def crown(root, center, radius, color):
    vertices = []
    for row in range(5):
        polar = math.pi * (row + 0.15) / 4.3
        for col in range(9):
            angle = col * 2 * math.pi / 9 + (row % 2) * 0.18
            vertices.append((center[0] + radius[0] * math.sin(polar) * math.cos(angle),
                             center[1] + radius[1] * math.sin(polar) * math.sin(angle),
                             center[2] + radius[2] * math.cos(polar)))
    triangles = []
    for row in range(4):
        for col in range(9):
            a, b = row * 9 + col, row * 9 + (col + 1) % 9
            triangles.extend(((a, a + 9, b), (b, a + 9, b + 9)))
    make_mesh("leaf-cluster", vertices, triangles, Vec4(*color)).reparentTo(root)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    assets = {}
    root = NodePath("lamp")
    box(root, "foot", (0, 0, 0.22), (0.6, 0.6, 0.44))
    box(root, "mast", (0, 0, 4.6), (0.16, 0.18, 9.0), STEEL)
    beam(root, (0, 0, 8.9), (2.6, 0, 9.3), 0.14)
    box(root, "luminaire", (2.5, 0, 9.28), (1.35, 0.44, 0.16), STEEL)
    box(root, "lens", (2.5, 0, 9.18), (1.2, 0.35, 0.035), WHITE)
    assets["lamp"] = root

    root = NodePath("reflector")
    box(root, "post", (0, 0, 0.50), (0.12, 0.16, 1), WHITE)
    box(root, "black-band", (0, -0.09, 0.8), (0.13, 0.035, 0.23), STEEL)
    box(root, "reflective-face", (0, -0.112, 0.80), (0.08, 0.02, 0.14),
        (0.98, 0.53, 0.05, 1))
    assets["reflector"] = root

    root = NodePath("gantry")
    for x in (-9.5, 9.5):
        box(root, "foundation", (x, 0, 0.30), (1, 1.3, 0.6))
        for y in (-0.4, 0.4):
            box(root, "upright", (x, y, 4.5), (0.22, 0.22, 9), STEEL)
    for y in (-0.4, 0.4):
        for z in (8.0, 9.0):
            box(root, "cross-member", (0, y, z), (19.4, 0.16, 0.16), STEEL)
        for x in range(-9, 9, 2):
            beam(root, (x, y, 8), (x + 2, y, 9))
    for x, title in ((-4.6, "BAY DISTRICT"), (4.6, "COASTAL CITY")):
        box(root, "sign-border", (x, -0.62, 7.1), (8.3, 0.16, 2.6), WHITE)
        box(root, "sign-enamel", (x, -0.72, 7.1), (8.1, 0.07, 2.4), GREEN)
        label(root, title, x, -0.77, 7.45, 0.58)
        label(root, "THROUGH ROUTE", x, -0.77, 6.8, 0.30)
        box(root, "arrow-stem", (x, -0.77, 6.35), (0.10, 0.025, 0.45), WHITE)
        make_mesh("arrow-head", [(x - 0.28, -0.79, 6.43), (x + 0.28, -0.79, 6.43),
                                  (x, -0.79, 6.78)], [(0, 1, 2)], Vec4(*WHITE)).reparentTo(root)
    assets["gantry"] = root

    root = NodePath("advance-sign")
    for x in (-1.2, 1.2):
        box(root, "post", (x, 0, 1.8), (0.12, 0.16, 3.6), STEEL)
    box(root, "sign-border", (0, -0.1, 3.3), (5.4, 0.16, 2.3), WHITE)
    box(root, "sign", (0, -0.20, 3.3), (5.2, 0.07, 2.1), GREEN)
    label(root, "COASTAL EXPRESSWAY", 0, -0.25, 3.86, 0.31)
    label(root, "BAY OVERPASS", 0, -0.25, 3.19, 0.47)
    label(root, "300 m", 0, -0.25, 2.55, 0.46)
    assets["advance-sign"] = root

    root = NodePath("soundwall")
    box(root, "plinth", (0, 2, 0.4), (0.48, 4, 0.8))
    for z, color in ((1.18, (0.17, 0.33, 0.32, 1)),
                     (1.92, (0.25, 0.43, 0.40, 1)),
                     (2.66, (0.38, 0.53, 0.47, 1))):
        box(root, "acoustic-panel", (0, 2, z), (0.18, 3.88, 0.7), color)
        for dz in (-0.16, 0.16):
            box(root, "rib", (-0.11, 2, z + dz), (0.04, 3.88, 0.035), STEEL)
    box(root, "post", (0, 0, 1.55), (0.32, 0.16, 3.1), WHITE)
    box(root, "coping", (0, 2, 3.06), (0.3, 4, 0.09), WHITE)
    assets["soundwall"] = root

    root = NodePath("crash-cushion")
    for y in (-0.85, 0, 0.85):
        box(root, "absorber", (0, y, 0.48), (0.85, 0.74, 0.96), (0.95, 0.52, 0.04, 1))
        box(root, "stripe", (0, y - 0.38, 0.48), (0.86, 0.025, 0.16), STEEL)
    assets["crash-cushion"] = root

    root = NodePath("drain-grate")
    box(root, "frame", (0, 0, 0.012), (0.48, 1, 0.024), STONE)
    for y in range(8):
        box(root, "slot", (0, -0.43 + y * 0.12, 0.028), (0.33, 0.06, 0.015), STEEL)
    assets["drain-grate"] = root

    root = NodePath("kilometer")
    box(root, "post", (0, 0, 0.65), (0.09, 0.12, 1.3), STEEL)
    box(root, "plate", (0, -0.06, 1.30), (0.64, 0.1, 0.85), GREEN)
    label(root, "E1", 0, -0.12, 1.4, 0.22)
    label(root, "0", 0, -0.12, 1.03, 0.25)
    assets["kilometer"] = root

    root = NodePath("equipment")
    box(root, "plinth", (0, 0, 0.1), (1.8, 1.0, 0.2))
    box(root, "cabinet", (0, 0, 0.87), (1.15, 0.55, 1.55), WHITE)
    box(root, "door", (0, -0.29, 0.88), (1.03, 0.03, 1.35), STONE)
    box(root, "handle", (0.38, -0.33, 0.95), (0.04, 0.04, 0.19), STEEL)
    for z in range(5):
        box(root, "vent", (-0.14, -0.313, 0.4 + z * 0.11), (0.55, 0.015, 0.035), STEEL)
    assets["equipment"] = root

    root = NodePath("overpass")
    box(root, "deck", (0, 0, 7.15), (110, 9.6, 0.60))
    for y in (-3.4, 0, 3.4):
        box(root, "girder", (0, y, 6.65), (110, 0.5, 0.65), STONE)
    for x in (-11.8, 11.8):
        box(root, "pier", (x, 0, 3.16), (1.25, 6.5, 6.32))
        box(root, "capital", (x, 0, 6.25), (2.0, 8.0, 0.40))
    for y in (-4.65, 4.65):
        box(root, "parapet", (0, y, 7.75), (110, 0.26, 0.80), WHITE)
        box(root, "cap", (0, y, 8.20), (110, 0.32, 0.13), STEEL)
    label(root, "B A Y   O V E R P A S S", 0, -4.82, 7.55, 0.34)
    assets["overpass"] = root

    root = NodePath("broadleaf-crown")
    for center, radius, color in (
        ((0, 0, 1.8), (0.85, 0.7, 0.65), (0.09, 0.22, 0.11, 1)),
        ((-0.42, 0.1, 2.15), (0.65, 0.65, 0.5), (0.16, 0.31, 0.14, 1)),
        ((0.35, -0.15, 2.3), (0.66, 0.62, 0.55), (0.24, 0.37, 0.15, 1)),
    ):
        crown(root, center, radius, color)
    assets["broadleaf-crown"] = root
    root = NodePath("shrub-bank")
    for x, y, z in ((-1.1, 0, 0.45), (0, 0.3, 0.55), (1.1, -0.1, 0.4)):
        crown(root, (x, y, z), (1.0, 0.9, 0.65), (0.20, 0.32, 0.12, 1))
    assets["shrub-bank"] = root

    files = []
    for name, root in assets.items():
        root.flattenStrong()
        path = OUT / f"{name}.bam"
        root.writeBamFile(Filename.fromOsSpecific(str(path)))
        files.append({"name": name, "file": path.name,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    pixels = PNMImage(256, 256, 3)
    for y in range(256):
        for x in range(256):
            # 无缝颗粒只改变明度，避免写实道路贴图的大块补丁。
            grain = ((x * 1973 + y * 9277 + x * y * 13) % 101) / 100
            value = 0.72 + 0.23 * grain
            pixels.setXel(x, y, value, value, value)
    pixels.write(Filename.fromOsSpecific(str(OUT / "aggregate.png")))
    sky = PNMImage(1024, 512, 3)
    for y in range(512):
        latitude = 1 - y / 511
        elevation = max(0, (latitude - 0.5) * 2)
        blend = elevation ** 0.48
        horizon, zenith = (0.57, 0.74, 0.84), (0.08, 0.32, 0.57)
        for x in range(1024):
            angle = x / 1024 * 2 * math.pi
            cloud = (math.sin(angle * 7 + latitude * 15)
                     + 0.5 * math.sin(angle * 13 - latitude * 33))
            veil = max(0, min(1, (cloud - 0.10) * 1.5))
            veil *= math.exp(-((elevation - 0.15) / 0.07) ** 2) * 0.65
            color = [a * (1 - blend) + b * blend for a, b in zip(horizon, zenith)]
            sky.setXel(x, y, *(c * (1 - veil) + 0.92 * veil for c in color))
    sky.write(Filename.fromOsSpecific(str(OUT / "expressway-sky.png")))
    (OUT / "source-manifest.json").write_text(json.dumps({
        "source": "Original dimensioned meshes authored for CoastalDrive HWY-01",
        "editable_source": "tools/environment/build_expressway_kit.py",
        "rights": "Project-authored; no third-party assets added",
        "units": "metres; +Y forward; +Z up", "assets": files,
    }, indent=2), encoding="utf-8")
    print(f"Exported {len(files)} models to {OUT}")


if __name__ == "__main__":
    build()
