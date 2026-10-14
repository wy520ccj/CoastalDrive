"""六维车身/四轮心与曲轴/输入轴/四轮自旋的同一十六维力学端口。"""

from dataclasses import dataclass

import numpy as np

from driveline_inertia import active_inertias, rotor_weights


@dataclass(frozen=True)
class UnsprungDrivetrain:
    mechanical: object
    base_mass: np.ndarray
    mass: np.ndarray
    engine: np.ndarray
    shaft: np.ndarray
    clutch: np.ndarray
    gear: np.ndarray
    output: np.ndarray
    brakes: np.ndarray
    differential: np.ndarray
    downstream: np.ndarray
    downstream_inertias: np.ndarray
    downstream_axes: np.ndarray
    axes: np.ndarray
    engine_axis: np.ndarray
    shaft_axis: np.ndarray

    def initial_momentum(self, velocity, downstream_omega, wheel_velocities=None):
        """从动轴以前一实际转速携带动量，不把不一致旧转速悄悄改成约束值。"""
        momentum = self.base_mass@velocity+self.downstream.T@(self.downstream_inertias*downstream_omega)
        if wheel_velocities is not None:
            difference = np.asarray(wheel_velocities)-self.mechanical.wheel_jacobians@velocity[:10]
            momentum[:10] += self.mechanical.wheel_forces(self.mechanical.wheel_masses[:,None]*difference)
        return momentum

    def wheel_kinetic_correction(self, velocity, actual_wheel_velocities):
        """保留原生导向迭代留下的实际轮心动能，不先投影覆盖真实速度。"""
        predicted = self.mechanical.wheel_jacobians@velocity[:10]
        actual = np.asarray(actual_wheel_velocities)
        return .5*np.sum(self.mechanical.wheel_masses[:,None]*(actual-predicted)*(actual+predicted))

    def spin(self, velocity, config):
        return (config.engine_inertia*velocity[10]*self.engine_axis
                +config.input_shaft_inertia*velocity[11]*self.shaft_axis
                -config.wheel_inertia*np.sum(velocity[12:,None]*self.axes,axis=0)
                +np.sum((self.downstream_inertias*(self.downstream@velocity))[:,None]*self.downstream_axes,axis=0))


def drivetrain_ports(mechanics, axes, engine_axis, shaft_axis, downstream_axes, ratio, config):
    """绝对转子速度与相对壳体端口共用广义质量；从动转子按Jggᵀ消元。"""
    if not (config.finite_drivetrain and config.input_shaft_enabled and config.tire_compliance
            and config.wheel_rotor_transport):
        raise ValueError("簧下共同求解须使用完整有限传动、输入轴、弹性轮胎和机械轮轴")
    axes,engine_axis,shaft_axis,downstream_axes = map(np.asarray,(axes,engine_axis,shaft_axis,downstream_axes))
    base = np.zeros((16,16))
    base[:10,:10] = mechanics.mass_matrix
    base[10,10],base[11,11] = config.engine_inertia,config.input_shaft_inertia
    base[12:,12:] = config.wheel_inertia*np.eye(4)
    engine,shaft,brakes = np.zeros(16),np.zeros(16),np.zeros((4,16))
    engine[3:6],engine[10] = -engine_axis,1.
    shaft[3:6],shaft[11] = -shaft_axis,1.
    brakes[:,3:6],brakes[:,12:] = axes,np.eye(4)
    output = ratio*np.asarray(config.drive_weights)@brakes
    differential = np.array((brakes[0]-brakes[1],brakes[2]-brakes[3],
                             .5*(brakes[0]+brakes[1]-brakes[2]-brakes[3])))
    downstream = np.array([config.final_drive*np.asarray(weights)@brakes
                           for weights in rotor_weights(config.front_drive_share)])
    downstream[:,3:6] += downstream_axes
    inertias = (np.asarray(active_inertias(config.downstream_inertias,config.front_drive_share))
                if config.downstream_inertia_enabled else np.zeros(3))
    mass = base+downstream.T@np.diag(inertias)@downstream
    return UnsprungDrivetrain(mechanics,base,mass,engine,shaft,engine-shaft,shaft-output,output,
                             brakes,differential,downstream,inertias,downstream_axes,axes,engine_axis,shaft_axis)


@dataclass(frozen=True)
class UnsprungTirePorts:
    longitudinal: np.ndarray
    lateral: np.ndarray
    normal: np.ndarray
    radii: np.ndarray
    spin_radii: np.ndarray
    steering_velocity: np.ndarray
    guide_velocity: np.ndarray | None = None


def tire_ports(drivetrain, contact_offsets, tangents, laterals, normals, steering_angular, trails, *, normal_offsets=None,
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
            gradient[3:6] = np.cross(point,axis)
            gradient[6+i] = np.dot(mechanical.guides[i],axis)
            radius = np.dot(spin_axis,np.cross(point_offset,axis))
            if envelope_normal:
                radius = 0.
            else:
                gradient -= radius*brake
            wheel.append(gradient)
            lever.append(radius)
            relative.append(np.dot(np.cross(steer,point_offset),axis))
        rows.append(wheel)
        radii.append(lever)
        biases.append(relative)
    rows,radii = np.asarray(rows),np.asarray(radii)
    guide = None if wheel_velocity_bias is None else np.column_stack(
        [np.einsum('ij,ij->i',wheel_velocity_bias,directions) for directions in (tangents,laterals,normals)])
    return UnsprungTirePorts(rows[:,0],rows[:,1],rows[:,2],radii[:,0],radii,np.asarray(biases),guide)
