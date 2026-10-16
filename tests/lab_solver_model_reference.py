"""簧下/径向/切向接触与有限传动的共同末状态；构型由外层真实几何刷新。"""

import math
from dataclasses import dataclass, replace

import numpy as np
from mechanical_kernels import cross, unsprung_contact_residual, unsprung_port_residual
from wheel_contact_kernels import unsprung_body_torque, unsprung_momentum_values

from tire_compliance import energy_terms
from tire_properties import tire_grip, tire_stiffness
from unsprung_contact import normal_material, suspension_potential
from unsprung_dynamics import native_gyro_impulse
from wheel_dynamics import WheelStep


def dry_port_derivative(port, torque, speed, capacity, impulse_response):
    """固定容量投影残差的分段导数；不让差分跨过静止/滑动边界。"""
    # 残差为T-clip(T+v/(hR),-C,C)。静止分支解v=0，滑动分支解T=±C。
    if capacity > 0. and abs(torque+speed/impulse_response) < capacity:
        return -port/impulse_response, 0.
    return np.zeros_like(port), 1.


@dataclass(frozen=True)
class UnsprungJointStep:
    velocity: np.ndarray
    compression: np.ndarray
    tire_deflection: np.ndarray
    normal: object
    wheels: tuple
    forces: np.ndarray
    port_torques: np.ndarray
    downstream_omega: np.ndarray
    rolling_torques: np.ndarray
    force_parameters: np.ndarray
    drive_torque: float
    kinetic_change: float
    kinetic_numerical_loss: float
    potential_change: float
    material_loss: float
    contact_numerical_loss: float
    road_loss: float
    port_heat: np.ndarray
    rolling_heat: float
    engine_work: float
    engine_heat: float
    known_work: float
    steering_work: float
    road_work: float
    energy_error: float
    momentum_error: float
    force_error: float
    port_error: float
    iterations: int
    contact_geometry: object | None = None
    normal_coefficients: np.ndarray | None = None
    normal_scale: np.ndarray | None = None
    guide_work: float = 0.
    body_gyro_work: float = 0.
    suspension_geometry_work: float = 0.
    suspension_relative_velocity: np.ndarray | None = None


