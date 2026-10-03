"""传动预研：有限离合、双向齿轮损失、单轮干式制动的共同活动集。"""

import hashlib
import json
import math
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("drive-brake-active-initial")
proof_path = Path(__file__).with_name("drive-port-active-probe.py")
proof = runpy.run_path(str(proof_path))
dot, limits, hashes = (proof[name] for name in ("dot", "limits", "source_hashes"))
EPS = 1e-11


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def solve_three(rows, rhs):
    cofactors = cross(rows[1], rows[2]), cross(rows[2], rows[0]), cross(rows[0], rows[1])
    determinant = dot(rows[0], cofactors[0])
    return tuple(sum(cofactors[j][i]*rhs[j] for j in range(3))/determinant for i in range(3))


def active_three(free, response, h, clutch_capacity, brake_capacity, eta):
    """只解三个明确机械约束；标签边界可以重复，真实反力必须一致。"""
    candidates = []
    clutch_modes = ("locked", "positive-slip", "negative-slip") if clutch_capacity else ("positive-slip", "negative-slip")
    brake_modes = ("locked", "positive-slip", "negative-slip") if brake_capacity else ("positive-slip", "negative-slip")
    for cmode in clutch_modes:
        for gear_mode in ("positive-motion", "negative-motion", "static"):
            signs = (-1, 1) if gear_mode != "static" else (0,)
            for sign in signs:
                slope = (1-eta if ((gear_mode == "positive-motion") == (sign > 0)) else 1-1/eta)
                for bmode in brake_modes:
                    rows = (response[0] if cmode == "locked" else (1.,0.,0.),
                            response[1] if gear_mode == "static" else (-slope,1.,0.),
                            response[2] if bmode == "locked" else (0.,0.,1.))
                    rhs = (free[0]/h if cmode == "locked" else (clutch_capacity if cmode == "positive-slip" else -clutch_capacity),
                           free[1]/h if gear_mode == "static" else 0.,
                           free[2]/h if bmode == "locked" else (brake_capacity if bmode == "positive-slip" else -brake_capacity))
                    value = solve_three(rows, rhs)
                    clutch, loss, brake = value
                    if sign and clutch*sign < -EPS:
                        continue
                    low, high = limits(clutch, eta)
                    speeds = tuple(free[i]-h*dot(response[i],value) for i in range(3))
                    slip, speed, wheel_speed = speeds
                    if abs(clutch)>clutch_capacity+EPS or loss<low-EPS or loss>high+EPS or abs(brake)>brake_capacity+EPS:
                        continue
                    if cmode == "locked" and abs(slip)>EPS:
                        continue
                    if cmode == "positive-slip" and slip < -EPS or cmode == "negative-slip" and slip > EPS:
                        continue
                    if gear_mode == "static" and abs(speed)>EPS:
                        continue
                    if gear_mode == "positive-motion" and (speed < -EPS or abs(loss-high)>EPS):
                        continue
                    if gear_mode == "negative-motion" and (speed > EPS or abs(loss-low)>EPS):
                        continue
                    if bmode == "locked" and abs(wheel_speed)>EPS:
                        continue
                    if bmode == "positive-slip" and wheel_speed < -EPS or bmode == "negative-slip" and wheel_speed > EPS:
                        continue
                    candidates.append((value,speeds,(cmode,gear_mode,bmode),rows))
    if not candidates:
        raise ArithmeticError("传动/单轮制动的共同活动集无可行解")
    first = candidates[0]
    assert all(max(abs(c[0][i]-first[0][i]) for i in range(3)) < 1e-8 for c in candidates)
    return first, len(candidates)


def bisect(function, low, high):
    assert function(low)>=-EPS and function(high)<=EPS
    for _ in range(100):
        middle = (low+high)/2
        value = function(middle)
        if abs(value)<1e-13:
            return middle
        if value>0:
            low=middle
        else:
            high=middle
    return (low+high)/2


