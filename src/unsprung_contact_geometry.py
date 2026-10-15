"""有限接触末构型与空间离散梯度；只预测求解构型，真实积分仍属于原生世界。"""

from dataclasses import dataclass, replace

import numpy as np
from wheel_contact_kernels import rotated_path

from tire_compliance import project_deformation
from unsprung_drivetrain import tire_ports
from unsprung_motion import rotation_increment
from wheel_envelope import crown_extent_secant, cylinder_support


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
        wheel_velocity = hardware.mechanical.wheel_jacobians@velocity[:10]
        if self.wheel_velocity_bias is not None:
            wheel_velocity = wheel_velocity+self.wheel_velocity_bias
        middle_rotation = rotation_increment(.5*h*velocity[3:6])
        end_rotation = rotation_increment(h*velocity[3:6])
        if self.finite_motion is not None:
            motion = self.finite_motion.evaluate(velocity)
            wheel_velocity,end_rotation = motion.wheel_velocity,motion.rotation_increment
        middle_axes = hardware.axes@middle_rotation.T
        end_axes = hardware.axes@end_rotation.T
        speed = np.linalg.norm(velocity[3:6])
        average_axes = np.asarray([rotated_path(tuple(axis),tuple(velocity[3:6]/speed),h*speed,1.)[1]
                                  for axis in hardware.axes]) if speed else hardware.axes
        middle = self.roads.query(self.centers+.5*h*wheel_velocity,middle_rotation@self.rotation[:,2],middle_axes)
        end = self.roads.query(self.centers+h*wheel_velocity,end_rotation@self.rotation[:,2],end_axes)
        gradients,scales,normals = np.zeros((4,16)),np.ones(4),middle.normals.copy()
        for i,normal in enumerate(middle.normals):
            support = np.asarray(cylinder_support(tuple(-normal),tuple(middle_axes[i]),config.wheel_radius,
                config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height))
            meridian = np.cross(middle_axes[i],normal)
            squared = np.dot(meridian,meridian)
            axial_lever = np.dot(np.cross(support,normal),meridian)/squared if squared else 0.
            surface_velocity = wheel_velocity[i]+np.cross(velocity[3:6],axial_lever*middle_axes[i])
            motion = np.dot(surface_velocity,surface_velocity)
            if end.hits[i] is not None and motion>0.:
                delta_change = end.deflection[i]-self.target.deflection[i]
                first,last = self.target.hits[i],end.hits[i]
                if first is not None and first.node==last.node and first.plane is not None and first.plane==last.plane:
                    # 同一有限平面直接算小位移和包络高度割线，避免两个近似等深度相减。
                    plane_normal = np.asarray(first.plane[0])
                    eta0 = np.dot(plane_normal,hardware.axes[i])
                    eta_change = h*np.dot(plane_normal,np.cross(velocity[3:6],average_axes[i]))
                    extent = crown_extent_secant(float(eta0),float(eta0+eta_change),config.wheel_radius,
                        config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height)
                    delta_change = extent*eta_change-h*np.dot(plane_normal,wheel_velocity[i])
                desired = -delta_change/h
                normal = normal+(desired-np.dot(normal,surface_velocity))*surface_velocity/motion
            scales[i] = np.linalg.norm(normal)
            if scales[i]==0.:
                raise ArithmeticError("有限径向接触的空间梯度退化")
            normal = normal/scales[i]
            normals[i] = normal
            gradients[i,:3] = normal
            gradients[i,3:6] = np.cross(hardware.mechanical.wheel_arms[i]+axial_lever*middle_axes[i],normal)
            gradients[i,6+i] = np.dot(hardware.mechanical.guides[i],normal)
        tangents = np.cross(normals,middle_axes)
        tangents /= np.linalg.norm(tangents,axis=1)[:,None]
        laterals = np.cross(tangents,normals)
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
