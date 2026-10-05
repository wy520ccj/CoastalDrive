"""设计车辆硬件；输入模式不改变同一设计的质量、传动或碰撞几何。"""

from dataclasses import dataclass, replace

from driving_modes import REFERENCE_CAR
from vehicle_config import CAR, VehicleConfig


@dataclass(frozen=True)
class VehicleDesign:
    id: str
    name: str
    config: VehicleConfig
    basis: str


# classic_coupe_v1.glb移除四轮后的实际米制网格外廓，2026-10-06实读。
# 惯量仍为明确的参考设计值，不根据显示节点缩放偷偷改变硬件。
BODY_GEOMETRY = {"collision_half_width": .994, "collision_half_length": 2.128,
                 "collision_half_height": .671692818403244,
                 "body_center_height": .7716928255558014}
REFERENCE_DESIGN = replace(REFERENCE_CAR, **BODY_GEOMETRY)
GAME_DESIGN = replace(CAR, body_inertia=REFERENCE_CAR.body_inertia, **BODY_GEOMETRY)
DESIGN_VEHICLES = (
    VehicleDesign("game-tuned", "游戏调校", GAME_DESIGN, "保留已认可的动力/输入轴调校；车身外廓取现有模型"),
    VehicleDesign("reference-rwd", "设计参考车 RWD", REFERENCE_DESIGN, "reference-v28完整设计，模型外廓同步"),
    VehicleDesign("reference-fwd", "设计参考车 FWD", replace(REFERENCE_DESIGN, front_drive_share=1.),
                  "同一参考硬件，仅前轴驱动份额1"),
    VehicleDesign("reference-awd", "设计参考车 AWD", replace(REFERENCE_DESIGN, front_drive_share=.5),
                  "同一参考硬件，前后开放中差几何份额各50%"),
)


def vehicle_design(design_id):
    """配置/车型ID边界正常报错，不回退到另一辆车。"""
    for design in DESIGN_VEHICLES:
        if design.id == design_id:
            return design
    raise ValueError(f"未知车辆设计：{design_id}")
