"""完整车辆子步的固定数值包；配置和世界引用不随每步传输。"""

import hashlib
from dataclasses import fields, replace

from panda3d.core import Mat3, Quat, Vec3
from physics_packet_kernels import decode, encode, layout

from suspension import SuspensionState, SuspensionStep
from vehicle_state import WheelContactState, WheelDynamicsState
from vehicle_tire_step import TireAdvanceInput, TireAdvanceResult


class NumericBodyInput:
    """保持Panda原始单精度读数；只读输入，不创建或推进物理世界。"""

    @property
    def pose(self):
        return self

    @property
    def inverse_inertia(self):
        return Mat3(*self.tensor)

    def getPos(self):
        return Vec3(*self.position)

    def getQuat(self):
        return Quat(*self.orientation)


_records = (TireAdvanceInput,TireAdvanceResult,WheelContactState,WheelDynamicsState,
            SuspensionState,SuspensionStep,NumericBodyInput)
_names = tuple(tuple(field.name for field in fields(cls)) for cls in _records[:-1]) + (
    ('position','orientation','velocity','angular','tensor','angular_damping'),)
_signature = '|'.join(cls.__module__+'.'+cls.__name__+':'+','.join(names)
                      for cls,names in zip(_records,_names)).encode()
_layout = layout(_records,_names,int.from_bytes(hashlib.sha256(_signature).digest()[:8],'little'))


def input_bytes(request):
    body = request.body
    numeric = NumericBodyInput()
    numeric.position = tuple(body.pose.getPos())
    numeric.orientation = tuple(body.pose.getQuat())
    numeric.velocity,numeric.angular = body.velocity,body.angular
    numeric.tensor = tuple(body.inverse_inertia.getCell(row,column) for row in range(3) for column in range(3))
    numeric.angular_damping = body.angular_damping
    return encode(_layout,replace(request,config=None,body=numeric,world_source=None))


def result_bytes(result):
    return encode(_layout,result)


def from_bytes(payload):
    return decode(_layout,payload)
