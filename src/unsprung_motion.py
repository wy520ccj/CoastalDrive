"""共同残差中的原生末构型预测；不积分或覆盖真实世界状态。"""

from dataclasses import dataclass

import numpy as np
from mechanical_kernels import cross
from wheel_contact_kernels import finite_motion_vectors, rotated_path, rotation_increment_terms


def rotation_increment(vector):
    angle = np.linalg.norm(vector)
    if angle==0.:return np.eye(3)
    terms = np.empty((9,3))
    rotation_increment_terms((np.asarray(vector/angle,dtype=float),),(terms,),np.sin(angle),1-np.cos(angle))
    return terms[3:6]+terms[6:9]@terms[:3]


def _motion_vectors(position,centers,wheel_velocity,velocity,h):
    inputs = np.asarray(position),np.asarray(centers),wheel_velocity,np.asarray(velocity[:6])
    if all(value.dtype==np.float64 for value in inputs):
        old_arms,arm_change = np.empty_like(centers),np.empty_like(wheel_velocity)
        relative = np.empty((4,3))
        finite_motion_vectors(inputs,(old_arms,arm_change,relative),h)
    else:
        # 原非双精度减法/缩放的舍入不能通过先升精度替代。
        old_arms = centers-position
        arm_change = h*(wheel_velocity-velocity[:3])
        relative = wheel_velocity-velocity[:3]-np.cross(velocity[3:6],old_arms+arm_change)
    return old_arms,arm_change,relative


@dataclass(frozen=True)
class NativeEndMotion:
    centers: np.ndarray
    wheel_velocity: np.ndarray
    rotation_increment: np.ndarray
    compression: np.ndarray
    relative_velocity: np.ndarray


class FiniteSuspensionMotion:
    def __init__(self,position,rotation,centers,compression,mechanics,bias,dt):
        self.position,self.rotation,self.centers = position,rotation,centers
        self.compression,self.mechanics,self.bias,self.dt = compression,mechanics,bias,dt
        self.key,self.cached = None,None

    def evaluate(self,velocity):
        key = tuple(velocity[:10])
        if key==self.key:return self.cached
        h,angular = self.dt,velocity[3:6]
        wheel_velocity = self.mechanics.wheel_jacobians@velocity[:10]+self.bias
        increment = rotation_increment(h*angular)
        old_guide = self.rotation[:,2]
        guide = increment@old_guide
        speed = np.linalg.norm(angular)
        average = np.asarray(rotated_path(tuple(old_guide),tuple(angular/speed),h*speed,1.)[1]) if speed else old_guide
        guide_change = h*np.asarray(cross(angular,average))
        old_arms,arm_change,relative_inputs = _motion_vectors(self.position,self.centers,wheel_velocity,velocity,h)
        # 用小位移恒等式计算压缩变化，避免两个接近的投影长度相减。
        compression = self.compression+arm_change@guide+old_arms@guide_change
        relative = np.einsum('ij,j->i',relative_inputs,guide)
        self.key = key
        self.cached = NativeEndMotion(self.centers+h*wheel_velocity,wheel_velocity,increment,compression,relative)
        return self.cached
