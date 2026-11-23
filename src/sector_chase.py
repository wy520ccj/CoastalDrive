"""第一季追时基准。每场使用一份同车同路线的完整实跑。"""

from dataclasses import dataclass

from race import GameMode

CHASE_INPUT = 'game-keyboard-v32:abs-on:tcs-on:esc-on'
CHASE_VERSION = 'season-sector-chase-v1'


@dataclass(frozen=True)
class ChaseCourse:
    name: str
    labels: tuple[str, ...]
    reference: tuple[tuple[float, float, float], ...]


# 逐拍复算及原始文件哈希见 CAREER-SEASON-01。
CHASE_COURSES = {
    GameMode.TIME_TRIAL: ChaseCourse('滨海追时', ('第 1 段', '第 2 段', '第 3 段', '第 4 段', '终点段'), (
        (144.57980074419842, 13.240750425075655, 0.04638355548743379),
        (289.15960148839685, 21.448316982766187, 0.06530728100986742),
        (433.7394022325952, 35.16630322056317, 0.09290782811498093),
        (578.3192029767937, 44.42775087551525, 0.11805539496038346),
        (722.899003720992, 54.323738225263156, 0.15283292651906674),
    )),
    GameMode.VALLEY_PACE: ChaseCourse('山谷追时', ('测速门', '减速区', '限速带', '出带冲线'), (
        (375., 19.580184462707827, 0.07959391404535128),
        (400., 21.00035782211926, 0.08030932698941338),
        (650., 42.060603495859354, 0.10432010220426727),
        (1000., 59.001065845492896, 0.20228328016516822),
    )),
}