def make_joint_model(hardware, contacts, velocity, downstream_omega, compression, tire_deflection,
                         deformations, initial_force, known_force, road_delta, radial_rates, radial_damping,
                         friction, rolling_coefficients, engine_torque, engine_drag, clutch_capacity,
                         brake_capacities, ratio, synchronizing, dt, config, *, wheel_initial_velocity=None,
                         finite_contact=None, wheel_velocity_bias=None, wheel_known_force=None,
                         native_body_gyro=False, body_external_torque=None,finite_motion=None):
    """同时解十六速度、八接触力和十有限端口，不在结束后修补轮速/轮荷。

    本函数保持当前构型的质量/力端口，有限姿态与真实世界接点须由外层联立。
    known_force含外层已知广义力，惯性偏置应在外层按同一构型处理。
    原生轮心速度若带有限导向误差，显式传入并保留其动量/动能，而不是先强设到导向速度。
    """
    start = np.asarray(velocity)
    old_down = np.asarray(downstream_omega)
    q0,delta0,previous = map(np.asarray,(compression,tire_deflection,deformations))
    known,road,rates,radial_c,mu,rolling_c,brakes = map(np.asarray,
        (known_force,road_delta,radial_rates,radial_damping,friction,rolling_coefficients,brake_capacities))
    gx = contacts.longitudinal
    if finite_contact is not None and np.any(road!=0.):
        raise ValueError("有限真实静态接触不接受额外道路位移输入")
    gs = np.zeros((4,16))
    gs[:,6:10] = np.eye(4)
    ports = np.vstack((hardware.clutch,hardware.gear,hardware.output,hardware.brakes,hardware.differential))
    inertia = hardware.mass
    actual_wheels = (hardware.mechanical.wheel_jacobians@start[:10] if wheel_initial_velocity is None
                     else np.asarray(wheel_initial_velocity))
    if actual_wheels.shape!=(4,3) or not np.isfinite(actual_wheels).all():
        raise ValueError("原生轮心初速须为四个有限世界三维速度")
    momentum = hardware.initial_momentum(start,old_down,actual_wheels)
    bias = np.zeros((4,3)) if wheel_velocity_bias is None else np.asarray(wheel_velocity_bias)
    wheel_known = np.zeros((4,3)) if wheel_known_force is None else np.asarray(wheel_known_force)
    if bias.shape!=(4,3) or wheel_known.shape!=(4,3) or not np.isfinite(bias).all() or not np.isfinite(wheel_known).all():
        raise ValueError("轮心导向速度与已知外力须为四个有限世界三维向量")
    momentum[:10] -= hardware.mechanical.wheel_forces(hardware.mechanical.wheel_masses[:,None]*bias)
    external_torque = np.zeros(3) if body_external_torque is None else np.asarray(body_external_torque)
    response = np.diag(ports@np.linalg.solve(inertia,ports.T))
    rolling = np.maximum(np.abs(gx@start+contacts.radii*start[12:]),np.abs(contacts.radii*start[12:]))>=config.static_contact_speed
    rolling_flags = rolling.astype(float)
    port_settings = (dt,ratio,synchronizing,config.front_drive_share,config.final_drive,
                     config.drivetrain_efficiency,clutch_capacity,config.synchronizer_capacity)
    port_tuning = tuple(np.asarray(values,dtype=float) for values in
                        (config.differential_capacity,config.axle_torque_bias_ratios,config.differential_damping))
    state_scale = np.r_[np.ones(10),np.full(6,100.),np.full(8,1000.),np.full(10,100.)]
    row_scale = np.r_[np.maximum(np.diag(inertia)*state_scale[:16],1.),np.full(8,1000.),np.full(10,100.)]

    configuration_key,configuration_data = None,None
    velocity_key,velocity_data = None,None
    force_key,force_data = None,None
    torque_key,torque_data = None,None
    configuration_base_key,configuration_base_data = None,None
    velocity_base_key,velocity_base_data = None,None
    force_base_key,force_base_data = None,None
    gyro_cache = {}

    def configuration(end):
        nonlocal configuration_key,configuration_data
        # 有限接触/行程只依赖车身和轮心十速度；旧冻结法向端口仍可含自旋，须用全部速度。
        key = (end[:10] if finite_contact is not None else end).tobytes()
        if key==configuration_key:
            return configuration_data
        if key==configuration_base_key:
            configuration_key,configuration_data = key,configuration_base_data
            return configuration_data
        kinematics = finite_contact.evaluate(end) if finite_contact is not None else None
        active = contacts if kinematics is None else kinematics.contacts
        gn = active.normal
        guide = np.zeros((4,3)) if active.guide_velocity is None else active.guide_velocity
        local_previous = previous if kinematics is None else kinematics.deformation
        local_mu = mu if kinematics is None else kinematics.friction
        local_rolling = rolling_c if kinematics is None else kinematics.rolling
        scale = np.ones(4) if kinematics is None else kinematics.scale
        eligible = np.ones(4) if kinematics is None else np.array([hit is not None for hit in kinematics.geometry.hits])
        q = q0+dt*end[6:10]
        suspension_velocity = end[6:10]
        if finite_motion is not None:
            motion = finite_motion.evaluate(end)
            q,suspension_velocity = motion.compression,motion.relative_velocity
        delta = (delta0+road-dt*(gn@end+active.steering_velocity[:,2]+guide[:,2]) if kinematics is None
                 else kinematics.geometry.deflection)
        coefficients = normal_material(q,suspension_velocity,delta,delta0,dt,config,rates*eligible,radial_c*eligible)
        normal = coefficients if kinematics is None else replace(coefficients,normal_force=coefficients.normal_force*scale)
        parameters = []
        for i in range(4):
            car = config if i<2 else config_rear
            load = float(normal.normal_force[i])
            grip = tire_grip(load,local_mu[i],car)
            cx,cy = tire_stiffness(load,car)
            parameters.append((grip,cx,cy))
        configuration_key = key
        configuration_data = (kinematics,active,guide,local_previous,local_rolling,scale,q,
                              suspension_velocity,delta,coefficients,normal,np.asarray(parameters))
        return configuration_data

    def velocity_terms(end):
        nonlocal velocity_key,velocity_data
        key = end.tobytes()
        if key==velocity_key:
            return velocity_data
        if key==velocity_base_key:
            velocity_key,velocity_data = key,velocity_base_data
            return velocity_data
        geometry = configuration(end)
        _kinematics,active,guide,_previous,local_rolling,_scale,_q,_u,_delta,_coefficients,normal,_parameters = geometry
        gx,gy,gn = active.longitudinal,active.lateral,active.normal
        down = hardware.downstream@end
        inertial_torques = hardware.downstream_inertias*(down-old_down)/dt
        speeds = ports@end
        contact_speeds = np.column_stack((gx@end,gy@end,gn@end))+active.steering_velocity+guide
        rolling_torque = local_rolling*normal.normal_force*active.radii**2*end[12:] / np.maximum(
            np.abs(active.radii*end[12:]),config.rolling_transition_speed)
        engine_reaction = known+engine_torque*hardware.engine-engine_drag*np.dot(hardware.engine,end)*hardware.engine
        # 原反力表达式的连续前缀；只依赖本次完整速度/构型，保持矩阵及加减顺序。
        reaction_base = engine_reaction-gs.T@normal.suspension_force+gn.T@normal.normal_force
        rotor_bias = np.zeros(16)
        rotor_bias[3:6] = cross(end[3:6],hardware.spin(end,config))
        free_momentum = inertia@end-momentum
        velocity_key = key
        velocity_data = (geometry,down,inertial_torques,speeds,contact_speeds,rolling_torque,
                         reaction_base,rotor_bias,free_momentum)
        return velocity_data

    def evaluate(values):
        nonlocal force_key,force_data,torque_key,torque_data
        end,forces,torques = values[:16],values[16:24].reshape(4,2),values[24:]
        geometry,down,inertial_torques,speeds,contact_speeds,rolling_torque,reaction_base,rotor_bias,free_momentum = velocity_terms(end)
        kinematics,active,_guide,local_previous,_rolling,scale,q,suspension_velocity,delta,coefficients,normal,parameters = geometry
        gx,gy,gn = active.longitudinal,active.lateral,active.normal
        loss = torques[2]
        output_torque = ratio*(torques[1]-loss)
        # 扭矩扰动不改变本速度与八接触力的原反力前缀/轮心力；不跨共同解复用。
        current_force_key = velocity_key,forces.tobytes()
        if current_force_key!=force_key:
            if current_force_key==force_base_key:
                force_data = force_base_data
            else:
                force_reaction = reaction_base+gx.T@forces[:,0]+gy.T@forces[:,1]
                wheel_force = (forces[:,0,None]*gx[:,:3]+forces[:,1,None]*gy[:,:3]+normal.normal_force[:,None]*gn[:,:3]
                               -normal.suspension_force[:,None]*hardware.mechanical.guides+wheel_known) if native_body_gyro else None
                force_data = force_reaction,wheel_force
            force_key = current_force_key
        force_reaction,wheel_force = force_data
        # ports在本次共同解内固定，完整十扭矩字节相同才复用原矩阵投影。
        current_torque_key = torques.tobytes()
        if current_torque_key!=torque_key:
            torque_data = ports.T@torques
            torque_key = current_torque_key
        reaction,residual = np.empty(16),np.empty(34)
        unsprung_momentum_values((force_reaction,torque_data,rolling_torque,rotor_bias,free_momentum),
                                 (reaction,residual),dt)
        gyro = np.zeros(3)
        if native_body_gyro:
            body_torque = np.empty(3)
            unsprung_body_torque((hardware.mechanical.wheel_arms,wheel_force,reaction,rotor_bias),(body_torque,))
            free_angular = start[3:6]+dt*np.linalg.solve(hardware.mechanical.world_inertia,body_torque-external_torque)
            # 本次共同解内惯量和dt固定；仅复用自由角速度字节完全相同的原隐式陀螺。
            gyro_key = free_angular.tobytes()
            if gyro_key not in gyro_cache:
                gyro_cache[gyro_key] = native_gyro_impulse(hardware.mechanical.world_inertia,free_angular,dt)
            gyro = gyro_cache[gyro_key]
            residual[3:6] -= gyro
        # 残差维数由共同方程固定；直接装配，避免每次差分重新解释通用拼接规则。
        details = unsprung_contact_residual((end,forces,local_previous,contact_speeds,active.radii,rolling_flags,parameters),
            residual,dt,config.tire_contact_stiffness,config.tire_contact_damping,config.tire_shape,config.tire_curvature,
            config.slip_speed,math.hypot)
        unsprung_port_residual((torques,speeds,response,inertial_torques,brakes,*port_tuning),residual,port_settings,output_torque)
        return residual,(q,delta,normal,down,contact_speeds,rolling_torque,details,parameters,speeds,output_torque,
                         active,local_previous,coefficients,scale,kinematics,gyro,suspension_velocity)

    config_rear = replace(config,lateral_stiffness=config.rear_lateral_stiffness)
    def finish(values,details,iteration,momentum_error,force_error,port_error):
        end,forces,torques = values[:16],values[16:24].reshape(4,2),values[24:]
        q,delta,normal,down,surface,rolling_torque,contact,parameters,speeds,drive,active,previous,coefficients,scale,kinematics,gyro,suspension_velocity = details
        wheels,contact_energy,material_heat,road_heat,tangent_numeric = [],0.,0.,0.,0.
        for i,result in enumerate(contact):
            _target,elastic,rate,patch,patch_kappa,patch_alpha,mode = result
            energy,material,dissipation,numeric = energy_terms(tuple(forces[i]),tuple(previous[i]),elastic,rate,patch,
                                                             dt,config.tire_contact_stiffness,config.tire_contact_damping)
            vx = surface[i,0]+active.radii[i]*end[12+i]
            wheels.append(WheelStep(end[12+i],speeds[3+i],vx,surface[i,1],np.dot(end[3:6],hardware.axes[i]),
                -surface[i,0]/max(abs(vx),config.slip_speed),math.atan2(surface[i,1],max(abs(vx),config.slip_speed)),
                *forces[i],torques[3+i],force_error,mode if normal.normal_force[i]>0. else "airborne",*elastic,
                patch_kappa,patch_alpha,energy,material,dissipation,numeric,*rate,
                rolling_torque=rolling_torque[i],rolling_dissipation=dt*rolling_torque[i]*end[12+i]))
            contact_energy += energy
            material_heat += material
            road_heat += dissipation
            tangent_numeric += numeric
        old_potential,_ = suspension_potential(q0,config)
        old_radial = .5*np.dot(rates,np.maximum(delta0,0.)**2)
        old_contact = .5*config.tire_contact_stiffness*np.sum(previous**2)
        potential_change = normal.suspension_potential-old_potential+normal.tire_potential-old_radial+contact_energy-old_contact
        elastic_numeric = np.dot(normal.spring_force,q-q0)-(normal.suspension_potential-old_potential)
        elastic_numeric += np.dot(coefficients.normal_force,delta-delta0)-(normal.tire_potential-old_radial)-normal.tire_damping
        kinetic_change = .5*((end-start)@hardware.base_mass@(end+start)
                            +np.dot(hardware.downstream_inertias,(down-old_down)*(down+old_down)))
        kinetic_change -= hardware.wheel_kinetic_correction(start,actual_wheels)
        end_wheels = hardware.mechanical.wheel_jacobians@end[:10]+bias
        kinetic_change += hardware.wheel_kinetic_correction(end,end_wheels)
        kinetic_numeric = .5*((end-start)@hardware.base_mass@(end-start)+np.dot(hardware.downstream_inertias,(down-old_down)**2))
        kinetic_numeric += hardware.wheel_kinetic_correction(end-start,end_wheels-actual_wheels)
        engine_work = dt*engine_torque*np.dot(hardware.engine,end)
        engine_heat = dt*engine_drag*np.dot(hardware.engine,end)**2
        port_heat = dt*torques*speeds
        rolling_heat = dt*np.dot(rolling_torque,end[12:])
        steering_work = -dt*np.sum(np.column_stack((forces,normal.normal_force))*active.steering_velocity)
        known_work,road_work = dt*np.dot(end,known),np.dot(normal.normal_force,road)
        known_work += dt*np.sum(bias*wheel_known)
        wheel_force = (forces[:,0,None]*active.longitudinal[:,:3]+forces[:,1,None]*active.lateral[:,:3]
                       +normal.normal_force[:,None]*active.normal[:,:3]
                       -normal.suspension_force[:,None]*hardware.mechanical.guides+wheel_known)
        guide_impulse = hardware.mechanical.wheel_masses[:,None]*(end_wheels-actual_wheels)-dt*wheel_force
        guide_work = float(np.sum(guide_impulse*bias))
        gyro_work = float(np.dot(end[3:6],gyro))
        # 本构读取真实末构型；原生仍冻结本步力方向。两种几何的功差是数值积分项，不是材料耗散。
        suspension_geometry_work = np.dot(normal.spring_force,q-q0-dt*end[6:10])
        suspension_geometry_work += dt*np.dot(normal.suspension_force-normal.spring_force,suspension_velocity-end[6:10])
        material_loss = material_heat+normal.suspension_damping+normal.tire_damping
        contact_numeric = tangent_numeric+elastic_numeric
        balance = kinetic_change+kinetic_numeric+potential_change+material_loss+contact_numeric+road_heat
        balance += engine_heat+sum(port_heat)+rolling_heat-engine_work-known_work-steering_work-road_work-guide_work-gyro_work-suspension_geometry_work
        return UnsprungJointStep(end,q,delta,normal,tuple(wheels),forces,torques,down,rolling_torque,parameters,float(drive),
            float(kinetic_change),float(kinetic_numeric),float(potential_change),float(material_loss),float(contact_numeric),
            float(road_heat),port_heat,float(rolling_heat),float(engine_work),float(engine_heat),float(known_work),
            float(steering_work),float(road_work),float(balance),momentum_error,force_error,port_error,iteration+1,
            kinematics,coefficients.normal_force.copy(),scale,guide_work,gyro_work,float(suspension_geometry_work),suspension_velocity.copy())

    return evaluate,finish,state_scale,row_scale
