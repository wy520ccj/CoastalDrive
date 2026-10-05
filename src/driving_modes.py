"""驾驶物理配置与输入策略；独立于计时/自由驾驶等玩法。"""

from dataclasses import replace
from enum import Enum

from driver_assist import GAME_INPUT, SIMULATION_INPUT
from vehicle_config import CAR


class DrivingMode(Enum):
    GAME = "game"
    SIMULATION = "simulation"

    @property
    def label(self):
        return "正常游戏" if self == DrivingMode.GAME else "困难仿真"

    @property
    def vehicle_config(self):
        return CAR if self == DrivingMode.GAME else REFERENCE_CAR

    @property
    def input_config(self):
        return GAME_INPUT if self == DrivingMode.GAME else SIMULATION_INPUT

    def configured_vehicle(self, abs_enabled=None, tcs_enabled=None, esc_enabled=None):
        """车辆电子开关独立于输入模式；同配置沿用同一不可变实例。"""
        config = self.vehicle_config
        braking = config.braking
        traction = config.traction
        stability = config.stability
        if abs_enabled is not None and abs_enabled != braking.abs_enabled:
            braking = replace(braking, abs_enabled=abs_enabled)
        if tcs_enabled is not None and tcs_enabled != traction.tcs_enabled:
            traction = replace(traction, tcs_enabled=tcs_enabled)
        if esc_enabled is not None and esc_enabled != stability.esc_enabled:
            stability = replace(stability, esc_enabled=esc_enabled)
        if braking is config.braking and traction is config.traction and stability is config.stability:
            return config
        return replace(config, braking=braking, traction=traction, stability=stability)

    def score_variant(self, abs_enabled, tcs_enabled=True, esc_enabled=True):
        version = "game-controls-v23" if self == DrivingMode.GAME else "reference-v26"
        abs_variant = "on" if abs_enabled else "off"
        tcs_variant = "on" if tcs_enabled else "off"
        esc_variant = "on" if esc_enabled else "off"
        return f"{version}:abs-{abs_variant}:tcs-{tcs_variant}:esc-{esc_variant}"


# 通用设计参考车，惯量显式取原设计车身值；曲线不包含游戏轮惯量补偿。
REFERENCE_CAR = replace(
    CAR,
    torque_curve=((900, 110), (1800, 165), (3200, 200),
                  (4500, 190), (6000, 150), (6500, 0)),
    game_speed_limits=False,
    engine_inertia=.2,
    input_shaft_inertia=.04,
    downstream_inertias=(.03, .015, .02),
    angular_damping=0.0,
    body_inertia=(1919.56, 511.56, 2290.0),
)
