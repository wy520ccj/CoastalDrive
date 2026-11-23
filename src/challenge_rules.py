"""同一完整驾驶的预算、用时与赛段油耗联合评价，不替代各课题的道路规则。"""

import math
from dataclasses import dataclass

from challenge_build import ALL_PARAMETERS, PRICE_VERSION, BuildDraft
from fuel import FUEL_MODEL_VERSION
from vehicle_config import VehicleConfig

MEDALS = ('铜', '银', '金')


def _finite(value, title, *, positive=False):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or value < 0 or positive and value == 0):
        raise ValueError(title+'须为有限'+('正数' if positive else '非负数'))


@dataclass(frozen=True)
class MedalTarget:
    medal: str
    seconds: float
    consumption: float

    def __post_init__(self):
        if self.medal not in MEDALS:
            raise ValueError('未知挑战奖牌')
        _finite(self.seconds, '奖牌用时', positive=True)
        _finite(self.consumption, '奖牌油耗', positive=True)


@dataclass(frozen=True)
class ChallengeSpec:
    id: str
    name: str
    base_config: VehicleConfig
    distance_m: float
    budget: int
    allowed: tuple[str, ...] = ALL_PARAMETERS
    targets: tuple[MedalTarget, ...] = ()
    version: str = 'budget-energy-v1'
    design_id: str = 'game-tuned'
    assessment: str = 'road'
    metric_label: str = ''
    metric_unit: str = ''
    metric_limits: tuple[float, ...] = ()
    road_shape: str = ''
    provisional: bool = False

    def __post_init__(self):
        _finite(self.distance_m, '规定路线长度', positive=True)
        if type(self.budget) is not int or self.budget < 0:
            raise ValueError('挑战预算须为非负整数')
        if len(set(self.allowed)) != len(self.allowed) or set(self.allowed)-set(ALL_PARAMETERS):
            raise ValueError('挑战可调参数无效')
        if self.targets:
            if tuple(target.medal for target in self.targets) != MEDALS:
                raise ValueError('挑战须按铜银金设置三档联合目标')
            for old, new in zip(self.targets, self.targets[1:]):
                if new.seconds > old.seconds or new.consumption > old.consumption:
                    raise ValueError('较高奖牌的用时和油耗要求不能放宽')
        if self.assessment not in ('road', 'lower', 'career-slalom'):
            raise ValueError('未知专项评价方式')
        if type(self.provisional) is not bool or self.provisional and (self.assessment != 'road' or not self.targets):
            raise ValueError('试行标记须对应已有联合目标的道路挑战')
        if self.assessment == 'lower':
            if len(self.metric_limits) != 3 or any(a < b for a, b in zip(self.metric_limits, self.metric_limits[1:])):
                raise ValueError('专项铜银金门槛须由宽至严')
            for value in self.metric_limits:
                _finite(value, '专项门槛')
        elif self.assessment == 'career-slalom' and len(self.metric_limits) != 1:
            raise ValueError('生涯过门须指定全门金牌时限')

    def configuration(self, build):
        return build.build(self.base_config, allowed=self.allowed)

    def evaluate(self, build, seconds, litres, *, valid=True, reason='', metric_value=None):
        self.configuration(build)
        _finite(seconds, '实际用时', positive=valid)
        if litres is not None:
            _finite(litres, '实际燃油量')
        if metric_value is not None:
            _finite(metric_value, '专项实测值')
        consumption = None if litres is None else 100_000*litres/self.distance_m
        cost = build.cost
        official = valid and cost <= self.budget and litres is not None
        medal = ''
        if not valid:
            notice = reason or '本次未有效完成'
        elif cost > self.budget:
            notice = f'试验 · 超出预算{cost-self.budget}，不计正式成绩'
        elif litres is None:
            notice = '缺少燃油记录，不计正式成绩'
        elif self.assessment != 'road':
            if metric_value is None:
                official, notice = False, '缺少专项记录，不计正式成绩'
            else:
                if self.assessment == 'lower':
                    medal = next((name for name, limit in reversed(tuple(zip(MEDALS, self.metric_limits)))
                                  if metric_value <= limit), '')
                else:
                    if type(metric_value) is not int or not 0 <= metric_value <= 5:
                        raise ValueError('通过门数须为0至5整数')
                    medal = ('金' if seconds <= self.metric_limits[0] else '银') if metric_value == 5 else '铜' if metric_value >= 3 else ''
                notice = medal+'牌完成' if medal else '有效完成，继续争取铜牌'
        elif not self.targets:
            notice = '已完成 · 评级标定中'
        else:
            medal = next((target.medal for target in reversed(self.targets)
                          if seconds <= target.seconds
                          and litres <= target.consumption*self.distance_m/100_000), '')
            notice = medal+'牌完成' if medal else '有效完成，继续争取铜牌'
            if self.provisional:
                notice += ' · 试行目标'
        next_target = None
        if official and self.targets and medal != '金':
            next_target = self.targets[MEDALS.index(medal)+1 if medal else 0]
        return ChallengeResult(self.id, self.version, build, seconds, litres, consumption,
                               cost, valid, official, medal, notice, next_target, metric_value=metric_value)


@dataclass(frozen=True)
class ChallengeResult:
    challenge_id: str
    rules_version: str
    build: BuildDraft
    seconds: float
    litres: float | None
    consumption: float | None
    cost: int
    valid: bool
    official: bool
    medal: str
    notice: str
    next_target: MedalTarget | None
    price_version: str = PRICE_VERSION
    fuel_version: str = FUEL_MODEL_VERSION
    metric_value: float | None = None

    @property
    def gaps(self):
        if self.next_target is None:
            return None
        return (max(0., self.seconds-self.next_target.seconds),
                max(0., self.consumption-self.next_target.consumption))


class EnergyWindow:
    """正式发车至终点的累计量差；只读真实快照，不积分第二份车辆状态。"""

    def __init__(self, start_litres, distance_m):
        _finite(start_litres, '发车燃油读数')
        _finite(distance_m, '规定路线长度', positive=True)
        self.start_litres, self.distance_m = start_litres, distance_m
        self.previous_litres = start_litres
        self.litres = self.progress_m = 0.
        self.finished = False

    def sample(self, total_litres, progress_m, *, finish_fraction=None):
        if self.finished:
            return
        _finite(total_litres, '累计燃油读数')
        if total_litres < self.previous_litres:
            raise ValueError('燃油累计值倒退，不能跨复位或物理世界拼接记录')
        if type(progress_m) not in (int, float) or not math.isfinite(progress_m):
            raise ValueError('赛段进度须为有限数')
        if finish_fraction is not None:
            if not 0 <= finish_fraction <= 1:
                raise ValueError('终点所在步比例须在0至1之间')
            total_litres = self.previous_litres+(total_litres-self.previous_litres)*finish_fraction
            self.finished = True
        self.previous_litres = total_litres
        self.litres = total_litres-self.start_litres
        self.progress_m = min(self.distance_m, max(self.progress_m, progress_m, 0.))

    @property
    def consumption(self):
        distance = self.distance_m if self.finished else self.progress_m
        return None if distance < 50. else 100_000*self.litres/distance

    def remaining_allowance(self, target):
        return target.consumption*self.distance_m/100_000-self.litres
