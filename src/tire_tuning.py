"""驾驶教学配方的完整原车副本；前胎与制动分配共用同一恢复链。"""

import hashlib
import json
import re
from dataclasses import asdict, replace

from vehicle_workspace import WorkspaceVehicle
from workshop import BRAKE_SHARES
from workshop_cornering import FRONT_STIFFNESS


def vehicle_digest(vehicle):
    return hashlib.sha256(json.dumps(asdict(vehicle), sort_keys=True, allow_nan=False).encode()).hexdigest()


def previous_path(vehicle, workspace_path):
    metadata = vehicle.parameter_metadata
    if metadata is None or not ({'tuning_previous', 'tire_tuning_previous'} & metadata.keys()):
        return None
    name = metadata['tuning_previous'] if 'tuning_previous' in metadata else metadata['tire_tuning_previous']
    if not isinstance(name, str) or re.fullmatch(r'[0-9a-f]{64}\.json', name) is None:
        raise ValueError('原车副本编号无效')
    return workspace_path.parent/'tuning-backups'/name


def install(vehicle, index, workspace_path):
    """主文件保存失败时不交付候选；已留存的原车副本继续可用。"""
    if type(index) is not int or not 0 <= index < len(FRONT_STIFFNESS):
        raise ValueError('请选择有效的前胎配方')
    stiffness = FRONT_STIFFNESS[index]
    return _install_config(vehicle, replace(vehicle.config, lateral_stiffness=stiffness), workspace_path, '前胎')


def install_brakes(vehicle, index, workspace_path):
    if type(index) is not int or not 0 <= index < len(BRAKE_SHARES):
        raise ValueError('请选择有效的前制动分配')
    return _install_config(vehicle, replace(vehicle.config, front_brake_share=BRAKE_SHARES[index]), workspace_path, '制动分配')


def _install_config(vehicle, config, workspace_path, topic, *, career_parts=None):
    if config == vehicle.config:
        return vehicle
    digest = vehicle_digest(vehicle)
    backup = workspace_path.parent/'tuning-backups'/(digest+'.json')
    if backup.exists():
        saved = WorkspaceVehicle.load(backup)
        if saved is None or vehicle_digest(saved) != digest:
            raise ValueError('原车副本与编号不一致，未覆盖副本或当前车')
    else:
        vehicle.save(backup)
    metadata = {'basis': f'游戏{topic}教学配方；原标定与成绩留在原车副本，当前车须重新验证。',
                'tuning_previous': backup.name}
    if career_parts is not None:
        metadata['career_parts'] = sorted(career_parts)
    elif vehicle.parameter_metadata is not None and 'career_parts' in vehicle.parameter_metadata:
        metadata['career_parts'] = vehicle.parameter_metadata['career_parts']
    candidate = replace(vehicle, config=config,
        parameter_metadata=metadata, report_path=None, workshop_result=None, scheme_id=None)
    candidate.save(workspace_path)
    return candidate


def restore(vehicle, workspace_path):
    path = previous_path(vehicle, workspace_path)
    if path is None:
        raise ValueError('当前车辆没有改装副本')
    previous = WorkspaceVehicle.load(path)
    if previous is None:
        raise FileNotFoundError('原车副本不存在：'+str(path))
    if vehicle_digest(previous)+'.json' != path.name or previous.design_id != vehicle.design_id:
        raise ValueError('原车副本内容或车型不匹配，当前车辆保留')
    previous.save(workspace_path)
    return previous
