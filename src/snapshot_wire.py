"""完成步完整快照的原生传输布局；不裁剪遥测，不积分或预测车辆状态。"""

import hashlib
from dataclasses import fields

from physics_packet_kernels import decode, encode, layout

from impact_events import ContactState, ImpactEvent
from powertrain import PowertrainState
from simulation import Snapshot
from suspension import SuspensionState, SuspensionStep
from vehicle_brakes import BrakeState
from vehicle_dynamics import DynamicsState
from vehicle_stability import StabilityState
from vehicle_state import CarState, WheelContactState, WheelDynamicsState, WheelState
from vehicle_traction import TractionState

_records = (Snapshot,CarState,WheelState,WheelContactState,WheelDynamicsState,PowertrainState,
            SuspensionState,SuspensionStep,BrakeState,DynamicsState,StabilityState,TractionState,
            ImpactEvent,ContactState)
_names = tuple(tuple(field.name for field in fields(cls)) for cls in _records)
_signature = '|'.join(cls.__module__+'.'+cls.__name__+':'+','.join(names)
                      for cls,names in zip(_records,_names)).encode()
_layout = layout(_records,_names,int.from_bytes(hashlib.sha256(_signature).digest()[:8],'little'))


def encode_snapshots(states):
    return encode(_layout,states)


def decode_snapshots(payload):
    return decode(_layout,payload)
