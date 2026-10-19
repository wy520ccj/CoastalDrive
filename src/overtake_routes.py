"""车流赛事的固定路线与目标；不创建或改变道路交通。"""

from dataclasses import dataclass

from race import GameMode


@dataclass(frozen=True)
class OvertakeRoute:
    title: str
    shape: str
    seed: int
    distance: float
    seconds: float
    passes: int
    targets: tuple
    score_prefix: str
    finish_at_end: bool = False

    @property
    def rules(self):
        road = "固定弯坡" if self.shape == "hills" else "固定直线"
        goal = (f"跑完{self.distance/1000:g}公里，安全超越至少{self.passes}辆"
                if self.finish_at_end else f"{self.distance/1000:g}公里 / {self.seconds:g}秒内，安全超越{self.passes}辆即完成")
        medals = " · ".join(f"{medal}{seconds:g}秒" for medal, seconds in self.targets)
        return (f"{road} · 原生12车 · 使用当前车辆\n{goal}\n"
                "并行侧距至少1米；跟车/切回前后距至少10米\n"
                "从后方接近，整车超出10米才计数\n"
                "贴身/碰撞/越界/逆向/复位失败\n"+medals)


OVERTAKE_ROUTES = {
    GameMode.SAFE_OVERTAKE: OvertakeRoute("车流安全超车", "straight", 17, 2000., 150., 2,
        (("金", 85.), ("银", 110.), ("铜", 150.)), "safe-overtake-v1"),
    GameMode.HILL_TRAFFIC: OvertakeRoute("弯坡车流", "hills", 23, 2400., 180., 3,
        (("金", 110.), ("银", 140.), ("铜", 180.)), "hill-traffic-v1", finish_at_end=True),
}
