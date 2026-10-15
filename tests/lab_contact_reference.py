"""82ba3ca正式实现的只读数值对照；独立验证批量原生化，不进入生产路径。"""

import numpy as np
from mechanical_kernels import cross

from unsprung_drivetrain import UnsprungTirePorts
from wheel_envelope import crown_extent_secant, cylinder_support


def tire_ports_reference(drivetrain, contact_offsets, tangents, laterals, normals, steering_angular, trails, *, normal_offsets=None,
               material_axes=None, wheel_velocity_bias=None):
    """切向材料点与法向包络的共轭端口；显式包络法向不含轴向自旋。"""
    mechanical = drivetrain.mechanical
    rows,radii,biases = [],[],[]
    for i, (offset,tangent,lateral,normal,steer,trail) in enumerate(zip(
            contact_offsets,tangents,laterals,normals,steering_angular,trails)):
        wheel,lever,relative = [],[],[]
        spin_axis = drivetrain.axes[i] if material_axes is None else material_axes[i]
        brake = drivetrain.brakes[i]
        if material_axes is not None:
            brake = brake.copy()
            brake[3:6] = spin_axis
        # 侧向材料点保留拖距；显式法向取包络势能梯度，不把扫掠位移当材料速度。
        for direction,axis in enumerate((tangent,lateral,normal)):
            point_offset = np.asarray(offset)-trail*np.asarray(tangent) if direction==1 else np.asarray(offset)
            envelope_normal = direction==2 and normal_offsets is not None
            if envelope_normal:
                point_offset = normal_offsets[i]
            point = mechanical.wheel_arms[i]+point_offset
            gradient = np.zeros(16)
            gradient[:3] = axis
            gradient[3:6] = cross(point,axis)
            gradient[6+i] = np.dot(mechanical.guides[i],axis)
            radius = np.dot(spin_axis,cross(point_offset,axis))
            if envelope_normal:
                radius = 0.
            else:
                gradient -= radius*brake
            wheel.append(gradient)
            lever.append(radius)
            relative.append(np.dot(cross(steer,point_offset),axis))
        rows.append(wheel)
        radii.append(lever)
        biases.append(relative)
    rows,radii = np.asarray(rows),np.asarray(radii)
    guide = None if wheel_velocity_bias is None else np.column_stack(
        [np.einsum('ij,ij->i',wheel_velocity_bias,directions) for directions in (tangents,laterals,normals)])
    return UnsprungTirePorts(rows[:,0],rows[:,1],rows[:,2],radii[:,0],radii,np.asarray(biases),guide)


def finite_gradients_reference(middle, end, target, hardware, middle_axes, average_axes, wheel_velocity, angular, h, config):
    velocity = np.r_[np.zeros(3), angular]
    gradients,scales,normals = np.zeros((4,16)),np.ones(4),middle.normals.copy()
    for i,normal in enumerate(middle.normals):
        support = np.asarray(cylinder_support(tuple(-normal),tuple(middle_axes[i]),config.wheel_radius,
            config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height))
        meridian = cross(middle_axes[i],normal)
        squared = np.dot(meridian,meridian)
        axial_lever = np.dot(cross(support,normal),meridian)/squared if squared else 0.
        surface_velocity = wheel_velocity[i]+cross(velocity[3:6],axial_lever*middle_axes[i])
        motion = np.dot(surface_velocity,surface_velocity)
        if end.hits[i] is not None and motion>0.:
            delta_change = end.deflection[i]-target.deflection[i]
            first,last = target.hits[i],end.hits[i]
            if first is not None and first.node==last.node and first.plane is not None and first.plane==last.plane:
                # 同一有限平面直接算小位移和包络高度割线，避免两个近似等深度相减。
                plane_normal = np.asarray(first.plane[0])
                eta0 = np.dot(plane_normal,hardware.axes[i])
                eta_change = h*np.dot(plane_normal,cross(velocity[3:6],average_axes[i]))
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
        gradients[i,3:6] = cross(hardware.mechanical.wheel_arms[i]+axial_lever*middle_axes[i],normal)
        gradients[i,6+i] = np.dot(hardware.mechanical.guides[i],normal)
    tangents = np.cross(normals,middle_axes)
    tangents /= np.linalg.norm(tangents,axis=1)[:,None]
    laterals = np.cross(tangents,normals)
    return gradients, scales, normals, tangents, laterals
