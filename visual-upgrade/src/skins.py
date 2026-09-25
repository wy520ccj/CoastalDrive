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
    Skin("orange", "原厂橙", (0.95, 0.20, 0.025)),
    Skin("blue", "海湾蓝", (0.055, 0.31, 0.72)),
    Skin("red", "赛车红", (0.76, 0.055, 0.035)),
    Skin("green", "松林绿", (0.055, 0.36, 0.18)),
    Skin("white", "珍珠白", (0.82, 0.87, 0.91)),
)

# Both bodies fit the existing 0.95 m by 2.15 m traffic-clearance half extents.
MODELS = (
    VehicleModel("sports", "运动轿跑", "player-car.bam", (1.4, 1.65, 1.3)),
    VehicleModel("sedan", "经典轿车", "traffic-sedan.bam", (0.91 / 0.75, 2.145 / 1.3, 1.3)),
)


def traffic_models(seed, count):
    return tuple(random.Random(seed + 141).choices(("sedan", "sports"), k=count))


def traffic_skins(seed, count):
    return tuple(random.Random(seed + 812).choices(range(len(SKINS)), k=count))


def apply_skin(model, index):
    from panda3d.core import Material, Vec4

    material = Material()
    material.setName("vehicle-paint")
    material.setBaseColor(Vec4(*SKINS[index].color, 1))
    material.setRoughness(0.26)
    material.setMetallic(0.22)
    for part in model.findAllMatches("**/paint"):
        part.setMaterial(material, 1)
