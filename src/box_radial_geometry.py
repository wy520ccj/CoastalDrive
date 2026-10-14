"""轮胎完全处于Box一个轴向区间内时，按支持函数证明剖面的真实有符号距离。"""

from itertools import product

import numpy as np

from wheel_envelope import cylinder_support


def wheel_support(normal,axis,config):
    return np.asarray(cylinder_support(tuple(-normal),tuple(axis),config.wheel_radius,
        config.wheel_width/2,config.wheel_shoulder_radius,config.wheel_crown_height))


def box_section(center,axis,half,config):
    """返回有全局距离证明的见证点；未能证明的构型仍交给一般凸体算法。"""
    half = np.asarray(half)
    if config.wheel_crown_height==0.:
        return None
    axis = axis/np.linalg.norm(axis)
    tolerance = 128*np.finfo(float).eps*max(1.,np.linalg.norm(center),max(half))
    for free in range(3):
        positive = center+wheel_support(-np.eye(3)[free],axis,config)
        negative = center+wheel_support(np.eye(3)[free],axis,config)
        clearance = min(half[free]-positive[free],negative[free]+half[free])
        if clearance<=0.:
            continue
        fixed = [i for i in range(3) if i!=free]
        rho = np.linalg.norm(axis[fixed])
        if rho>=1.:
            continue
        q = np.sqrt(1-rho*rho)
        radius = config.wheel_radius-config.wheel_shoulder_radius
        crown = config.wheel_crown_height
        width = config.wheel_width/2-config.wheel_shoulder_radius
        coefficient = width*width/(4*crown)
        first = radius*rho/q+coefficient*(2*rho/q+rho**3/q**3)
        second = radius/q**3+coefficient*(2+rho*rho)/q**5
        if rho>2*crown/np.sqrt(width*width+4*crown*crown):
            first = max(first,width+radius*rho/q)
        first_theta,second_theta = first*rho,second*rho*rho+first*rho
        lower_support = (radius-crown)*q+config.wheel_shoulder_radius
        candidates,bounds = [],[]

        for index in fixed:
            for sign in (-1.,1.):
                normal = sign*np.eye(3)[index]
                wheel = center+wheel_support(normal,axis,config)
                distance = float(np.dot(normal,wheel)-half[index])
                road = wheel-distance*normal
                if all(abs(road[j])<=half[j]+tolerance for j in range(3) if j!=index):
                    candidates.append((distance,normal,wheel,road,(tuple(normal),float(half[index]))))

        for signs in product((-1.,1.),repeat=2):
            basis = np.eye(3)[fixed]*np.asarray(signs)[:,None]
            edge = np.zeros(3);edge[fixed]=np.asarray(signs)*half[fixed]
            delta = (center[fixed]-edge[fixed])*signs
            length = np.linalg.norm(delta)

            def evaluate(angle,basis=basis,edge=edge):
                normal = np.cos(angle)*basis[0]+np.sin(angle)*basis[1]
                tangent = -np.sin(angle)*basis[0]+np.cos(angle)*basis[1]
                wheel = center+wheel_support(normal,axis,config)
                return normal,wheel,float(np.dot(normal,wheel-edge)),float(np.dot(tangent,wheel-edge))

            left,right = evaluate(0.),evaluate(np.pi/2)
            upper = max(left[2],right[2])
            critical = np.sqrt(max(length*length-first_theta*first_theta,0.))
            minimum_dot = -np.linalg.norm(np.minimum(delta,0.)) if min(delta)<0. else min(delta)
            maximum_dot = np.linalg.norm(np.maximum(delta,0.)) if max(delta)>0. else max(delta)
            if critical>second_theta and minimum_dot>-critical:
                # 所有驻点均为严格极大值，因此这一法线锥最多只有一个内部极大值。
                if left[3]>0. and right[3]<0.:
                    lo,hi = 0.,np.pi/2
                    for _ in range(52):
                        middle = (lo+hi)/2
                        if evaluate(middle)[3]>0.:lo=middle
                        else:hi=middle
                    normal,wheel,distance,_slope = evaluate((lo+hi)/2)
                    upper = max(upper,distance)
                    road = edge.copy();road[free]=wheel[free]
                    if (abs(road[free])<=half[free]+tolerance
                            and np.linalg.norm(wheel-road-distance*normal)<=tolerance):
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
