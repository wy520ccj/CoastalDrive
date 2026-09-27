"""沿现有海岸的四个明确景观段；随机只用于群落内部微变化。"""

import math
import random
from dataclasses import dataclass
from functools import lru_cache

import gltf
from panda3d.core import InternalName, MaterialAttrib, NodePath, TextureStage

from coastal_map import nearest_point, offset_point, point_at
from environment.foundation import asset_path, texture
from environment.terrain import LIGHTHOUSE_POSITION, ROCK_BEDS, base_height, ground_height

SLICE_START = 0
SLICE_END = 360


@dataclass(frozen=True)
class Placement:
    model: str
    position: tuple[float, float, float]
    scale: tuple[float, float, float]
    heading: float


# 保留旧证据工具的高度入口；新布置使用视觉地面高度。
inland_height = base_height


@lru_cache(maxsize=1)
def placements():
    rng = random.Random(214)
    items = []

    def plant(model, s, d, scale=1, heading=0):
        x, y, _ = offset_point(point_at(s), -d)
        # 岩石埋入约三成；树根埋入，花草沿地表而非漂在统一高度。
        buried = (
            0.54 if model.startswith("rock") else 0.14 if model.startswith("pine") else 0.10
        ) * scale
        radius = (
            0.8 if model.startswith("rock") else 0.28 if model.startswith("pine") else 0.2
        ) * scale
        support = min(
            ground_height(x + dx, y + dy)
            for dx, dy in ((0, 0), (radius, 0), (-radius, 0), (0, radius), (0, -radius))
        )
        items.append(Placement(model, (x, y, support - buried), (scale,) * 3, heading))

    # 起点维护区：低植被、有规律的少量路灯，留出看海空间。
    for s in (15, 46):
        plant("coastal_lamp_a", s, 8.3, 1, point_at(s).heading)
    for s, d in ((13, 8.6), (17, 9.2), (22, 8.8), (44, 10), (48, 9.2)):
        plant("bush_round_a", s, d, 0.65, rng.uniform(0, 360))
        plant("flowers_coastal_a", s + 1, d - 0.8, 0.65, rng.uniform(0, 360))
    # 三簇松林：有主树、中树、幼树；在内侧坡上形成连续林缘。
    for cs, cd in ((92, 21), (123, 27), (156, 30)):
        for i, (ds, dd, size) in enumerate(
            (
                (-8, 2, 0.9),
                (-3, -4, 1.1),
                (4, 1, 1.2),
                (9, -3, 0.85),
                (1, 7, 1),
                (-10, 8, 0.65),
                (12, 7, 0.72),
            )
        ):
            plant(
                "pine_tall_a" if i % 2 else "pine_tall_b",
                cs + ds,
                cd + dd,
                size,
                rng.uniform(0, 360),
            )
        for i in range(9):
            plant(
                "bush_round_a" if i % 2 else "bush_round_b",
                cs + rng.uniform(-12, 12),
                cd - 6 + rng.uniform(-2, 7),
                rng.uniform(0.55, 1),
                rng.uniform(0, 360),
            )
    # 坡脚岩露头：主岩与碎石有共同地质方向，不再沿路摆完整石球。
    for cs, cd, _, _ in ROCK_BEDS:
        for i, (ds, dd, size) in enumerate(
            (
                (0, 0, 2.0),
                (3, 2, 1.35),
                (-3, 1, 1.2),
                (5, -1, 0.65),
                (-5, -1, 0.5),
                (1, -3, 0.35),
                (-1, -4, 0.3),
            )
        ):
            plant(
                "rock_coastal_a" if i % 2 else "rock_coastal_b",
                cs + ds,
                cd + dd,
                size,
                26 + rng.uniform(-20, 20),
            )
        for i in range(6):
            plant(
                "flowers_coastal_a",
                cs + rng.uniform(-7, 7),
                cd + rng.uniform(-4, 3),
                rng.uniform(0.45, 0.85),
                rng.uniform(0, 360),
            )
    # 海湾与灯塔视野：低矮灌木分组，中间留空，不放无通路的房屋。
    for cs, cd in ((205, 12), (267, 10), (321, 11)):
        for i in range(5):
            plant(
                "bush_round_b",
                cs + rng.uniform(-4, 4),
                cd + rng.uniform(-1, 2),
                rng.uniform(0.4, 0.7),
                rng.uniform(0, 360),
            )
    # 弯道外侧的方向牌朝向来车；外侧岩岸上的柱脚只用现有道路标高。
    for s in (68, 91, 117, 141):
        p = point_at(s)
        x, y, z = offset_point(p, 7.2)
        # 岸坡在外侧7.2米处；使用同一连续断面插值。
        from environment.terrain import shore_point

        lo, hi = 0.0, 1.0
        for _ in range(20):
            t = (lo + hi) / 2
            q = shore_point(s, t)
            if math.hypot(q[0] - p.x, q[1] - p.y) < 7.2:
                lo = t
            else:
                hi = t
        z = shore_point(s, (lo + hi) / 2)[2]
        turn = (point_at(s + 12).heading - point_at(s - 12).heading + 180) % 360 - 180
        items.append(
            Placement(
                "road_chevron_sign_a", (x, y, z - 0.10), (-1 if turn > 0 else 1, 1, 1), p.heading
            )
        )
    items.append(Placement("lighthouse_coastal_a", LIGHTHOUSE_POSITION, (1, 1, 1), -30))
    return tuple(items)


def build_slice(parent):
    root = parent.attachNewNode("coastal-visual-slice")
    templates = {}
    for item in placements():
        if item.model not in templates:
            templates[item.model] = NodePath(
                gltf.load_model(asset_path(f"models/{item.model}.glb"))
            )
        node = templates[item.model].copyTo(root)
        node.setPos(*item.position)
        node.setScale(*item.scale)
        node.setH(item.heading)
        if item.model == "road_chevron_sign_a":
            node.setTwoSided(True)
    root.flattenStrong()
    return root


def build_terrain(parent):
    node = NodePath(gltf.load_model(asset_path("terrain/coastal-terrain.glb")))
    node.reparentTo(parent)
    stage = TextureStage("terrain-detail")
    stage.setTexcoordName(InternalName.getTexcoordName("0"))
    node.setTexture(stage, texture("ground-detail"), 1)
    return node


def dress_existing_tree(root, variant):
    """只换示范段的树冠，原树干网格、局部坐标和碰撞对应关系保留。"""
    lower, upper = root.getTightBounds()
    for path in root.findAllMatches("**/+GeomNode"):
        node = path.node()
        for index in reversed(range(node.getNumGeoms())):
            material = node.getGeomState(index).getAttrib(MaterialAttrib).getMaterial()
            if material.getName() == "leafsDark":
                node.removeGeom(index)
    crown = NodePath(gltf.load_model(asset_path(f"models/pine_tall_{variant}.glb")))
    for path in crown.findAllMatches("**/+GeomNode"):
        node = path.node()
        for index in reversed(range(node.getNumGeoms())):
            material = node.getGeomState(index).getAttrib(MaterialAttrib).getMaterial()
            if material.getName() == "Coast_bark":
                node.removeGeom(index)
    _, top = crown.getTightBounds()
    scale = (upper.z - lower.z) / top.z
    crown.setScale(scale)
    crown.setZ(lower.z)
    crown.reparentTo(root)


def road_clearance(item):
    return nearest_point(*item.position[:2])[1]
