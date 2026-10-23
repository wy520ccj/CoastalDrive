"""车库手动调校；数值直接生成同一VehicleConfig，原车备份沿用工坊恢复链。"""

import math
from dataclasses import asdict, dataclass, replace

from tire_tuning import _install_config


@dataclass(frozen=True)
class SetupField:
    key: str
    title: str
    unit: str
    field: str
    indices: tuple
    factor: float
    low: float
    high: float


GROUPS = {'tires': '轮胎', 'brakes': '制动', 'front': '前悬架', 'rear': '后悬架', 'drive': '传动'}
FIELDS = {
    'tires': (
        SetupField('front_tire', '前轮侧偏刚度', 'kN/rad', 'lateral_stiffness', (), 1000., 20., 120.),
        SetupField('rear_tire', '后轮侧偏刚度', 'kN/rad', 'rear_lateral_stiffness', (), 1000., 20., 120.)),
    'brakes': (
        SetupField('brake_share', '前轴制动力份额', '%', 'front_brake_share', (), .01, 45., 80.),
        SetupField('brake_torque', '总制动扭矩', 'N·m', 'brake_torque', (), 1., 1500., 8000.)),
    'front': (
        SetupField('front_spring', '前弹簧', 'kN/m', 'suspension_spring_rates', (0, 1), 1000., 10., 150.),
        SetupField('front_bump', '前压缩阻尼', 'kN·s/m', 'suspension_compression_damping', (0, 1), 1000., .5, 15.),
        SetupField('front_rebound', '前回弹阻尼', 'kN·s/m', 'suspension_extension_damping', (0, 1), 1000., .5, 15.),
        SetupField('front_bar', '前防倾杆刚度', 'kN/m', 'suspension_antiroll_rates', (0,), 1000., 0., 100.)),
    'rear': (
        SetupField('rear_spring', '后弹簧', 'kN/m', 'suspension_spring_rates', (2, 3), 1000., 10., 150.),
        SetupField('rear_bump', '后压缩阻尼', 'kN·s/m', 'suspension_compression_damping', (2, 3), 1000., .5, 15.),
        SetupField('rear_rebound', '后回弹阻尼', 'kN·s/m', 'suspension_extension_damping', (2, 3), 1000., .5, 15.),
        SetupField('rear_bar', '后防倾杆刚度', 'kN/m', 'suspension_antiroll_rates', (1,), 1000., 0., 100.)),
    'drive': (
        SetupField('final_drive', '主减速比', '', 'final_drive', (), 1., 2., 6.),
        SetupField('front_diff', '前差速器阻尼', 'N·m·s/rad', 'differential_damping', (0,), 1., 0., 200.),
        SetupField('rear_diff', '后差速器阻尼', 'N·m·s/rad', 'differential_damping', (1,), 1., 0., 200.),
        SetupField('front_cap', '前差速器耦合上限', 'N·m', 'differential_capacity', (0,), 1., 0., 1000.),
        SetupField('rear_cap', '后差速器耦合上限', 'N·m', 'differential_capacity', (1,), 1., 0., 1000.)),
}
BY_KEY = {field.key: field for fields in FIELDS.values() for field in fields}
HELP = {
    'tires': '前轮更硬通常响应更快；前后差异会改变转向平衡。数值是轮胎模型标定值。',
    'brakes': '前轴份额决定制动力分配；总扭矩影响制动能力，过大仍会触发ABS。',
    'front': '弹簧支撑车身；阻尼控制压缩和回弹；防倾杆影响前后侧倾分配。',
    'rear': '左右轮同步调整。前后悬架共同决定车身响应，去工坊比较制动与转向。',
    'drive': '减速比影响加速与转速；差速器须同时有阻尼和耦合上限才产生作用。',
}


def values(config):
    document = asdict(config)
    return {field.key: (document[field.field][field.indices[0]] if field.indices else document[field.field])/field.factor
            for field in BY_KEY.values()}


def candidate(config, changes):
    original, updated = values(config), {}
    for key, raw in changes.items():
        field = BY_KEY[key]
        value = float(raw)
        if not math.isfinite(value) or not field.low <= value <= field.high:
            raise ValueError(f'{field.title}须在{field.low:g}至{field.high:g}{field.unit}之间')
        if value == original[key]:
            continue
        if field.indices:
            if field.field not in updated:
                updated[field.field] = list(asdict(config)[field.field])
            for index in field.indices:
                updated[field.field][index] = value*field.factor
        else:
            updated[field.field] = value*field.factor
    for name in ('suspension_spring_rates', 'suspension_compression_damping', 'suspension_extension_damping',
                 'suspension_antiroll_rates', 'differential_damping', 'differential_capacity'):
        if name in updated:
            updated[name] = tuple(updated[name])
    if config.suspension_damper_curves is not None and any('bump' in key or 'rebound' in key for key in changes
                                                         if float(changes[key]) != original[key]):
        raise ValueError('当前车使用非线性阻尼曲线，请到工坊编辑曲线，车库未替换原曲线')
    return replace(config, **updated)


def install(vehicle, changes, path):
    return _install_config(vehicle, candidate(vehicle.config, changes), path, '手动调校')
