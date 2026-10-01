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


# 通用设计参考车，惯量显式取原设计车身值；曲线不包含游戏轮惯量补偿。
REFERENCE_CAR = replace(
    CAR,
    torque_curve=((900, 110), (1800, 165), (3200, 200),
                  (4500, 190), (6000, 150), (6500, 0)),
    game_speed_limits=False,
    angular_damping=0.0,
    body_inertia=(1919.56, 511.56, 2290.0),
)
