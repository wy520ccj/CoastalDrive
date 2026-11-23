"""有限接触末构型与空间离散梯度；只预测求解构型，真实积分仍属于原生世界。"""

from dataclasses import dataclass, replace
from functools import cached_property

import numpy as np
from wheel_contact_kernels import (
    finite_contact_averages,
    finite_contact_frames,
    finite_radial_gradients,
    rotated_path,
)

from tire_compliance import project_deformation
from unsprung_drivetrain import tire_ports
from unsprung_motion import rotation_increment


def _average_axes(axes,angular,speed,h):
    if not speed:
        return axes
    if axes.dtype==np.float64 and angular.dtype==np.float64:
        average = np.empty((4,3))
        finite_contact_averages((axes,angular/speed),(average,),h*speed)
        return average
    # 原低精度除法与零角返回类型保持；不能先升精度再做归一化。
    return np.asarray([rotated_path(tuple(axis),tuple(angular/speed),h*speed,1.)[1] for axis in axes])


def _material_frame(previous,tangents,laterals,normals,target,initial,scales,steering,h,stiffness):
    if previous.dtype==np.float64:
        deformation,loss,velocities = np.empty((4,2)),np.empty(4),np.empty_like(steering)
        finite_contact_frames((previous,tangents,laterals,normals,target,initial,scales,steering),
                              (deformation,loss,velocities),h,.5*stiffness)
        return deformation,loss,velocities
    normal_steering = -(target-initial)/(h*scales)
    deformation,loss = [],[]
    for value,tangent,lateral,normal in zip(previous,tangents,laterals,normals):
        projected,energy = project_deformation(value,tuple(map(tuple,(tangent,lateral,normal))),stiffness)
        deformation.append(projected);loss.append(energy)
    return np.asarray(deformation),np.asarray(loss),np.column_stack((steering[:,:2],normal_steering))


@dataclass(frozen=True)
class RadialContactStep:
    geometry: object
    contacts: object
    scale: np.ndarray
    deformation: np.ndarray
    frame_loss: np.ndarray
    friction: np.ndarray
    rolling: np.ndarray


class FiniteRadialContact:
    wheel_velocity_bias = None
    finite_motion = None

    @cached_property
    def query_cache(self):
        """仅本子步静态描述的数值候选；派生属性可由旧可信检查点重建。"""
        # 纯平面批量查询比逐轮缓存更便宜；存在有限实体时才共同准备逐轮键。
        if all(surface.plane is not None for surface in self.roads.surfaces):
            return None
        return [{} for _ in self.roads.surfaces]

    def __init__(self, roads, hardware, centers, rotation, old_axes, deformation, steering, trails, dt, config, on_asphalt,
                 wheel_velocity_bias=None,finite_motion=None):
        self.roads,self.hardware,self.centers,self.rotation = roads,hardware,np.asarray(centers),rotation
        self.deformation,self.steering,self.trails = np.asarray(deformation),steering,trails
        self.dt,self.config,self.on_asphalt = dt,config,on_asphalt
        self.wheel_velocity_bias = wheel_velocity_bias
        self.finite_motion = finite_motion
        self.initial = roads.query(centers,rotation[:,2],old_axes,surface_cache=self.query_cache)
        self.target = roads.query(centers,rotation[:,2],hardware.axes,surface_cache=self.query_cache)
        self.cache_key,self.cached = None,None

    def evaluate(self, velocity):
        key = tuple(velocity[:10])
        if key==self.cache_key:
            return self.cached
        h,hardware,config = self.dt,self.hardware,self.config
        middle_rotation = rotation_increment(.5*h*velocity[3:6])
        if self.finite_motion is not None:
            motion = self.finite_motion.evaluate(velocity)
            wheel_velocity,end_rotation = motion.wheel_velocity,motion.rotation_increment
        else:
            wheel_velocity = hardware.mechanical.wheel_jacobians@velocity[:10]
            if self.wheel_velocity_bias is not None:
                wheel_velocity = wheel_velocity+self.wheel_velocity_bias
            end_rotation = rotation_increment(h*velocity[3:6])
        middle_axes = hardware.axes@middle_rotation.T
        end_axes = hardware.axes@end_rotation.T
        speed = np.linalg.norm(velocity[3:6])
        average_axes = _average_axes(hardware.axes,velocity[3:6],speed,h)
        middle = self.roads.query(self.centers+.5*h*wheel_velocity,middle_rotation@self.rotation[:,2],middle_axes,
                                 surface_cache=self.query_cache)
        end = self.roads.query(self.centers+h*wheel_velocity,end_rotation@self.rotation[:,2],end_axes,
                              surface_cache=self.query_cache)
        # 中点和末点仍逐次请求真实几何；只有相同字节/布局的数值候选可以复用。
        planes,same_plane,touching = np.zeros((4,3)),np.zeros(4),np.zeros(4)
        for i,(first,last) in enumerate(zip(self.target.hits,end.hits,strict=True)):
            touching[i] = last is not None
            if first is not None and last is not None and first.node==last.node and first.plane is not None and first.plane==last.plane:
                planes[i],same_plane[i] = first.plane[0],1.
        gradients,scales,normals,tangents,laterals = np.empty((4,16)),np.empty(4),np.empty((4,3)),np.empty((4,3)),np.empty((4,3))
        finite_radial_gradients((middle.normals,middle_axes,hardware.axes,average_axes,wheel_velocity,
            velocity[3:6],hardware.mechanical.wheel_arms,hardware.mechanical.guides,self.target.deflection,
            end.deflection,planes,same_plane,touching),(gradients,scales,normals,tangents,laterals),
            h,config.wheel_radius,config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height)
        contacts = tire_ports(hardware,middle.offsets,tangents,laterals,normals,self.steering,self.trails,
            normal_offsets=middle.normal_offsets,material_axes=middle_axes,wheel_velocity_bias=self.wheel_velocity_bias)
        # 指定转向先改变轮轴包络；这部分是执行器输入功，不充作道路输入或假耗散。
        deformation,frame_loss,steering_velocity = _material_frame(self.deformation,tangents,laterals,normals,
            self.target.deflection,self.initial.deflection,scales,contacts.steering_velocity,h,config.tire_contact_stiffness)
        contacts = replace(contacts,normal=gradients,
            steering_velocity=steering_velocity)
        friction,rolling = [],[]
        for hit in end.hits:
            asphalt = hit is None or self.on_asphalt(*hit.point[:2])
            friction.append(config.road_friction if asphalt else config.grass_friction)
            rolling.append((config.rolling_coefficient if asphalt else config.grass_rolling_coefficient)
                           if config.wheel_rolling_resistance else 0.)
        geometry = replace(end,offsets=middle.offsets,normals=normals,tangents=tangents,laterals=laterals)
        self.cache_key = key
        self.cached = RadialContactStep(geometry,contacts,scales,deformation,frame_loss,
                                       np.asarray(friction),np.asarray(rolling))
        return self.cached
