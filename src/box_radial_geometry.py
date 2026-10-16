"""轮胎完全处于Box一个轴向区间内时，按支持函数证明剖面的真实有符号距离。"""

import struct
from functools import lru_cache

import numpy as np
from wheel_contact_kernels import (
    box_cone_refine,
    box_cone_samples,
    box_edge_frames,
    box_edge_proof,
    box_face_candidates,
)

from unsprung_dynamics import small_norm
from wheel_envelope import cylinder_support


def wheel_support(normal,axis,config):
    return np.asarray(cylinder_support(tuple(-normal),tuple(axis),config.wheel_radius,
        config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height))


@lru_cache(maxsize=512,typed=True)
def _axis_curvature(dtype,bits,wheel_radius,half_width,shoulder,crown,parameter_bits,free):
    """原类型/原顺序的曲率界限；参数字节另区分正负零，typed区分标量强弱类型。"""
    axis = np.frombuffer(bits,dtype=np.dtype(dtype))
    fixed = [i for i in range(3) if i!=free]
    rho = small_norm(axis[fixed])
    if rho>=1.:
        return None
    q = np.sqrt(1-rho*rho)
    radius = wheel_radius-shoulder
    width = half_width-shoulder
    coefficient = width*width/(4*crown)
    first = radius*rho/q+coefficient*(2*rho/q+rho**3/q**3)
    second = radius/q**3+coefficient*(2+rho*rho)/q**5
    if rho>2*crown/np.sqrt(width*width+4*crown*crown):
        first = max(first,width+radius*rho/q)
    first_theta,second_theta = first*rho,second*rho*rho+first*rho
    lower_support = (radius-crown)*q+shoulder
    return first_theta,second_theta,lower_support


def _edge_proof(deltas,first_theta):
    """仅批量原标量公式；低精度曲率平方仍按原NumPy类型计算。"""
    if isinstance(first_theta,np.float64):
        bounds=np.empty((4,3))
        box_edge_proof((deltas,),(bounds,),first_theta)
        return bounds
    bounds=[]
    for delta in deltas:
        length=small_norm(delta)
        critical=np.sqrt(max(length*length-first_theta*first_theta,0.))
        minimum_dot=-small_norm(np.minimum(delta,0.)) if min(delta)<0. else min(delta)
        maximum_dot=small_norm(np.maximum(delta,0.)) if max(delta)>0. else max(delta)
        bounds.append((critical,minimum_dot,maximum_dot))
    return np.asarray(bounds)


def box_section(center,axis,half,config):
    """返回有全局距离证明的见证点；未能证明的构型仍交给一般凸体算法。"""
    half = np.asarray(half)
    if config.wheel_crown_height==0.:
        return None
    axis = axis/small_norm(axis)
    center_native,axis_native = np.asarray(center,dtype=float),np.asarray(axis,dtype=float)
    parameters = config.wheel_radius,config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height,np.pi/2
    tolerance = 128*np.finfo(float).eps*max(1.,small_norm(center),max(half))
    axis_normals,axis_wheels = np.empty((6,3)),np.empty((6,3))
    half_native = np.asarray(half,dtype=float)
    face_distances,face_roads,face_eligible = np.empty(6),np.empty((6,3)),np.empty(6)
    box_face_candidates((center_native,axis_native,half_native),
                        (axis_normals,axis_wheels,face_distances,face_roads,face_eligible),
                        *parameters[:4],tolerance)
    for free in range(3):
        positive,negative = axis_wheels[2*free],axis_wheels[2*free+1]
        clearance = min(half[free]-positive[free],negative[free]+half[free])
        if clearance<=0.:
            continue
        fixed = [i for i in range(3) if i!=free]
        curvature = _axis_curvature(axis.dtype.str,axis.tobytes(),*parameters[:4],struct.pack('=4d',*parameters[:4]),free)
        if curvature is None:
            continue
        first_theta,second_theta,lower_support = curvature
        candidates,bounds = [],[]

        for index in fixed:
            for side in range(2):
                row = 2*index+side
                normal,wheel = axis_normals[row],axis_wheels[row]
                distance,road = float(face_distances[row]),face_roads[row]
                if face_eligible[row]:
                    candidates.append((distance,normal,wheel,road,(tuple(normal),float(half[index]))))

        bases,edges,deltas = np.empty((8,3)),np.empty((4,3)),np.empty((4,2))
        box_edge_frames((center_native,half_native),(bases,edges,deltas),free)
        edge_bounds = _edge_proof(deltas,first_theta)
        for row in range(4):
            basis,edge = bases[2*row:2*row+2],edges[row]

            normals,wheels,values = np.empty((3,3)),np.empty((3,3)),np.empty((3,2))
            inputs,outputs = (center_native,axis_native,basis,edge),(normals,wheels,values)
            box_cone_samples(inputs,outputs,*parameters,np.cos,np.sin)
            upper = max(float(values[0,0]),float(values[1,0]))
            critical,minimum_dot,maximum_dot = edge_bounds[row]
            if critical>second_theta and minimum_dot>-critical:
                # 所有驻点均为严格极大值，因此这一法线锥最多只有一个内部极大值。
                if values[0,1]>0. and values[1,1]<0.:
                    box_cone_refine(inputs,outputs,*parameters,np.cos,np.sin)
                    normal,wheel,distance = normals[2],wheels[2],float(values[2,0])
                    upper = max(upper,distance)
                    road = edge.copy();road[free]=wheel[free]
                    if (abs(road[free])<=half[free]+tolerance
                            and small_norm(wheel-road-distance*normal)<=tolerance):
                        candidates.append((distance,normal,wheel,road,None))
            elif not (critical>second_theta and maximum_dot<critical):
                # 未能证明驻点类型时，保留整个法线锥的上界，不把一次局部根当全局距离。
                upper = maximum_dot-lower_support
            bounds.append(upper)
        if candidates:
            best = max(candidates,key=lambda item:item[0])
            distance = best[0]
            if distance>=0.:
                return best
            if -distance<clearance and max(bounds)<=distance+tolerance:
                return best
    return None
