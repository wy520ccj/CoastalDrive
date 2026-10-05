"""车型外观与明确的物理设计关联；车漆仅改变材质。"""

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Skin:
    id: str
    name: str
    color: tuple[float, float, float]


@dataclass(frozen=True)
class VehicleDefinition:
    id: str
    name: str
    visual: str
    quality: str
    player_selectable: bool
    traffic_allowed: bool
    body_scale: tuple[float, float, float] = (1, 1, 1)
    physics_id: str = "game-tuned"


SKINS = (
    Skin("orange", "原厂橙", (0.8, 0.12, 0.025)),
    Skin("blue", "海湾蓝", (0.08, 0.38, 0.8)),
    Skin("red", "赛车红", (0.75, 0.07, 0.05)),
    Skin("green", "松林绿", (0.1, 0.46, 0.25)),
    Skin("white", "珍珠白", (0.86, 0.89, 0.91)),
)

# 全部车型集中描述；质量等级只决定资产表现，不改变车辆物理。
VEHICLES = (
    VehicleDefinition(
        "sports", "经典双门 · 游戏调校", "vehicles/classic_coupe_v1.glb", "hero", True, False
    ),
    VehicleDefinition(
        "sedan",
        "经典轿车 · 游戏调校",
        "traffic-sedan.bam",
        "legacy",
        True,
        False,
        (0.91 / 0.75, 2.145 / 1.3, 1.3),
    ),
    VehicleDefinition("reference-rwd", "设计参考车 RWD", "vehicles/classic_coupe_v1.glb", "hero",
                      True, False, physics_id="reference-rwd"),
    VehicleDefinition("reference-fwd", "设计参考车 FWD", "vehicles/classic_coupe_v1.glb", "hero",
                      True, False, physics_id="reference-fwd"),
    VehicleDefinition("reference-awd", "设计参考车 AWD", "vehicles/classic_coupe_v1.glb", "hero",
                      True, False, physics_id="reference-awd"),
    VehicleDefinition(
        "traffic-compact",
        "轻巧掀背",
        "vehicles/traffic_compact_v1.glb",
        "traffic",
        False,
        True,
    ),
    VehicleDefinition(
        "traffic-sedan",
        "城市轿车",
        "vehicles/traffic_sedan_v1.glb",
        "traffic",
        False,
        True,
    ),
    VehicleDefinition(
        "traffic-wagon",
        "旅行车",
        "vehicles/traffic_wagon_v1.glb",
        "traffic",
        False,
        True,
    ),
)
PLAYER_VEHICLES = tuple(vehicle for vehicle in VEHICLES if vehicle.player_selectable)
TRAFFIC_VEHICLES = tuple(vehicle for vehicle in VEHICLES if vehicle.traffic_allowed)


def vehicle_definition(vehicle_id):
    try:
        return next(vehicle for vehicle in VEHICLES if vehicle.id == vehicle_id)
    except StopIteration:
        raise ValueError(f"Unknown vehicle: {vehicle_id}") from None


def traffic_models(seed, count):
    rng = random.Random(seed + 141)
    models = []
    while len(models) < count:
        group = [vehicle.id for vehicle in TRAFFIC_VEHICLES]
        rng.shuffle(group)
        models.extend(group)
    return tuple(models[:count])


def traffic_skins(seed, count):
    return tuple(random.Random(seed + 812).choices(range(len(SKINS)), k=count))


def paint_color(index, *, quality="legacy"):
    """PBR车辆共用线性车漆色；旧BAM保持既有颜色。"""
    if quality == "legacy":
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
    quality = model.getPythonTag("vehicle-quality") or "legacy"
    material.setBaseColor(Vec4(*paint_color(index, quality=quality), 1))
    material.setRoughness({"hero": 0.32, "traffic": 0.36}.get(quality, 0.45))
    material.setMetallic(0)
    for part in model.findAllMatches("**/paint"):
        part.setMaterial(material, 1)
