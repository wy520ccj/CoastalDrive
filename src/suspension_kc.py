"""车身 +X 向右、+Y 向前、+Z 向上。轮轴指向右侧，正转角为右转。

汽车外倾以轮顶外倾为正，轮胎倾角以轮顶向轮轴正向（右）为正。
四轮始终按左前、右前、左后、右后排列。
"""

import math

from vehicle_config import VehicleConfig
from vehicle_steering import wheel_angles


def wheel_kinematics(
    center_angle_deg: float, compressions: tuple[float, float, float, float], config: VehicleConfig,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float], tuple[float, float, float, float]]:
    """返回四轮转角（度）、汽车外倾（度）及向右为正的轮胎倾角（弧度）。"""
    ack_fl, ack_fr = wheel_angles(center_angle_deg, config)
    base = (ack_fl, ack_fr, 0.0, 0.0)
    if not config.suspension_kc_enabled:
        return base, (0.0,) * 4, (0.0,) * 4
    steer, camber, inclination = [], [], []
    for i, angle in enumerate(base):
        axle = i // 2
        side = 1 if i % 2 == 0 else -1
        q = float(compressions[i])
        toe = config.static_toe_deg[axle] + config.bump_steer_gains[axle] * q
        steer_i = angle + side * toe
        camber_i = (config.static_camber_deg[axle] + config.camber_jounce_gains[axle] * q
                    + config.camber_jounce_quad[axle] * (q * q))
        steer_camber = config.camber_steer_gain * steer_i if i < 2 else 0.0
        steer.append(steer_i)
        camber.append(camber_i)
        inclination.append(math.radians(-side * camber_i + steer_camber))
    return tuple(steer), tuple(camber), tuple(inclination)


def snapshot_kc_angles(
    player, config: VehicleConfig,
) -> tuple[tuple[float, float, float, float], tuple[float, float, float, float]]:
    """从玩家快照读取四角行程和齿条角，得到四轮转角和外倾角。"""
    compressions = tuple(c.compression for c in player.wheel_contacts) or (0.0,) * 4
    steer, camber, _inclination = wheel_kinematics(player.steering, compressions, config)
    return steer, camber
