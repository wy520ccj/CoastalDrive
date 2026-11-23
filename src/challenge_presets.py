"""各路线实跑过的预算方案，套用后仍可继续调校。"""

from dataclasses import dataclass, replace

from challenge_build import BuildDraft
from race import GameMode


@dataclass(frozen=True)
class RoadSetup:
    title: str
    build: BuildDraft
    tab: int
    measured: tuple[float, float] | None = None


_EFFICIENCY = BuildDraft(mass=.96, drag=.95)
_TUNED_EFFICIENCY = replace(_EFFICIENCY, brake_share=.65, antiroll_share=.4)
_TUNED_FRONT = BuildDraft(front_tire=1.3, brake_share=.65, antiroll_share=.4)
_POWER = BuildDraft(power=1.15)
_BALANCED = BuildDraft(power=1.1, front_tire=1.15, rear_tire=1.15, springs=1.125, final_drive=1.075)
_FREE = BuildDraft(brake_share=.65, antiroll_share=.4)
# 数值来自同路线的完整实跑，来源见第一季任务包及历史 preset-measurements.md。
_ROAD_PRESETS = {
    ('first-drive', ''): (
        RoadSetup('原车方案', BuildDraft(), 0, (21.464, 17.366)),
        RoadSetup('加大主减速比', BuildDraft(final_drive=1.075), 0, (21.362, 16.501)),
    ),
    ('coast-sprint', ''): (
        RoadSetup('动力升级', _POWER, 0, (58.751, 23.622)),
        RoadSetup('轻量低阻', _EFFICIENCY, 0, (59.743, 20.582)),
        RoadSetup('原车方案', BuildDraft(), 0, (59.854, 21.126)),
    ),
    ('ridge-run', ''): (
        RoadSetup('原车方案', BuildDraft(), 0, (63.308, 20.988)),
        RoadSetup('轻量低阻', _TUNED_EFFICIENCY, 0, (62.995, 20.576)),
        RoadSetup('前轮调校', _TUNED_FRONT, 1, (63.267, 20.966)),
    ),
    ('coastal-cup', ''): (
        RoadSetup('动力底盘', _BALANCED, 0, (110.370, 19.825)),
        RoadSetup('轻量低阻', _EFFICIENCY, 0, (111.336, 18.760)),
        RoadSetup('原车方案', BuildDraft(), 0, (111.665, 19.108)),
    ),
    (GameMode.BEND_SPRINT.value, 'budget-bend'): (
        RoadSetup('前轮响应', BuildDraft(front_tire=1.3), 1, (92.150, 19.436)),
        RoadSetup('轻量低阻', _EFFICIENCY, 0, (93.770, 18.946)),
        RoadSetup('原车方案', BuildDraft(), 0, (93.922, 19.288)),
    ),
    (GameMode.VALLEY_PACE.value, 'budget-valley'): (
        RoadSetup('制动升级', BuildDraft(brakes=1.25, brake_share=.65, antiroll_share=.4), 1, (59.828, 20.199)),
        RoadSetup('轻量低阻', _TUNED_EFFICIENCY, 0, (59.001, 20.228)),
        RoadSetup('免费调校', _FREE, 2, (59.249, 20.743)),
    ),
    (GameMode.RIDGE_SPRINT.value, 'budget-ridge-suspension'): (
        RoadSetup('原车方案', BuildDraft(), 0, (72.295, 20.315)),
        RoadSetup('前轮与调校', _TUNED_FRONT, 1, (71.974, 20.230)),
        RoadSetup('轻量低阻', _EFFICIENCY, 0, (72.025, 19.868)),
    ),
    (GameMode.RIDGE_SPRINT.value, 'budget-ridge-long-waves'): (
        RoadSetup('前轮与调校', _TUNED_FRONT, 1, (71.477, 22.547)),
        RoadSetup('软簧与调校', replace(_TUNED_FRONT, springs=.75), 1, (70.898, 22.180)),
        RoadSetup('原车方案', BuildDraft(), 0, (72.939, 21.707)),
    ),
    (GameMode.TIME_TRIAL.value, ''): (
        RoadSetup('前轮响应', _TUNED_FRONT, 1, (54.324, 21.142)),
        RoadSetup('轻量低阻', _TUNED_EFFICIENCY, 0, (55.174, 20.996)),
        RoadSetup('免费调校', _FREE, 2, (55.290, 21.164)),
    ),
    (GameMode.SAFE_OVERTAKE.value, ''): (
        RoadSetup('原车方案', BuildDraft(), 0, (84.441, 10.979)),
        RoadSetup('轻量低阻', _TUNED_EFFICIENCY, 0, (83.788, 10.742)),
        RoadSetup('动力调校', replace(_POWER, brake_share=.65, antiroll_share=.4), 0, (83.947, 10.932)),
    ),
    (GameMode.HILL_TRAFFIC.value, ''): (
        RoadSetup('动力升级', _POWER, 0, (88.972, 11.236)),
        RoadSetup('轻量低阻', _EFFICIENCY, 0, (92.756, 10.125)),
        RoadSetup('动力底盘', _BALANCED, 1, (86.542, 11.661)),
    ),
    (GameMode.SHORT_BRAKING.value, ''): (
        RoadSetup('制动分配', BuildDraft(brake_share=.65), 2),
        RoadSetup('制动升级', BuildDraft(brakes=1.25, brake_share=.65), 1),
    ),
    (GameMode.FAST_SLALOM.value, ''): (
        RoadSetup('原车方案', BuildDraft(), 1),
        RoadSetup('前轮响应', BuildDraft(front_tire=1.3), 1),
    ),
}


_DISTANCE_PRESETS = {
    ('straight', 'normal'): (
        RoadSetup('低风阻', BuildDraft(drag=.95), 0, (188.998, 9.961)),
        RoadSetup('轻量低阻', _EFFICIENCY, 0, (172.645, 10.459)),
        RoadSetup('原车方案', BuildDraft(), 0, (189.079, 10.115)),
    ),
}


def road_setups(spec, *, distance_conditions=None):
    if spec.id == GameMode.DISTANCE_CHALLENGE.value:
        return _DISTANCE_PRESETS.get(distance_conditions, ())
    return _ROAD_PRESETS.get((spec.id, spec.road_shape), ())


def road_presets(spec, *, distance_conditions=None):
    """供既有路线复核工具读取方案名称、配置与参数页。"""
    return tuple((setup.title, setup.build, setup.tab) for setup in road_setups(spec, distance_conditions=distance_conditions))