def nested_three(free,d,h,clutch_capacity,brake_capacity,eta):
    def brake(clutch,loss):
        demand=(free[2]/h-d[2][0]*clutch-d[2][1]*loss)/d[2][2]
        return max(-brake_capacity,min(brake_capacity,demand))
    def gear(clutch):
        low,high=limits(clutch,eta)
        def speed(loss):
            return free[1]-h*(d[1][0]*clutch+d[1][1]*loss+d[1][2]*brake(clutch,loss))
        if speed(low)<-EPS:
            loss=low
        elif speed(high)>EPS:
            loss=high
        else:
            loss=bisect(speed,low,high)
        used_brake=brake(clutch,loss)
        return free[0]-h*(d[0][0]*clutch+d[0][1]*loss+d[0][2]*used_brake),loss,used_brake
    if gear(-clutch_capacity)[0]<-EPS:
        clutch=-clutch_capacity
    elif gear(clutch_capacity)[0]>EPS:
        clutch=clutch_capacity
    else:
        clutch=bisect(lambda c:gear(c)[0],-clutch_capacity,clutch_capacity)
    result=gear(clutch)
    return clutch,result[1],result[2]


def model(h,ratio,wheel):
    principal,je,jw,drag=(1900.,510.,2200.),.2,1.15,.6
    angle=.63
    rotation=((math.cos(angle),0.,math.sin(angle)),(0.,1.,0.),(-math.sin(angle),0.,math.cos(angle)))
    tensor=tuple(tuple(sum(rotation[a][c]*rotation[b][c]/principal[c] for c in range(3)) for b in range(3)) for a in range(3))
    inertia=tuple(tuple(sum(rotation[a][c]*rotation[b][c]*principal[c] for c in range(3)) for b in range(3)) for a in range(3))
    ae=(0.,math.cos(.2),math.sin(.2))
    axes=((math.cos(.3),-math.sin(.3),0.),(math.cos(.28),-math.sin(.28),0.),(math.cos(.4),0.,math.sin(.4)),(math.cos(.4),0.,-math.sin(.4)))
    rear=tuple(ratio/2*(axes[2][a]+axes[3][a]) for a in range(3))
    ge=tuple(-v for v in ae)+(1.,0.,0.,0.,0.)
    gc=tuple(-ae[a]-rear[a] for a in range(3))+(1.,0.,0.,-ratio/2,-ratio/2)
    gl=rear+(0.,0.,0.,ratio/2,ratio/2)
    gb=axes[wheel]+(0.,)+tuple(float(i==wheel) for i in range(4))
    gradients=gc,gl,gb
    def mass(v):
        return tuple(dot(row,v[:3]) for row in inertia)+(je*v[3],)+tuple(jw*x for x in v[4:])
    def minv(v):
        return tuple(dot(row,v[:3]) for row in tensor)+(v[3]/je,)+tuple(x/jw for x in v[4:])
    mg=minv(ge)
    factor=h*drag/(1+h*drag*dot(ge,mg))
    def mobility(v):
        base=minv(v)
        return tuple(base[i]-factor*mg[i]*dot(mg,v) for i in range(8))
    responses=tuple(mobility(g) for g in gradients)
    d=tuple(tuple(dot(g,response) for response in responses) for g in gradients)
    return gradients,ge,mass,mobility,mg,drag,d,responses,axes


