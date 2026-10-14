"""完成步完整快照的原生传输布局；不裁剪遥测，不积分或预测车辆状态。"""

import hashlib
from dataclasses import fields

from physics_packet_kernels import decode, encode, layout

from impact_events import ContactState, ImpactEvent
from powertrain import PowertrainState
from simulation import Snapshot
from suspension import SuspensionState, SuspensionStep
from unsprung_state import UnsprungState
from vehicle_brakes import BrakeState
from vehicle_dynamics import DynamicsState
from vehicle_stability import StabilityState
from vehicle_state import CarState, WheelContactState, WheelDynamicsState, WheelState
from vehicle_traction import TractionState

_records = (Snapshot,CarState,WheelState,WheelContactState,WheelDynamicsState,PowertrainState,
            SuspensionState,SuspensionStep,BrakeState,DynamicsState,StabilityState,TractionState,
            ImpactEvent,ContactState,UnsprungState)
_names = tuple(tuple(field.name for field in fields(cls)) for cls in _records)
_signature = '|'.join(cls.__module__+'.'+cls.__name__+':'+','.join(names)
                      for cls,names in zip(_records,_names)).encode()
_layout = layout(_records,_names,int.from_bytes(hashlib.sha256(_signature).digest()[:8],'little'))

# 独立轮心首版已有真实速度，但没有发布加速度；旧记录不能虚构这些字段。
_acceleration_names = {"sprung_acceleration","total_center_acceleration","wheel_accelerations"}
_pre_kinematics_names = tuple(tuple(name for name in names if name not in _acceleration_names)
                              if cls is UnsprungState else names for cls,names in zip(_records,_names))
_pre_kinematics_signature = int.from_bytes(hashlib.sha256('|'.join(
    cls.__module__+'.'+cls.__name__+':'+','.join(names)
    for cls,names in zip(_records,_pre_kinematics_names)).encode()).digest()[:8],'little')
_pre_kinematics_layout = layout(_records,_pre_kinematics_names,_pre_kinematics_signature)

# SIM-ALIGN前的完整快照；新增量的零默认表示当时没有此机制，不回算历史物理。
_align_names = {"pneumatic_trail", "aligning_moment", "aligning_angular_impulse",
                "contact_steering_work", "steering_lateral_velocity"}
_legacy_records = _records[:-1]
_pre_unsprung_names = tuple(tuple(name for name in names if name!='unsprung_state')
                           if cls is CarState else names for cls,names in zip(_legacy_records,_names))
_pre_unsprung_signature = int.from_bytes(hashlib.sha256('|'.join(
    cls.__module__+'.'+cls.__name__+':'+','.join(names)
    for cls,names in zip(_legacy_records,_pre_unsprung_names)).encode()).digest()[:8],'little')
_pre_unsprung_layout = layout(_legacy_records,_pre_unsprung_names,_pre_unsprung_signature)
_legacy_names = tuple(tuple(name for name in names if name not in _align_names)
                      if cls is WheelDynamicsState else names for cls,names in zip(_legacy_records,_pre_unsprung_names))
_legacy_signature = int.from_bytes(hashlib.sha256('|'.join(
    cls.__module__+'.'+cls.__name__+':'+','.join(names)
    for cls, names in zip(_legacy_records, _legacy_names)).encode()).digest()[:8], 'little')
_legacy_layout = layout(_legacy_records, _legacy_names, _legacy_signature)


def encode_snapshots(states):
    return encode(_layout,states)


def decode_snapshots(payload):
    if payload[:4]==b'CDP1' and int.from_bytes(payload[4:12],'little')==_pre_kinematics_signature:
        return decode(_pre_kinematics_layout,payload)
    if payload[:4] == b'CDP1' and int.from_bytes(payload[4:12],'little')==_pre_unsprung_signature:
        return decode(_pre_unsprung_layout,payload)
    if payload[:4] == b'CDP1' and int.from_bytes(payload[4:12], 'little') == _legacy_signature:
        return decode(_legacy_layout,payload)
    return decode(_layout,payload)
