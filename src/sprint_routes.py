"""短途赛事的固定道路与门位；只描述路线，不持有车辆或物理世界。"""

from dataclasses import dataclass

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

    def medal_for(self, seconds):
        return next((medal for medal, target in zip(("金", "银", "铜"), self.targets, strict=True)
                     if seconds <= target), "")


SPRINT_ROUTES = {
    GameMode.BEND_SPRINT: SprintRoute("平路连弯", "curve", 17, (450., 900., 1350., 1800.),
        "1.8公里 · 平路连续弯\n看远处弯势，提前松油、连贯出弯", (80., 110., 155.)),
    GameMode.RIDGE_SPRINT: SprintRoute("山脊冲刺", "hills", 0, (350., 700., 1050., 1400.),
        "1.4公里 · 起伏连弯\n上坡保留动力，坡顶看清方向再加速", (65., 90., 125.)),
    GameMode.VALLEY_PACE: SprintRoute("山谷节奏", "hills", 17, (250., 400., 650., 1000.),
        "1公里 · 下谷再爬坡\n250米≥60km/h，400–650米全段35–50km/h", (70., 85., 105.),
        entry_kph=60., speed_zone=SpeedZone(400., 650., 35., 50.)),
}
