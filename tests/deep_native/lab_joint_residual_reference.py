"""LAB-PERF-08 基线dff1955的正式材料和端口残差，仅用于逐位对照。"""

import numpy as np

from differential import torque_bias_capacities
from tire_compliance import contact_force


def contact_reference(inputs, residual, dt, stiffness, damping, shape, curvature, slip_speed):
    end,forces,previous,speeds,radii,rolling,parameters = inputs
    details = []
    for i in range(4):
        grip,cx,cy = parameters[i]
        vx = speeds[i,0]+radii[i]*end[12+i]
        result = contact_force(tuple(forces[i]),tuple(previous[i]),tuple(-speeds[i,:2]),
            max(abs(vx),slip_speed),bool(rolling[i]),grip,cx,cy,dt,stiffness,damping,shape,curvature)
        residual[16+2*i:18+2*i] = forces[i]-result[0]
        details.append(result)
    return details


def port_reference(inputs, residual, settings, drive):
    torques,speeds,response,inertial_torques,brakes,maximum,biases,damping = inputs
    dt,ratio,synchronizing,share,final_drive,efficiency,clutch_capacity,synchronizer_capacity = settings
    loss = torques[2]
    axle = (share*drive-final_drive*(share*inertial_torques[0]+inertial_torques[1]),
            (1-share)*drive-final_drive*((1-share)*inertial_torques[0]+inertial_torques[2]))
    limits = np.empty(3)
    limits[:2] = torque_bias_capacities(maximum[:2],biases,axle)
    limits[2] = maximum[2]
    error_c = torques[0]-np.clip(torques[0]+speeds[0]/(dt*response[0]),-clutch_capacity,clutch_capacity)
    if ratio and not synchronizing:
        error_g = speeds[1]/(dt*response[1])
        slope = 1-efficiency if torques[1]*speeds[2]>=0. else 1-1/efficiency
        error_l = loss-slope*torques[1]
    elif ratio:
        error_g = torques[1]-np.clip(torques[1]+speeds[1]/(dt*response[1]),-synchronizer_capacity,synchronizer_capacity)
        error_l = loss
    else:
        error_g,error_l = torques[1],loss
    brake_error = torques[3:7]-np.clip(torques[3:7]+speeds[3:7]/(dt*response[3:7]),-brakes,brakes)
    differential_error = torques[7:]-np.clip(damping*speeds[7:],-limits,limits)
    residual[24:27] = error_c,error_g,error_l
    residual[27:31] = brake_error
    residual[31:] = differential_error
