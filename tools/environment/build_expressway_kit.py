"""离线制作原创快速路模块；尺寸源即为可编辑美术源文件。"""

import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, NodePath, Vec4

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

    from build_expressway_signs import build_models

    assets.update(build_models())
    files = []
    for name, root in assets.items():
        root.flattenStrong()
        path = OUT / f"{name}.bam"
        root.writeBamFile(Filename.fromOsSpecific(str(path)))
        files.append({"name": name, "file": path.name,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    from make_expressway_surfaces import build as build_surfaces

    build_surfaces()
    (OUT / "source-manifest.json").write_text(json.dumps({
        "source": "Original dimensioned meshes authored for CoastalDrive HWY-01",
        "editable_source": "tools/environment/build_expressway_kit.py",
        "rights": "Project-authored; no third-party assets added",
        "units": "metres; +Y forward; +Z up", "assets": files,
    }, indent=2), encoding="utf-8")
    print(f"Exported {len(files)} models to {OUT}")


if __name__ == "__main__":
    build()
