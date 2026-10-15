"""共同残差中的原生末构型预测；不积分或覆盖真实世界状态。"""

from dataclasses import dataclass

import numpy as np
from wheel_contact_kernels import rotated_path

from unsprung_dynamics import cross_matrix


def rotation_increment(vector):
    angle = np.linalg.norm(vector)
    if angle==0.:return np.eye(3)
    skew = cross_matrix(vector/angle)
    return np.eye(3)+np.sin(angle)*skew+(1-np.cos(angle))*skew@skew


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
        guide_change = h*np.cross(angular,average)
        old_arms = self.centers-self.position
        arm_change = h*(wheel_velocity-velocity[:3])
        arms = old_arms+arm_change
        # 用小位移恒等式计算压缩变化，避免两个接近的投影长度相减。
        compression = self.compression+arm_change@guide+old_arms@guide_change
        relative = np.einsum('ij,j->i',wheel_velocity-velocity[:3]-np.cross(angular,arms),guide)
        self.key = key
        self.cached = NativeEndMotion(self.centers+h*wheel_velocity,wheel_velocity,increment,compression,relative)
        return self.cached
