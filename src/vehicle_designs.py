"""设计车辆硬件；输入模式不改变同一设计的质量、传动或碰撞几何。"""

from dataclasses import dataclass, replace

from driving_modes import REFERENCE_CAR
from paths import resource_root
from vehicle_config import CAR, VehicleConfig
from vehicle_parameters import load_vehicle_config


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
REFERENCE_DESIGN = replace(REFERENCE_CAR, tire_aligning_enabled=True, **BODY_GEOMETRY)
GAME_DESIGN = replace(CAR, body_inertia=REFERENCE_CAR.body_inertia, **BODY_GEOMETRY)
GR86_PROFILE_PATH = resource_root() / "assets/game/vehicle-configs/gr86-2022-premium-6mt.json"
GR86_DESIGN = load_vehicle_config(GR86_PROFILE_PATH, REFERENCE_CAR)


def coastal_design(*, mass, length, width, height, wheelbase, radius, drive, torque, cg, weight, track=None):
    """原创车型的明确设计值；沿用同一机械模型，不冒充原厂实测。"""
    inertia = (mass*((2*length)**2+(2*height)**2)/12,
               mass*((2*width)**2+(2*height)**2)/12,
               mass*((2*length)**2+(2*width)**2)/12)
    return replace(REFERENCE_DESIGN, mass=mass, body_inertia=inertia,
        collision_half_length=length, collision_half_width=width, collision_half_height=height,
        body_center_height=height+.17, wheelbase=wheelbase, track_width=width*1.72 if track is None else track,
        wheel_radius=radius, wheel_width=.215 if mass < 1200 else .245,
        wheel_connection_height=radius+.26, center_of_mass_height=cg,
        front_drive_share=drive, front_weight_share=weight,
        torque_curve=tuple((rpm, value*torque) for rpm, value in REFERENCE_DESIGN.torque_curve),
        suspension_spring_rates=(mass*35.,)*4,
        suspension_compression_damping=(mass*3.5,)*4,
        suspension_extension_damping=(mass*2.1,)*4)


DESIGN_VEHICLES = (
    VehicleDesign("game-tuned", "游戏调校", GAME_DESIGN, "滨海公路默认调校，兼顾操控平衡与日常驾驶手感"),
    VehicleDesign("reference-rwd", "设计参考车 RWD", REFERENCE_DESIGN, "标准后驱动力学基准模型"),
    VehicleDesign("reference-fwd", "设计参考车 FWD", replace(REFERENCE_DESIGN, front_drive_share=1.),
                  "标准前驱动力学基准模型（前轴驱动份额 100%）"),
    VehicleDesign("reference-awd", "设计参考车 AWD", replace(REFERENCE_DESIGN, front_drive_share=.5),
                  "标准四驱动力学基准模型（前后开放中差 50/50 分配）"),
    VehicleDesign("gr86-2022-premium-6mt", "GR86 Premium · 6MT", GR86_DESIGN,
                  "2022 款美规 GR86 Premium 6MT，采用原厂公开几何与动力参数及工程先验配置"),
    VehicleDesign('coastal-hatch', 'Hyundai i20 · 项目调校', coastal_design(mass=1080., length=1.93, width=.90,
        height=.62, wheelbase=2.48, radius=.305, drive=1., torque=.82, cg=.43, weight=.60),
        '轻量前驱掀背工程调校，适配紧凑弯道与绕桩练习（外观基于 ANDREO12 开放模型）'),
    VehicleDesign('coastal-roadster', 'Lotus Elise · 项目调校', coastal_design(mass=1040., length=1.98, width=.90,
        height=.49, wheelbase=2.34, radius=.31, drive=0., torque=1.02, cg=.38, weight=.50),
        '轻量低质心后驱工程调校，转向响应敏捷（外观基于 Stéphane Agullo 开放模型）'),
    VehicleDesign('coastal-gt', '远航 GT', coastal_design(mass=1450., length=2.28, width=.99,
        height=.55, wheelbase=2.75, radius=.34, drive=.5, torque=1.50, cg=.43, weight=.54),
        '原创四驱旅行 GT 工程调校，兼顾高速稳定性与长途巡航性能'),
    VehicleDesign('club-coupe', 'BMW 1M Coupé · 项目调校', coastal_design(mass=1350., length=2.24, width=.95,
        height=.60, wheelbase=2.72, radius=.325, drive=0., torque=1.35, cg=.43, weight=.53, track=1.50),
        '前置后驱双门轿跑工程调校（外观改编自 Mike Pan 开放模型）'),
    VehicleDesign('subaru-wrx-sti', 'Subaru WRX STI · 项目调校', coastal_design(mass=1480., length=2.27, width=1.,
        height=.70, wheelbase=2.603, radius=.34, drive=.5, torque=1.75, cg=.49, weight=.58, track=1.54),
        '全轮驱动性能掀背工程调校（外观基于 lubomircenovsky 开放模型）'),
    VehicleDesign('porsche-930', 'Porsche 911 Turbo · 项目调校', coastal_design(mass=1200., length=2.35, width=1.,
        height=.82, wheelbase=2.343, radius=.323, drive=0., torque=1.20, cg=.45, weight=.40, track=1.57),
        '经典后驱涡轮轿跑工程调校（外观基于 Lionsharp Studios 开放模型）'),
)


def vehicle_design(design_id):
    """配置/车型ID边界正常报错，不回退到另一辆车。"""
    for design in DESIGN_VEHICLES:
        if design.id == design_id:
            return design
    raise ValueError(f"未知车辆设计：{design_id}")
