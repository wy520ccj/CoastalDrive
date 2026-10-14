"""簧下/径向/切向接触与有限传动的共同末状态；构型由外层真实几何刷新。"""

import math
from dataclasses import dataclass, replace

import numpy as np

from differential import torque_bias_capacities
from tire_compliance import contact_force, energy_terms
from tire_properties import tire_grip, tire_stiffness
from unsprung_contact import normal_material, suspension_potential
from wheel_dynamics import WheelStep


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


def solve_unsprung_joint(hardware, contacts, velocity, downstream_omega, compression, tire_deflection,
                         deformations, initial_force, known_force, road_delta, radial_rates, radial_damping,
                         friction, rolling_coefficients, engine_torque, engine_drag, clutch_capacity,
                         brake_capacities, ratio, synchronizing, dt, config, *, wheel_initial_velocity=None,
                         finite_contact=None):
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
    response = np.diag(ports@np.linalg.solve(inertia,ports.T))
    rolling = np.maximum(np.abs(gx@start+contacts.radii*start[12:]),np.abs(contacts.radii*start[12:]))>=config.static_contact_speed
    state_scale = np.r_[np.ones(10),np.full(6,100.),np.full(8,1000.),np.full(10,100.)]
    row_scale = np.r_[np.maximum(np.diag(inertia)*state_scale[:16],1.),np.full(8,1000.),np.full(10,100.)]

    def evaluate(values):
        end,forces,torques = values[:16],values[16:24].reshape(4,2),values[24:]
        kinematics = finite_contact.evaluate(end) if finite_contact is not None else None
        active = contacts if kinematics is None else kinematics.contacts
        gx,gy,gn = active.longitudinal,active.lateral,active.normal
        local_previous = previous if kinematics is None else kinematics.deformation
        local_mu = mu if kinematics is None else kinematics.friction
        local_rolling = rolling_c if kinematics is None else kinematics.rolling
        scale = np.ones(4) if kinematics is None else kinematics.scale
        eligible = np.ones(4) if kinematics is None else np.array([hit is not None for hit in kinematics.geometry.hits])
        q = q0+dt*end[6:10]
        delta = (delta0+road-dt*(gn@end+active.steering_velocity[:,2]) if kinematics is None
                 else kinematics.geometry.deflection)
        coefficients = normal_material(q,end[6:10],delta,delta0,dt,config,rates*eligible,radial_c*eligible)
        normal = coefficients if kinematics is None else replace(coefficients,normal_force=coefficients.normal_force*scale)
        down = hardware.downstream@end
        loss = torques[2]
        output_torque = ratio*(torques[1]-loss)
        inertial_torques = hardware.downstream_inertias*(down-old_down)/dt
        axle = (config.front_drive_share*output_torque-config.final_drive*(
                    config.front_drive_share*inertial_torques[0]+inertial_torques[1]),
                (1-config.front_drive_share)*output_torque-config.final_drive*(
                    (1-config.front_drive_share)*inertial_torques[0]+inertial_torques[2]))
        limits = np.r_[torque_bias_capacities(config.differential_capacity[:2],config.axle_torque_bias_ratios,axle),
                       config.differential_capacity[2]]
        speeds = ports@end
        contact_speeds = np.column_stack((gx@end,gy@end,gn@end))+active.steering_velocity
        rolling_torque = local_rolling*normal.normal_force*active.radii**2*end[12:] / np.maximum(
            np.abs(active.radii*end[12:]),config.rolling_transition_speed)
        reaction = known+engine_torque*hardware.engine-engine_drag*np.dot(hardware.engine,end)*hardware.engine
        reaction = reaction-gs.T@normal.suspension_force+gn.T@normal.normal_force+gx.T@forces[:,0]+gy.T@forces[:,1]-ports.T@torques
        reaction[12:] -= rolling_torque
        rotor_bias = np.zeros(16)
        rotor_bias[3:6] = np.cross(end[3:6],hardware.spin(end,config))
        momentum_error = inertia@end-momentum-dt*(reaction-rotor_bias)
        force_errors,details,parameters = [],[],[]
        for i in range(4):
            car = config if i<2 else config_rear
            load = float(normal.normal_force[i])
            grip = tire_grip(load,local_mu[i],car)
            cx,cy = tire_stiffness(load,car)
            vx = contact_speeds[i,0]+active.radii[i]*end[12+i]
            result = contact_force(tuple(forces[i]),tuple(local_previous[i]),tuple(-contact_speeds[i,:2]),
                max(abs(vx),config.slip_speed),bool(rolling[i]),grip,cx,cy,dt,
                config.tire_contact_stiffness,config.tire_contact_damping,config.tire_shape,config.tire_curvature)
            force_errors.extend(forces[i]-result[0])
            details.append(result)
            parameters.append((grip,cx,cy))
        error_c = torques[0]-np.clip(torques[0]+speeds[0]/(dt*response[0]),-clutch_capacity,clutch_capacity)
        if ratio and not synchronizing:
            error_g = speeds[1]/(dt*response[1])
            slope = 1-config.drivetrain_efficiency if torques[1]*speeds[2]>=0. else 1-1/config.drivetrain_efficiency
            error_l = loss-slope*torques[1]
        elif ratio:
            capacity = config.synchronizer_capacity
            error_g = torques[1]-np.clip(torques[1]+speeds[1]/(dt*response[1]),-capacity,capacity)
            error_l = loss
        else:
            error_g,error_l = torques[1],loss
        brake_error = torques[3:7]-np.clip(torques[3:7]+speeds[3:7]/(dt*response[3:7]),-brakes,brakes)
        differential_error = torques[7:]-np.clip(np.asarray(config.differential_damping)*speeds[7:],-limits,limits)
        port_errors = np.r_[error_c,error_g,error_l,brake_error,differential_error]
        residual = np.r_[momentum_error,force_errors,port_errors]
        return residual,(q,delta,normal,down,contact_speeds,rolling_torque,details,np.asarray(parameters),speeds,output_torque,
                         active,local_previous,coefficients,scale,kinematics)

    config_rear = replace(config,lateral_stiffness=config.rear_lateral_stiffness)
    values = np.r_[start,np.asarray(initial_force).ravel(),np.zeros(10)]
    for iteration in range(30):
        residual,details = evaluate(values)
        momentum_error = float(np.max(np.abs(residual[:16])))
        force_error = float(np.max(np.abs(residual[16:24])))
        port_error = float(np.max(np.abs(residual[24:])))
        if momentum_error<1e-9 and force_error<1e-5 and port_error<1e-9:
            break
        columns = []
        for i,scale in enumerate(state_scale):
            plus,minus = values.copy(),values.copy()
            epsilon = 1e-5*scale
            plus[i] += epsilon
            minus[i] -= epsilon
            columns.append((evaluate(plus)[0]-evaluate(minus)[0])/(2*epsilon)*scale/row_scale)
        jacobian = np.column_stack(columns)
        delta = np.linalg.solve(jacobian,residual/row_scale)*state_scale
        before = np.linalg.norm(residual/row_scale)
        for attempt in range(12):
            candidate = values-2.**-attempt*delta
            if np.linalg.norm(evaluate(candidate)[0]/row_scale)<before:
                values = candidate
                break
        else:
            raise ArithmeticError(f"簧下/轮胎/传动共同线搜索不下降：{momentum_error:g}Ns，{force_error:g}N，{port_error:g}Nm")
    else:
        raise ArithmeticError(f"簧下/轮胎/传动共同求解超过30轮：{momentum_error:g}Ns，{force_error:g}N，{port_error:g}Nm")
    end,forces,torques = values[:16],values[16:24].reshape(4,2),values[24:]
    q,delta,normal,down,surface,rolling_torque,contact,parameters,speeds,drive,active,previous,coefficients,scale,kinematics = details
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
    kinetic_numeric = .5*((end-start)@hardware.base_mass@(end-start)+np.dot(hardware.downstream_inertias,(down-old_down)**2))
    kinetic_numeric += hardware.wheel_kinetic_correction(end-start,hardware.mechanical.wheel_jacobians@end[:10]-actual_wheels)
    engine_work = dt*engine_torque*np.dot(hardware.engine,end)
    engine_heat = dt*engine_drag*np.dot(hardware.engine,end)**2
    port_heat = dt*torques*speeds
    rolling_heat = dt*np.dot(rolling_torque,end[12:])
    steering_work = -dt*np.sum(np.column_stack((forces,normal.normal_force))*active.steering_velocity)
    known_work,road_work = dt*np.dot(end,known),np.dot(normal.normal_force,road)
    material_loss = material_heat+normal.suspension_damping+normal.tire_damping
    contact_numeric = tangent_numeric+elastic_numeric
    balance = kinetic_change+kinetic_numeric+potential_change+material_loss+contact_numeric+road_heat
    balance += engine_heat+sum(port_heat)+rolling_heat-engine_work-known_work-steering_work-road_work
    return UnsprungJointStep(end,q,delta,normal,tuple(wheels),forces,torques,down,rolling_torque,parameters,float(drive),
        float(kinetic_change),float(kinetic_numeric),float(potential_change),float(material_loss),float(contact_numeric),
        float(road_heat),port_heat,float(rolling_heat),float(engine_work),float(engine_heat),float(known_work),
        float(steering_work),float(road_work),float(balance),momentum_error,force_error,port_error,iteration+1,
        kinematics,coefficients.normal_force.copy(),scale)
