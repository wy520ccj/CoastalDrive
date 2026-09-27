"""Stable appearance IDs; choosing a body or paint never changes driving physics."""

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Skin:
    id: str
    name: str
    color: tuple[float, float, float]


@dataclass(frozen=True)
class VehicleModel:
    id: str
    name: str
    filename: str
    body_scale: tuple[float, float, float]


SKINS = (
    Skin("orange", "原厂橙", (0.8, 0.12, 0.025)),
    Skin("blue", "海湾蓝", (0.08, 0.38, 0.8)),
    Skin("red", "赛车红", (0.75, 0.07, 0.05)),
    Skin("green", "松林绿", (0.1, 0.46, 0.25)),
    Skin("white", "珍珠白", (0.86, 0.89, 0.91)),
)

# Both bodies fit the existing 0.95 m by 2.15 m traffic-clearance half extents.
MODELS = (
    VehicleModel("sports", "经典双门", "player-car.bam", (1.4, 1.65, 1.3)),
    VehicleModel("sedan", "经典轿车", "traffic-sedan.bam", (0.91 / 0.75, 2.145 / 1.3, 1.3)),
)


def traffic_models(seed, count):
    return tuple(random.Random(seed + 141).choices(("sedan", "sports"), k=count))


def traffic_skins(seed, count):
    return tuple(random.Random(seed + 812).choices(range(len(SKINS)), k=count))


def paint_color(index, *, hero=False):
    """新PBR车漆把显示色转为线性反射率；旧BAM保持既有颜色。"""
    if not hero:
        return SKINS[index].color
    color = (
        (0.90, 0.43, 0.10),
        (0.12, 0.45, 0.78),
        (0.78, 0.08, 0.055),
        (0.16, 0.46, 0.28),
        (0.85, 0.87, 0.86),
    )[index]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in color)


def apply_skin(model, index):
    from panda3d.core import Material, Vec4

    material = Material()
    material.setName("vehicle-paint")
    hero = model.getName() == "classic-coupe-v1"
    material.setBaseColor(Vec4(*paint_color(index, hero=hero), 1))
    material.setRoughness(0.32 if hero else 0.45)
    material.setMetallic(0)
    for part in model.findAllMatches("**/paint"):
        part.setMaterial(material, 1)