def main():
    OUT.mkdir(exist_ok=False)
    (OUT/'source.py').write_bytes(Path(__file__).read_bytes())
    (OUT/'two-port-source.py').write_bytes(proof_path.read_bytes())
    before=hashes()
    trials=[]
    for h in (1/240,1/960):
        for ratio in (-12.,12.):
            for wheel in (0,2):
                gradients,ge,mass,mobility,mg,drag,d,responses,axes=model(h,ratio,wheel)
                for eta in (.88,1.):
                    for cmode in ('locked','positive-slip','negative-slip'):
                        for gmode in ('static','positive-motion','negative-motion'):
                            for bmode in ('locked','positive-slip','negative-slip'):
                                clutch=120. if cmode=='locked' else (300. if cmode=='positive-slip' else -300.)
                                delta=0. if cmode=='locked' else (40. if cmode=='positive-slip' else -40.)
                                speed=0. if gmode=='static' else (40. if gmode=='positive-motion' else -40.)
                                brake=60. if bmode=='locked' else (600. if bmode=='positive-slip' else -600.)
                                wheel_speed=0. if bmode=='locked' else (30. if bmode=='positive-slip' else -30.)
                                low,high=limits(clutch,eta)
                                loss=(low+high)/2 if gmode=='static' else (high if gmode=='positive-motion' else low)
                                expected=(clutch,loss,brake)
                                free=tuple((delta,speed,wheel_speed)[i]+h*dot(d[i],expected) for i in range(3))
                                weights=solve_three(d,free)
                                qfree=tuple(sum(weights[j]*responses[j][i] for j in range(3)) for i in range(8))
                                gross=140.
                                q0=tuple(qfree[i]+h*mg[i]*(drag*dot(ge,qfree)-gross) for i in range(8))
                                result,labels=active_three(free,d,h,300.,600.,eta)
                                value,speeds,modes,rows=result
                                assert max(abs(value[i]-expected[i]) for i in range(3))<1e-8,(cmode,gmode,bmode,value,expected)
                                reference=nested_three(free,d,h,300.,600.,eta)
                                difference=max(abs(value[i]-reference[i]) for i in range(3))
                                assert difference<1e-8
                                qend=tuple(qfree[i]-h*sum(value[j]*responses[j][i] for j in range(3)) for i in range(8))
                                ue=dot(ge,qend)
                                change=tuple(qend[i]-q0[i] for i in range(8))
                                error=(.5*(dot(qend,mass(qend))-dot(q0,mass(q0))+dot(change,mass(change)))
                                       +h*(drag*ue**2+dot(value,speeds)-gross*ue))
                                assert abs(error)<3e-9
                                assert all(h*value[i]*speeds[i]>=-1e-9 for i in range(3))
                                # 接触力对三反力的解析导数，使用当前真正活动集。
                                gx=tuple(cross((.7,1.,-.3),(0.,1.,0.))[a]-.33*axes[wheel][a] for a in range(3))+(0.,)+tuple(-.33 if i==wheel else 0. for i in range(4))
                                response=mobility(gx)
                                rhs=tuple(dot(gradients[i],response) if (modes[i]=='locked' or modes[i]=='static') else 0. for i in range(3))
                                derivative=solve_three(rows,rhs)
                                shifted=[]
                                for perturbation in (-.01,.01):
                                    nextfree=tuple(free[i]+h*dot(gradients[i],response)*perturbation for i in range(3))
                                    shifted.append(active_three(nextfree,d,h,300.,600.,eta)[0][0])
                                finite=tuple((shifted[1][i]-shifted[0][i])/.02 for i in range(3))
                                # 容量端点的零滑差可有不同半光滑导数；定向工况均在实际活动集内。
                                derivative_error=max(abs(derivative[i]-finite[i]) for i in range(3))
                                assert derivative_error<1e-7,(modes,derivative,finite)
                                trials.append({'h':h,'ratio':ratio,'wheel':wheel,'eta':eta,'expected_modes':[cmode,gmode,bmode],
                                               'q0':q0,'qend':qend,'free':free,'response':d,'value':value,'speeds':speeds,'modes':modes,
                                               'expected':expected,'labels':labels,'nested':reference,'difference':difference,
                                               'energy_error':error,'force_derivative':derivative,'force_finite':finite,'derivative_error':derivative_error})
    after=hashes()
    assert before==after
    report={'claim':'432 directed fixed-mobility clutch/gear/single-brake trials with analytic contact-force derivative; no nonlinear tire or gyro/world integration; prototype only',
            'source_before':before,'source_after':after,'source_stable':before==after,'trials':trials,
            'maximum_energy_error_j':max(abs(t['energy_error']) for t in trials),
            'maximum_nested_torque_difference_nm':max(t['difference'] for t in trials),
            'maximum_force_derivative_error':max(t['derivative_error'] for t in trials)}
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print({k:report[k] for k in ('maximum_energy_error_j','maximum_nested_torque_difference_nm','maximum_force_derivative_error','source_stable')})


if __name__=='__main__':
    main()
