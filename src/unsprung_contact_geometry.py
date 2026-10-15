"""有限接触末构型与空间离散梯度；只预测求解构型，真实积分仍属于原生世界。"""

from dataclasses import dataclass, replace

import numpy as np
from wheel_contact_kernels import finite_radial_gradients, rotated_path

from tire_compliance import project_deformation
from unsprung_drivetrain import tire_ports
from unsprung_motion import rotation_increment


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

    def __init__(self, roads, hardware, centers, rotation, old_axes, deformation, steering, trails, dt, config, on_asphalt,
                 wheel_velocity_bias=None,finite_motion=None):
        self.roads,self.hardware,self.centers,self.rotation = roads,hardware,np.asarray(centers),rotation
        self.deformation,self.steering,self.trails = np.asarray(deformation),steering,trails
        self.dt,self.config,self.on_asphalt = dt,config,on_asphalt
        self.wheel_velocity_bias = wheel_velocity_bias
        self.finite_motion = finite_motion
        self.initial = roads.query(centers,rotation[:,2],old_axes)
        self.target = roads.query(centers,rotation[:,2],hardware.axes)
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
        average_axes = np.asarray([rotated_path(tuple(axis),tuple(velocity[3:6]/speed),h*speed,1.)[1]
                                  for axis in hardware.axes]) if speed else hardware.axes
        middle = self.roads.query(self.centers+.5*h*wheel_velocity,middle_rotation@self.rotation[:,2],middle_axes)
        end = self.roads.query(self.centers+h*wheel_velocity,end_rotation@self.rotation[:,2],end_axes)
        # 原生只组装已查询构型的梯度/坐标；道路中点和末点仍在上方逐次真实求交。
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
        normal_steering = -(self.target.deflection-self.initial.deflection)/(h*scales)
        contacts = replace(contacts,normal=gradients,
            steering_velocity=np.column_stack((contacts.steering_velocity[:,:2],normal_steering)))
        deformation,frame_loss = [],[]
        for previous,tangent,lateral,normal in zip(self.deformation,tangents,laterals,normals):
            projected,loss = project_deformation(previous,tuple(map(tuple,(tangent,lateral,normal))),config.tire_contact_stiffness)
            deformation.append(projected);frame_loss.append(loss)
        friction,rolling = [],[]
        for hit in end.hits:
            asphalt = hit is None or self.on_asphalt(*hit.point[:2])
            friction.append(config.road_friction if asphalt else config.grass_friction)
            rolling.append((config.rolling_coefficient if asphalt else config.grass_rolling_coefficient)
                           if config.wheel_rolling_resistance else 0.)
        geometry = replace(end,offsets=middle.offsets,normals=normals,tangents=tangents,laterals=laterals)
        self.cache_key = key
        self.cached = RadialContactStep(geometry,contacts,scales,np.asarray(deformation),np.asarray(frame_loss),
                                       np.asarray(friction),np.asarray(rolling))
        return self.cached
