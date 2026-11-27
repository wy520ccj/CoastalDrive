"""簧下/径向/切向接触与有限传动的共同末状态；构型由外层真实几何刷新。"""

import math
from dataclasses import dataclass, replace

import numpy as np
from mechanical_kernels import (
    unsprung_fixed_evaluate,
    unsprung_fixed_prepare,
    unsprung_jacobian_tail,
)

from tire_compliance import energy_terms
from tire_properties import tire_camber_stiffness, tire_grip, tire_stiffness
from unsprung_contact import normal_material, suspension_potential
from wheel_dynamics import WheelStep


@dataclass
class JointJacobianHint:
    """一个子步的只读输入种子和独立输出；只给数值方向，不代表物理状态。"""
    previous: np.ndarray | None = None
    current: np.ndarray | None = None


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


def solve_unsprung_joint(hardware, contacts, velocity, downstream_omega, compression, tire_deflection,
                         deformations, initial_force, known_force, road_delta, radial_rates, radial_damping,
                         friction, rolling_coefficients, engine_torque, engine_drag, clutch_capacity,
                         brake_capacities, ratio, synchronizing, dt, config, *, wheel_initial_velocity=None,
                         finite_contact=None, wheel_velocity_bias=None, wheel_known_force=None,
                         native_body_gyro=False, body_external_torque=None,finite_motion=None,jacobian_updates=True,
                         jacobian_hint=None, inclination_rad=(0.,) * 4):
    """同时解十六速度、八接触力和十有限端口，不在结束后修补轮速/轮荷。

    本函数保持当前构型的质量/力端口，有限姿态与真实世界接点须由外层联立。
    known_force含外层已知广义力，惯性偏置应在外层按同一构型处理。
    原生轮心速度若带有限导向误差，显式传入并保留其动量/动能，而不是先强设到导向速度。
    """
    start = np.asarray(velocity,dtype=float)
    old_down = np.asarray(downstream_omega,dtype=float)
    q0,delta0,previous = (np.asarray(item,dtype=float) for item in (compression,tire_deflection,deformations))
    known,road,rates,radial_c,mu,rolling_c,brakes = (np.asarray(item,dtype=float) for item in
        (known_force,road_delta,radial_rates,radial_damping,friction,rolling_coefficients,brake_capacities))
    if finite_contact is not None and np.any(road!=0.):
        raise ValueError("有限真实静态接触不接受额外道路位移输入")
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
    external_torque = np.zeros(3) if body_external_torque is None else np.asarray(body_external_torque,dtype=float)
    response = np.diag(ports@np.linalg.solve(inertia,ports.T))
    wheel_speed = contacts.radii*start[12:]
    initial_vx = contacts.longitudinal@start+wheel_speed
    rolling = np.maximum(np.abs(initial_vx),np.abs(wheel_speed))>=config.static_contact_speed
    rolling_flags = rolling.astype(float)
    port_settings = (dt,ratio,synchronizing,config.front_drive_share,config.final_drive,
                     config.drivetrain_efficiency,clutch_capacity,config.synchronizer_capacity)
    port_tuning = tuple(np.asarray(values,dtype=float) for values in
                        (config.differential_capacity,config.axle_torque_bias_ratios,config.differential_damping))
    state_scale = np.r_[np.ones(10),np.full(6,100.),np.full(8,1000.),np.full(10,100.)]
    row_scale = np.r_[np.maximum(np.diag(inertia)*state_scale[:16],1.),np.full(8,1000.),np.full(10,100.)]

    mechanical = hardware.mechanical
    fixed = unsprung_fixed_prepare(
        (inertia,momentum,known,ports,response,hardware.engine,hardware.downstream,hardware.downstream_inertias,
         hardware.downstream_axes,old_down,hardware.engine_axis,hardware.shaft_axis,hardware.axes,mechanical.wheel_arms,
         mechanical.guides,wheel_known,mechanical.world_inertia,external_torque,start[3:6],brakes,*port_tuning,rolling_flags),
        port_settings,(engine_torque,engine_drag,config.engine_inertia,config.input_shaft_inertia,config.wheel_inertia,
                       config.rolling_transition_speed,config.slip_speed,config.tire_contact_stiffness,
                       config.tire_contact_damping,config.tire_shape,config.tire_curvature),native_body_gyro)
    config_rear = replace(config,lateral_stiffness=config.rear_lateral_stiffness,camber_stiffness=config.rear_camber_stiffness)
    zero_camber = np.zeros(4)
    camber_factors = zero_camber
    if any(inclination_rad) and (config.camber_stiffness or config.rear_camber_stiffness):
        initial_vx = initial_vx+contacts.steering_velocity[:,0]
        if contacts.guide_velocity is not None:
            initial_vx = initial_vx+contacts.guide_velocity[:,0]
        camber_factors = np.array([math.sin(gamma)*min(1.,abs(vx)/config.slip_speed) if rolls else 0.
                                   for gamma,vx,rolls in zip(inclination_rad,initial_vx,rolling)])
    configuration_key,configuration_data = None,None
    configuration_base_key,configuration_base_data = None,None
    geometry_columns = 10 if finite_contact is not None else 16

    def configuration(end):
        nonlocal configuration_key,configuration_data
        # 有限接触/行程只依赖车身和轮心十速度；旧冻结法向端口仍可含自旋，须用全部速度。
        key = end[:geometry_columns].tobytes()
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
        offsets = np.empty(4) if camber_factors is not zero_camber else zero_camber
        for i in range(4):
            car = config if i<2 else config_rear
            load = float(normal.normal_force[i])
            grip = tire_grip(load,local_mu[i],car)
            cx,cy = tire_stiffness(load,car)
            parameters.append((grip,cx,cy))
            if offsets is not zero_camber:
                offsets[i] = tire_camber_stiffness(load,car)*camber_factors[i] if camber_factors[i] != 0. else 0.
        configuration_key = key
        native = (active.longitudinal,active.lateral,gn,active.radii,active.steering_velocity,guide,
                  local_previous,local_rolling,normal.suspension_force,normal.normal_force,np.asarray(parameters),offsets)
        configuration_data = native,(kinematics,active,scale,q,suspension_velocity,delta,coefficients,normal)
        return configuration_data

    def evaluate(values):
        native,_details = configuration(values[:16])
        residual = np.empty(34)
        unsprung_fixed_evaluate(fixed,native,values,residual)
        return residual

    values = np.r_[start,np.asarray(initial_force).ravel(),np.zeros(10)]
    # 只更新数值Jacobian，原完整残差/精确端口行和收敛门槛不变。
    jacobian = None
    if jacobian_hint is not None:
        jacobian_hint.current = None
        if jacobian_updates and jacobian_hint.previous is not None:
            # 种子以未缩放物理坐标保存；这里换成当前质量/状态的缩放坐标。
            jacobian = jacobian_hint.previous*state_scale[None,:]/row_scale[:,None]
    for iteration in range(30):
        residual = evaluate(values)
        momentum_error = float(np.max(np.abs(residual[:16])))
        force_error = float(np.max(np.abs(residual[16:24])))
        port_error = float(np.max(np.abs(residual[24:])))
        # 达到原门槛后，只接受进一步下降且仍合格的一次校正。
        polishing = momentum_error<1e-9 and force_error<1e-5 and port_error<1e-9
        if polishing and (not jacobian_updates or jacobian is None):
            break
        # 一轮差分中会反复回到已算基点；只固定该点的完整字节项，不缓存新构型或跨子步复用。
        configuration_base_key = values[:geometry_columns].tobytes()
        configuration_base_data = configuration_data
        fresh_jacobian = jacobian is None
        if fresh_jacobian:
            jacobian = np.empty((34,34))
            unsprung_jacobian_tail(fixed,configuration_base_data[0],values,residual,state_scale,row_scale,
                                  jacobian,geometry_columns,jacobian_updates)
            for i in range(geometry_columns):
                scale = state_scale[i]
                plus = values.copy()
                epsilon = 1e-5*scale
                plus[i] += epsilon
                if jacobian_updates:
                    jacobian[:,i] = (evaluate(plus)-residual)/epsilon*scale/row_scale
                else:
                    minus = values.copy()
                    minus[i] -= epsilon
                    jacobian[:,i] = (evaluate(plus)-evaluate(minus))/(2*epsilon)*scale/row_scale
        # 轮速差分0.001rad/s可能跨过小制动容量的两个边界，给出不属于当前分支的割线。
        # 固定容量端口使用精确分段导数；仍解原来的全部残差，不裁剪/覆写末状态。
        fixed_ports = [(0, clutch_capacity), *((i+3, capacity) for i, capacity in enumerate(brakes))]
        if ratio and synchronizing:
            fixed_ports.append((1, config.synchronizer_capacity))
        speeds = ports@values[:16]
        for index, capacity in fixed_ports:
            speed_row, torque_derivative = dry_port_derivative(ports[index], values[24+index],
                speeds[index], capacity, dt*response[index])
            derivative = np.r_[speed_row, np.zeros(18)]
            derivative[24+index] = torque_derivative
            jacobian[24+index] = derivative*state_scale/row_scale[24+index]
        try:
            delta = np.linalg.solve(jacobian,residual/row_scale)*state_scale
        except np.linalg.LinAlgError:
            if polishing:
                break
            if fresh_jacobian:
                raise
            jacobian = None
            continue
        before = np.linalg.norm(residual/row_scale)
        max_attempts = 12 if jacobian_updates else 20
        for attempt in range(max_attempts):
            candidate = values-2.**-attempt*delta
            candidate_residual = evaluate(candidate)
            after = np.linalg.norm(candidate_residual/row_scale)
            if after<before:
                if polishing:
                    candidate_errors = (float(np.max(np.abs(candidate_residual[:16]))),
                        float(np.max(np.abs(candidate_residual[16:24]))),float(np.max(np.abs(candidate_residual[24:]))))
                    if not (candidate_errors[0]<1e-9 and candidate_errors[1]<1e-5 and candidate_errors[2]<1e-9):
                        continue
                    values = candidate
                    momentum_error,force_error,port_error = candidate_errors
                    break
                if jacobian_updates and not attempt and after<.5*before:
                    displacement = (candidate-values)/state_scale
                    squared = np.dot(displacement,displacement)
                    if squared>0.:
                        # 在原状态/残差缩放坐标中满足Broyden割线条件。
                        difference = (candidate_residual-residual)/row_scale
                        jacobian = jacobian+np.outer(difference-jacobian@displacement,displacement)/squared
                    else:
                        jacobian = None
                else:
                    jacobian = None
                values = candidate
                break
        else:
            if polishing:
                break
            if not fresh_jacobian:
                jacobian = None
                continue
            if jacobian_updates:
                jacobian_updates = False
                jacobian = None
                continue
            raise ArithmeticError(f"簧下/轮胎/传动共同线搜索不下降：{momentum_error:g}Ns，{force_error:g}N，{port_error:g}Nm")
        if polishing:
            break
    else:
        raise ArithmeticError(f"簧下/轮胎/传动共同求解超过30轮：{momentum_error:g}Ns，{force_error:g}N，{port_error:g}Nm")
    if jacobian_updates and jacobian_hint is not None and jacobian is not None:
        jacobian_hint.current = jacobian*row_scale[:,None]/state_scale[None,:]
        jacobian_hint.current.flags.writeable = False
    end,forces,torques = values[:16],values[16:24].reshape(4,2),values[24:]
    native,geometry = configuration(end)
    kinematics,active,scale,q,suspension_velocity,delta,coefficients,normal = geometry
    down,surface,rolling_torque,contact,speeds,gyro = unsprung_fixed_evaluate(fixed,native,values,np.empty(34),True)
    down,surface,rolling_torque,speeds,gyro = map(np.asarray,(down,surface,rolling_torque,speeds,gyro))
    previous,parameters = native[6],native[10]
    drive = ratio*(torques[1]-torques[2])
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


def unsprung_energy_ledger(steps) -> dict[str, float]:
    """累计同一簧下序列的储能、耗散、输入功、离散项及闭合残差，单位J。"""
    steps = tuple(steps)
    return {
        "kinetic_change": math.fsum(s.kinetic_change for s in steps),
        "potential_change": math.fsum(s.potential_change for s in steps),
        "physical_dissipation": math.fsum(
            s.material_loss+s.road_loss+s.rolling_heat+s.engine_heat+sum(s.port_heat) for s in steps),
        "external_work": math.fsum(s.engine_work+s.known_work+s.steering_work+s.road_work for s in steps),
        "numerical_terms": math.fsum(s.kinetic_numerical_loss+s.contact_numerical_loss
                                      +s.guide_work+s.body_gyro_work+s.suspension_geometry_work for s in steps),
        # 导向、陀螺及构型功在闭合式中作为输入功扣除。
        "numerical_balance": math.fsum(s.kinetic_numerical_loss+s.contact_numerical_loss
                                        -s.guide_work-s.body_gyro_work-s.suspension_geometry_work for s in steps),
        "cumulative_energy_error": math.fsum(s.energy_error for s in steps),
    }
