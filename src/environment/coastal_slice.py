"""现有滨海路段 0–360 m 的装饰布置，全部位于道路护栏之外。"""

import random
from dataclasses import dataclass

import gltf
from panda3d.core import NodePath

from coastal_map import nearest_point, offset_point, point_at
from environment.foundation import asset_path

SLICE_START = 0
SLICE_END = 360


@dataclass(frozen=True)
class Placement:
    model: str
    position: tuple[float, float, float]
    scale: tuple[float, float, float]
    heading: float


def inland_height(x, y):
    """与现有扇形岛面相交求高度，只用于落地装饰。"""
    from coastal_map import island_mesh

    vertices, triangles = island_mesh()
    for ia, ib, ic in triangles:
        a, b, c = vertices[ia], vertices[ib], vertices[ic]
        det = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(det) < 1e-9:
            continue
        u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / det
        v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / det
        if u >= -1e-6 and v >= -1e-6 and u + v <= 1 + 1e-6:
            return u * a[2] + v * b[2] + (1 - u - v) * c[2]
    raise ValueError(f"内陆装饰不在岛面上：{x}, {y}")


def placements():
    rng = random.Random(214)
    items = []

    def inland(model, distance, lateral, scale=1, heading=0, mirror=False):
        p = point_at(distance)
        x, y, _ = offset_point(p, lateral)
        size = (-scale if mirror else scale, scale, scale)
        sunk = 0.04
        if model == "cliff_coastal_a":
            size = (scale, scale, scale * 0.55)
            sunk = 1.5
        items.append(Placement(model, (x, y, inland_height(x, y) - sunk), size, heading))

    for distance in range(SLICE_START + 8, SLICE_END, 11):
        inland("bush_round_a" if distance % 2 else "bush_round_b", distance,
               -8.2 - rng.random() * 1.3, rng.uniform(0.8, 1.4), rng.uniform(0, 360))
        inland("flowers_coastal_a", distance + 3, -7.2, rng.uniform(0.9, 1.6), rng.uniform(0, 360))
        if distance % 3:
            inland("pine_tall_a" if distance % 2 else "pine_tall_b", distance,
                   -14 - rng.random() * 7, rng.uniform(0.8, 1.3), rng.uniform(0, 360))
    for distance in range(15, SLICE_END, 37):
        inland("rock_coastal_a" if distance % 2 else "rock_coastal_b", distance,
               -10.5, rng.uniform(1.0, 1.6), rng.uniform(0, 360))
    for distance in (45, 78, 115, 152, 193, 242, 285, 326):
        before, after = point_at(distance - 12), point_at(distance + 12)
        turn = (after.heading - before.heading + 180) % 360 - 180
        inland("road_chevron_sign_a", distance, -7.1, 1,
               point_at(distance).heading, mirror=turn > 0)
    for distance in (25, 95, 170, 260, 335):
        inland("coastal_lamp_a", distance, -8.1, 1, point_at(distance).heading)
    # 岛内丘陵挡住空旷平地；占地远离道路，不作为可驾驶地形。
    for distance, lateral, scale in ((80, -36, 3.2), (135, -34, 3.5), (200, -37, 3.8), (270, -32, 3.2)):
        inland("cliff_coastal_a", distance, lateral, scale, distance * 1.7)
    for distance, lateral in ((150, -24), (174, -28), (215, -25)):
        inland("coastal_house_a", distance, lateral, 1, point_at(distance).heading + 20)
    # 海上岩岛与灯塔：底部沉入 SEA_LEVEL，顶端接灯塔地基。
    items.extend((
        Placement("cliff_coastal_a", (146, 108, -6), (3.2, 3.2, 2.0), 25),
        Placement("lighthouse_coastal_a", (146, 108, 0.78), (1, 1, 1), 0),
        Placement("rock_coastal_b", (138, 119, -3.2), (4, 4, 3), 90),
        Placement("cliff_coastal_a", (240, 245, -6), (10, 7, 5), 75),
        Placement("cliff_coastal_a", (70, 395, -5), (17, 12, 6.5), 45),
        Placement("cliff_coastal_a", (-150, 445, -5), (22, 14, 8), 25),
    ))
    return tuple(items)


def build_slice(parent):
    root = parent.attachNewNode("coastal-visual-slice")
    templates = {}
    for item in placements():
        if item.model not in templates:
            templates[item.model] = NodePath(gltf.load_model(asset_path(f"models/{item.model}.glb")))
        node = templates[item.model].copyTo(root)
        node.setPos(*item.position)
        node.setScale(*item.scale)
        node.setH(item.heading)
        if item.model == "road_chevron_sign_a":
            # 镜像左转箭头会反转面序，双面路牌保持正反方向均可见。
            node.setTwoSided(True)
    # 显式检查仅装饰节点；不创建 Bullet body 或写入仿真 props。
    root.flattenStrong()
    return root


def road_clearance(item):
    return nearest_point(*item.position[:2])[1]
