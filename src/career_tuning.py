"""生涯动力和悬架套件；安装标记与完整原车副本一起保存，重复安装不叠加。"""

import math
from dataclasses import replace

from tire_tuning import _install_config

POWER_GAIN = 1.12
SPRING_GAIN = 1.15
DAMPER_GAIN = math.sqrt(SPRING_GAIN)
UPGRADES = ('street-power', 'sport-suspension')


def installed_parts(vehicle):
    metadata = vehicle.parameter_metadata
    if metadata is None or 'career_parts' not in metadata:
        return set()
    parts = metadata['career_parts']
    if not isinstance(parts, list) or any(part not in UPGRADES for part in parts):
        raise ValueError('生涯改装记录无效')
    return set(parts)


def is_installed(vehicle, part):
    if part.topic == 'tires':
        return vehicle.config.lateral_stiffness == 70000.
    if part.topic == 'brakes':
        return vehicle.config.front_brake_share == .7
    return part.id in installed_parts(vehicle)


def upgraded_config(config, part_id):
    if part_id == 'street-power':
        return replace(config, torque_curve=tuple((rpm, torque*POWER_GAIN) for rpm, torque in config.torque_curve))
    if part_id != 'sport-suspension':
        raise ValueError('请选择有效的动力或悬架套件')
    curves = config.suspension_damper_curves
    return replace(config,
        suspension_spring_rates=tuple(k*SPRING_GAIN for k in config.suspension_spring_rates),
        suspension_compression_damping=tuple(c*DAMPER_GAIN for c in config.suspension_compression_damping),
        suspension_extension_damping=tuple(c*DAMPER_GAIN for c in config.suspension_extension_damping),
        suspension_damper_curves=None if curves is None else tuple(
            tuple((speed, force*DAMPER_GAIN) for speed, force in rows) for rows in curves),
        suspension_stiffness=config.suspension_stiffness*SPRING_GAIN,
        suspension_compression=config.suspension_compression*DAMPER_GAIN,
        suspension_relaxation=config.suspension_relaxation*DAMPER_GAIN)


def install(vehicle, part_id, workspace_path):
    if part_id not in UPGRADES:
        raise ValueError('请选择有效的动力或悬架套件')
    parts = installed_parts(vehicle)
    if part_id in parts:
        return vehicle
    topic = '动力' if part_id == 'street-power' else '悬架'
    return _install_config(vehicle, upgraded_config(vehicle.config, part_id), workspace_path, topic,
                           career_parts=parts | {part_id})
