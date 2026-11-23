"""挑战工程参数与最终方案报价；每次只从本关原车生成，不累计安装。"""

import math
from dataclasses import dataclass, fields, replace
from decimal import ROUND_CEILING, Decimal

PRICE_VERSION = 'engineering-price-v1'


@dataclass(frozen=True)
class EngineeringParameter:
    key: str
    title: str
    minimum: float
    maximum: float
    extent: str
    maximum_cost: int


HARDWARE = (
    EngineeringParameter('power', '发动机扭矩', 1., 1.20, '.20', 6000),
    EngineeringParameter('mass', '车身质量', .92, 1., '.08', 8000),
    EngineeringParameter('drag', '风阻面积', .88, 1., '.12', 6000),
    EngineeringParameter('front_tire', '前轴侧偏刚度', .70, 1.30, '.30', 2000),
    EngineeringParameter('rear_tire', '后轴侧偏刚度', .70, 1.30, '.30', 2000),
    EngineeringParameter('brakes', '最大制动扭矩', 1., 1.30, '.30', 2400),
    EngineeringParameter('springs', '弹簧刚度', .75, 1.25, '.25', 1500),
    EngineeringParameter('dampers', '减振阻尼', .75, 1.25, '.25', 1500),
    EngineeringParameter('final_drive', '主减速比', .85, 1.15, '.15', 1800),
)
ADJUSTMENTS = ('brake_share', 'antiroll_share')
ALL_PARAMETERS = tuple(item.key for item in HARDWARE) + ADJUSTMENTS


def _check_number(value, low, high, title):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{title}须在{low:g}至{high:g}之间')


@dataclass(frozen=True)
class BuildDraft:
    power: float = 1.
    mass: float = 1.
    drag: float = 1.
    front_tire: float = 1.
    rear_tire: float = 1.
    brakes: float = 1.
    springs: float = 1.
    dampers: float = 1.
    final_drive: float = 1.
    brake_share: float | None = None
    antiroll_share: float | None = None

    def __post_init__(self):
        for item in HARDWARE:
            _check_number(self.value(item.key), item.minimum, item.maximum, item.title)
        if self.brake_share is not None:
            _check_number(self.brake_share, .40, .80, '前制动份额')
        if self.antiroll_share is not None:
            _check_number(self.antiroll_share, .05, .95, '前防倾份额')

    def value(self, key):
        # 字段目录来自内部固定接口；不允许用任意配置字段绕过本关参数约束。
        if key not in ALL_PARAMETERS:
            raise ValueError('未知挑战改装参数：'+key)
        return self.__dict__[key]

    def changed(self):
        return tuple(item.name for item in fields(self)
                     if self.value(item.name) != (None if item.name in ADJUSTMENTS else 1.))

    def costs(self):
        result = {}
        for item in HARDWARE:
            x = abs(Decimal(str(self.value(item.key))) - 1) / Decimal(item.extent)
            amount = Decimal(item.maximum_cost) * (x + x*x) / 2
            result[item.key] = int((amount/10).to_integral_value(rounding=ROUND_CEILING))*10
        return result

    @property
    def cost(self):
        return sum(self.costs().values())

    def build(self, base, *, allowed=ALL_PARAMETERS):
        if any(key not in ALL_PARAMETERS for key in allowed):
            raise ValueError('挑战包含未知可调参数')
        blocked = set(self.changed()) - set(allowed)
        if blocked:
            raise ValueError('本关不可修改：'+'、'.join(sorted(blocked)))
        if not self.changed():
            return base
        values = {}
        if self.power != 1.:
            values['torque_curve'] = tuple((rpm, torque*self.power) for rpm, torque in base.torque_curve)
        if self.mass != 1.:
            values['mass'] = base.mass*self.mass
            if base.body_inertia is not None:
                values['body_inertia'] = tuple(value*self.mass for value in base.body_inertia)
        if self.drag != 1.:
            values['drag_coefficient'] = base.drag_coefficient*self.drag
        if self.front_tire != 1.:
            values['lateral_stiffness'] = base.lateral_stiffness*self.front_tire
        if self.rear_tire != 1.:
            values['rear_lateral_stiffness'] = base.rear_lateral_stiffness*self.rear_tire
        if self.brakes != 1.:
            values['brake_torque'] = base.brake_torque*self.brakes
        if self.final_drive != 1.:
            values['final_drive'] = base.final_drive*self.final_drive
        if self.springs != 1.:
            values['suspension_spring_rates'] = tuple(value*self.springs for value in base.suspension_spring_rates)
            values['suspension_spring_preloads'] = tuple(value*self.springs for value in base.suspension_spring_preloads)
            values['suspension_stiffness'] = base.suspension_stiffness*self.springs
        if self.dampers != 1.:
            for key in ('suspension_compression_damping', 'suspension_extension_damping'):
                values[key] = tuple(value*self.dampers for value in base.__dict__[key])
            values['suspension_compression'] = base.suspension_compression*self.dampers
            values['suspension_relaxation'] = base.suspension_relaxation*self.dampers
            if base.suspension_damper_curves is not None:
                values['suspension_damper_curves'] = tuple(tuple((speed, force*self.dampers)
                    for speed, force in curve) for curve in base.suspension_damper_curves)
        if self.brake_share is not None:
            values['front_brake_share'] = self.brake_share
        if self.antiroll_share is not None:
            total = sum(base.suspension_antiroll_rates)
            if total <= 0:
                raise ValueError('原车没有可分配的防倾刚度')
            values['suspension_antiroll_rates'] = total*self.antiroll_share, total*(1-self.antiroll_share)
        return replace(base, **values)
