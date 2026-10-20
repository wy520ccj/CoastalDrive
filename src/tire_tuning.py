"""游戏内前胎教学配方；先保存完整原车，确认写盘后再由菜单应用。"""

import hashlib
import json
import re
from dataclasses import asdict, replace

from vehicle_workspace import WorkspaceVehicle
from workshop_cornering import FRONT_STIFFNESS


def vehicle_digest(vehicle):
    return hashlib.sha256(json.dumps(asdict(vehicle), sort_keys=True, allow_nan=False).encode()).hexdigest()


def previous_path(vehicle, workspace_path):
    metadata = vehicle.parameter_metadata
    if metadata is None or 'tire_tuning_previous' not in metadata:
        return None
    name = metadata['tire_tuning_previous']
    if not isinstance(name, str) or re.fullmatch(r'[0-9a-f]{64}\.json', name) is None:
        raise ValueError('原车副本编号无效')
    return workspace_path.parent/'tuning-backups'/name


def install(vehicle, index, workspace_path):
    """主文件保存失败时不交付候选；已留存的原车副本继续可用。"""
    if type(index) is not int or not 0 <= index < len(FRONT_STIFFNESS):
        raise ValueError('请选择有效的前胎配方')
    stiffness = FRONT_STIFFNESS[index]
    if stiffness == vehicle.config.lateral_stiffness:
        return vehicle
    digest = vehicle_digest(vehicle)
    backup = workspace_path.parent/'tuning-backups'/(digest+'.json')
    if backup.exists():
        saved = WorkspaceVehicle.load(backup)
        if saved is None or vehicle_digest(saved) != digest:
            raise ValueError('原车副本与编号不一致，未覆盖副本或当前车')
    else:
        vehicle.save(backup)
    metadata = {'basis': '游戏前胎教学配方；原标定与成绩留在原车副本，当前车须重新验证。',
                'tire_tuning_previous': backup.name}
    candidate = replace(vehicle, config=replace(vehicle.config, lateral_stiffness=stiffness),
        parameter_metadata=metadata, report_path=None, workshop_result=None, scheme_id=None)
    candidate.save(workspace_path)
    return candidate


def restore(vehicle, workspace_path):
    path = previous_path(vehicle, workspace_path)
    if path is None:
        raise ValueError('当前车辆没有前胎改装副本')
    previous = WorkspaceVehicle.load(path)
    if previous is None:
        raise FileNotFoundError('原车副本不存在：'+str(path))
    if vehicle_digest(previous)+'.json' != path.name or previous.design_id != vehicle.design_id:
        raise ValueError('原车副本内容或车型不匹配，当前车辆保留')
    previous.save(workspace_path)
    return previous
