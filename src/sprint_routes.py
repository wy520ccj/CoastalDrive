"""短途赛事的固定道路与门位；只描述路线，不持有车辆或物理世界。"""

from dataclasses import dataclass, replace

from race import GameMode


@dataclass(frozen=True)
class SpeedZone:
    start: float
    end: float
    minimum_kph: float
    maximum_kph: float


@dataclass(frozen=True)
class SprintRoute:
    name: str
    shape: str
    seed: int
    gates: tuple[float, ...]
    description: str
    targets: tuple[float, float, float]
    entry_kph: float = 0.
    speed_zone: SpeedZone | None = None
    version: str = ''

    def medal_for(self, seconds):
        return next((medal for medal, target in zip(("金", "银", "铜"), self.targets, strict=True)
                     if seconds <= target), "")


SPRINT_ROUTES = {
    GameMode.BEND_SPRINT: SprintRoute("平路连弯", "curve", 17, (450., 900., 1350., 1800.),
        "1.8公里 · 组合弯与出口直线\n弯前制动，连续换向后再加速", (80., 110., 155.)),
    GameMode.RIDGE_SPRINT: SprintRoute("山脊冲刺", "hills", 0, (350., 700., 1050., 1400.),
        "1.4公里 · 起伏缓弯与下坡弯\n控制起伏段车身，下坡弯前减速", (65., 90., 125.)),
    GameMode.VALLEY_PACE: SprintRoute("山谷节奏", "hills", 17, (250., 400., 650., 1000.),
        "1公里 · 下谷再爬坡\n250米≥60km/h，400–650米全段35–50km/h", (70., 85., 105.),
        entry_kph=60., speed_zone=SpeedZone(400., 650., 35., 50.)),
}

VALLEY_BRAKING_VERSION = 'budget-valley-braking-v1'
VALLEY_BRAKING = replace(SPRINT_ROUTES[GameMode.VALLEY_PACE], gates=(375., 400., 650., 1000.),
                        entry_kph=80., version=VALLEY_BRAKING_VERSION,
                        description='1公里 · 下谷制动\n375米≥80km/h，400–650米全段35–50km/h')


def sprint_route(mode, version=''):
    if mode == GameMode.VALLEY_PACE and version == VALLEY_BRAKING_VERSION:
        return VALLEY_BRAKING
    return SPRINT_ROUTES[mode]


def sprint_result_route(result):
    return sprint_route(GameMode(result.route_id), result.rules_version)
