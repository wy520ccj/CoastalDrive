"""传动预研：四轮接触/制动与曲轴/离合/齿轮/陀螺共同末状态，生产只读。"""

import json
import math
import runpy
import sys
from dataclasses import replace
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'tests'))
from test_rotor_transport import CONFIG, INERTIA, TENSOR
from tire_compliance import contact_force, contact_jacobian, energy_terms
from tire_coupling import ContactFrame
from tire_properties import tire_grip, tire_stiffness
from wheel_dynamics import Mobility, _solve_force

PORT_PATH=Path(__file__).with_name('drive-brake-active-probe.py')
PORT=runpy.run_path(str(PORT_PATH))
dot,cross,limits,solve_three,hashes=(PORT[k] for k in ('dot','cross','limits','solve_three','hashes'))
TWO=runpy.run_path(str(Path(__file__).with_name('drive-port-active-probe.py')))['active']
OUT=Path(__file__).with_name('drive-contact-joint-r1')
EPS=1e-11


def port_plans(response,h,capacity,brake,eta):
    """缓存当前机械响应的33种实际约束逆矩阵；轮胎迭代只更新自由速度。"""
    plans=[]
    cmodes=('locked','positive-slip','negative-slip') if capacity else ('positive-slip','negative-slip')
    bmodes=('locked','positive-slip','negative-slip') if brake else ('positive-slip','negative-slip')
    for cmode in cmodes:
        for gmode in ('positive-motion','negative-motion','static'):
            for sign in ((-1,1) if gmode!='static' else (0,)):
                slope=1-eta if ((gmode=='positive-motion')==(sign>0)) else 1-1/eta
                for bmode in bmodes:
                    rows=(response[0] if cmode=='locked' else (1.,0.,0.),
                          response[1] if gmode=='static' else (-slope,1.,0.),
                          response[2] if bmode=='locked' else (0.,0.,1.))
                    inverse_columns=tuple(solve_three(rows,tuple(float(i==j) for i in range(3))) for j in range(3))
                    plans.append(((cmode,gmode,bmode),sign,inverse_columns))
    return plans


def port_state(free,d,h,capacity,brake,eta,plans,warm):
    """先检查上一真实活动集；只有物理约束变动才检查其他模式，不回退机制。"""
    order=([warm] if warm is not None else [])+[i for i in range(len(plans)) if i!=warm]
    for index in order:
        modes,sign,inverse_columns=plans[index]
        cmode,gmode,bmode=modes
        rhs=(free[0]/h if cmode=='locked' else (capacity if cmode=='positive-slip' else -capacity),
             free[1]/h if gmode=='static' else 0.,
             free[2]/h if bmode=='locked' else (brake if bmode=='positive-slip' else -brake))
        value=tuple(sum(inverse_columns[j][i]*rhs[j] for j in range(3)) for i in range(3))
        c,l,b=value
        if sign and c*sign < -EPS:
            continue
        low,high=limits(c,eta)
        speeds=tuple(free[i]-h*dot(d[i],value) for i in range(3))
        delta,x,u=speeds
        if abs(c)>capacity+EPS or l<low-EPS or l>high+EPS or abs(b)>brake+EPS:
            continue
        if cmode=='locked' and abs(delta)>EPS or cmode=='positive-slip' and delta < -EPS or cmode=='negative-slip' and delta > EPS:
            continue
        if gmode=='static' and abs(x)>EPS or gmode=='positive-motion' and (x < -EPS or abs(l-high)>EPS) or gmode=='negative-motion' and (x > EPS or abs(l-low)>EPS):
            continue
        if bmode=='locked' and abs(u)>EPS or bmode=='positive-slip' and u < -EPS or bmode=='negative-slip' and u > EPS:
            continue
        return value,speeds,index
    raise ArithmeticError('传动/制动局部活动集无可行解')


def advance_joint(velocity,angular,omega,engine_omega,frames,deformation,engine_torque,capacity,ratio,brakes,h,
                  config=CONFIG,engine_inertia=.2,engine_axis=(0.,1.,0.),drag=0.,eta=.88):
    """四轮块求解；同一物理状态同时闭合端口、制动、非线性接触与轴向输运。"""
    mass,iw=config.mass,config.wheel_inertia
    q0=tuple(angular)+(engine_omega,)+tuple(omega)
    axes=tuple(f.spin_axis for f in frames)
    ge=tuple(-v for v in engine_axis)+(1.,0.,0.,0.,0.)
    rear=tuple(ratio/2*(axes[2][a]+axes[3][a]) for a in range(3))
    gc=tuple(-engine_axis[a]-rear[a] for a in range(3))+(1.,0.,0.,-ratio/2,-ratio/2)
    gl=rear+(0.,0.,0.,ratio/2,ratio/2)
    gu=tuple(axes[i]+(0.,)+tuple(float(j==i) for j in range(4)) for i in range(4))
    gx=tuple(tuple(f.moment_x)+(0.,)+tuple(-f.rolling_radius if j==i else 0. for j in range(4)) for i,f in enumerate(frames))
    gy=tuple(cross(f.point,f.axle)+(0.,0.,0.,0.,0.) for f in frames)
    def m(v):
        return tuple(INERTIA[a]*v[a] for a in range(3))+(engine_inertia*v[3],)+tuple(iw*x for x in v[4:])
    def minv(v):
        return tuple(dot(row,v[:3]) for row in TENSOR)+(v[3]/engine_inertia,)+tuple(x/iw for x in v[4:])
    mg=minv(ge)
    factor=h*drag/(1+h*drag*dot(ge,mg))
    def mobility(v):
        base=minv(v)
        return tuple(base[a]-factor*mg[a]*dot(mg,v) for a in range(8))
    mc,ml=mobility(gc),mobility(gl)
    dcc,dcl,dll=dot(gc,mc),dot(gc,ml),dot(gl,ml)
    responses=tuple((mobility(gx[i]),mobility(gy[i]),mobility(gu[i])) for i in range(4))
    local_d=tuple(((dcc,dcl,dot(gc,responses[i][2])),
                   (dcl,dll,dot(gl,responses[i][2])),
                   (dot(gc,responses[i][2]),dot(gl,responses[i][2]),dot(gu[i],responses[i][2]))) for i in range(4))
    plans=tuple(port_plans(local_d[i],h,capacity,brakes[i],eta) for i in range(4))
    local_warm=[None]*4
    forces=[(0.,0.,0.)]*4
    configurations=(config,config,replace(config,lateral_stiffness=config.rear_lateral_stiffness),replace(config,lateral_stiffness=config.rear_lateral_stiffness))
    rolling=tuple(max(abs(dot(velocity,f.tangent)+dot(angular,f.moment_x)),abs(f.rolling_radius*omega[i]))>=config.static_contact_speed for i,f in enumerate(frames))
    base=tuple(m(q0)[a]+h*engine_torque*ge[a] for a in range(8))
    def spin(q):
        return tuple(engine_inertia*q[3]*engine_axis[a]-iw*sum(q[i+4]*axes[i][a] for i in range(4)) for a in range(3))
    def known(gyro,exclude=None):
        rhs=tuple(base[a]+h*(gyro[a] if a<3 else 0.)+h*sum(
            forces[i][0]*gx[i][a]+forces[i][1]*gy[i][a]-forces[i][2]*gu[i][a] for i in range(4) if i!=exclude) for a in range(8))
        v=tuple(velocity[a]+h/mass*sum(forces[i][0]*frames[i].tangent[a]+forces[i][1]*frames[i].axle[a] for i in range(4) if i!=exclude) for a in range(3))
        return mobility(rhs),v
    def shared(guess):
        q=guess
        for _ in range(30):
            qfree,v=known(cross(spin(q),q[:3]))
            result,_=TWO(dot(gc,qfree),dot(gl,qfree),dcc,dcl,dll,h,capacity,eta)
            c,l=result[:2]
            end=tuple(qfree[a]-h*(c*mc[a]+l*ml[a]) for a in range(8))
            error=max(abs(end[a]-q[a]) for a in range(8))
            q=end
            if error<1e-12:
                return q,v,c,l,result
        raise ArithmeticError('传动/全转子共享末状态超过30次迭代')
    def contact(i,q,v,fx,fy):
        f,car=frames[i],configurations[i]
        vx=dot(v,f.tangent)+dot(q[:3],f.moment_x)
        vy=dot(v,f.axle)+dot(q[:3],cross(f.point,f.axle))
        target,*details=contact_force((fx,fy),deformation[i],(f.rolling_radius*q[i+4]-vx,-vy),max(abs(vx),car.slip_speed),rolling[i],
            tire_grip(f.load,f.mu,car),*tire_stiffness(f.load,car),h,car.tire_contact_stiffness,car.tire_contact_damping,car.tire_shape,car.tire_curvature)
        return target,details,vx,vy
    q=q0
    sweeps=[]
    for sweep in range(20):
        q,v,c,l,port=shared(q)
        gyro=cross(spin(q),q[:3])
        for i in (range(4) if sweep%2==0 else range(3,-1,-1)):
            qbase,vbase=known(gyro,exclude=i)
            f,car=frames[i],configurations[i]
            rx,ry,rb=responses[i]
            def state(fx,fy):
                free=tuple(qbase[a]+h*(rx[a]*fx+ry[a]*fy) for a in range(8))
                port_free=dot(gc,free),dot(gl,free),dot(gu[i],free)
                value,_speeds,index=port_state(port_free,local_d[i],h,capacity,brakes[i],eta,plans[i],local_warm[i])
                local_warm[i]=index
                c,l,b=value
                end=tuple(free[a]-h*(c*mc[a]+l*ml[a]+b*rb[a]) for a in range(8))
                v=tuple(vbase[a]+h/mass*(fx*f.tangent[a]+fy*f.axle[a]) for a in range(3))
                return end,v,b,index
            def residual(fx,fy):
                end,v,_b,_index=state(fx,fy)
                target,_details,_vx,_vy=contact(i,end,v,fx,fy)
                return fx-target[0],fy-target[1]
            def jacobian(fx,fy):
                end,v,_b,index=state(fx,fy)
                _target,_details,vx,vy=contact(i,end,v,fx,fy)
                modes,_sign,columns=plans[i][index]
                derivatives=[]
                for response,tangent in ((rx,f.tangent),(ry,f.axle)):
                    free_derivative=tuple(dot(g,response) if mode in ('locked','static') else 0. for g,mode in zip((gc,gl,gu[i]),modes))
                    dc,dl,db=tuple(sum(columns[j][a]*free_derivative[j] for j in range(3)) for a in range(3))
                    dq=tuple(h*(response[a]-dc*mc[a]-dl*ml[a]-db*rb[a]) for a in range(8))
                    dx=h/mass*dot(tangent,f.tangent)+dot(dq[:3],f.moment_x)
                    dy=h/mass*dot(tangent,f.axle)+dot(dq[:3],cross(f.point,f.axle))
                    derivatives.append((f.rolling_radius*dq[i+4]-dx,-dy,dx))
                slip_jac=tuple(tuple(derivatives[j][a] for j in range(2)) for a in range(2))
                denominator_gradient=tuple(math.copysign(1.,vx)*d[2] for d in derivatives) if abs(vx)>car.slip_speed else (0.,0.)
                target=contact_jacobian((fx,fy),deformation[i],(f.rolling_radius*end[i+4]-vx,-vy),slip_jac,
                    max(abs(vx),car.slip_speed),denominator_gradient,rolling[i],tire_grip(f.load,f.mu,car),*tire_stiffness(f.load,car),
                    h,car.tire_contact_stiffness,car.tire_contact_damping,car.tire_shape,car.tire_curvature)
                return 1-target[0][0],-target[0][1],-target[1][0],1-target[1][1]
            fx,fy,_error=_solve_force(residual,tolerance=.0001,initial=forces[i][:2],jacobian=jacobian)
            _end,_v,b,_index=state(fx,fy)
            forces[i]=fx,fy,b
        q,v,c,l,port=shared(q)
        force_error=max(math.hypot(*(forces[i][a]-contact(i,q,v,*forces[i][:2])[0][a] for a in range(2))) for i in range(4))
        brake_error=max(abs(forces[i][2]-max(-brakes[i],min(brakes[i],forces[i][2]+dot(gu[i],q)/(h*dot(gu[i],responses[i][2]))))) for i in range(4))
        sweeps.append({'force_n':force_error,'brake_nm':brake_error})
        if force_error<.001 and brake_error<1e-9:
            break
    else:
        raise ArithmeticError(f'传动/四轮共同求解超过20轮：{force_error:g}N，制动{brake_error:g}Nm')
    contacts=[]
    for i in range(4):
        fx,fy,b=forces[i]
        _target,details,vx,vy=contact(i,q,v,fx,fy)
        elastic,rate,patch,patch_kappa,patch_alpha,mode=details
        energy,material,road,numerical=energy_terms((fx,fy),deformation[i],elastic,rate,patch,h,config.tire_contact_stiffness,config.tire_contact_damping)
        contacts.append({'fx':fx,'fy':fy,'brake_torque':b,'omega':q[i+4],'relative_omega':dot(gu[i],q),'vx':vx,'vy':vy,
                         'elastic':elastic,'rate':rate,'patch':patch,'mode':mode,'energy':energy,'material':material,'road':road,'numerical':numerical})
    change=tuple(q[a]-q0[a] for a in range(8))
    kinetic=.5*mass*(dot(v,v)-dot(velocity,velocity))+.5*(dot(q,m(q))-dot(q0,m(q0)))
    numerical=.5*mass*sum((v[a]-velocity[a])**2 for a in range(3))+.5*dot(change,m(change))
    elastic=sum(s['energy'] for s in contacts)-.5*config.tire_contact_stiffness*sum(value**2 for d in deformation for value in d)
    contact_loss=sum(s['material']+s['road']+s['numerical'] for s in contacts)
    brake_loss=h*sum(s['brake_torque']*s['relative_omega'] for s in contacts)
    engine_work=h*engine_torque*dot(ge,q)
    drag_loss=h*drag*dot(ge,q)**2
    clutch_loss=h*c*dot(gc,q)
    gear_loss=h*l*dot(gl,q)
    energy_error=kinetic+numerical+elastic+contact_loss+brake_loss+drag_loss+clutch_loss+gear_loss-engine_work
    external=tuple(h*sum(cross(f.point,tuple(f.tangent[a]*s['fx']+f.axle[a]*s['fy'] for a in range(3)))[axis] for f,s in zip(frames,contacts)) for axis in range(3))
    spin_end,spin_start=spin(q),spin(q0)
    momentum=tuple(INERTIA[a]*change[a]+spin_end[a]-spin_start[a]+h*cross(q[:3],spin_end)[a]-external[a] for a in range(3))
    assert abs(energy_error)<3e-9,energy_error
    assert max(abs(value) for value in momentum)<1e-10,momentum
    assert clutch_loss>=-1e-9 and gear_loss>=-1e-9 and brake_loss>=-1e-9
    return {'q0':q0,'qend':q,'velocity_end':v,'clutch':c,'gear_loss_torque':l,'clutch_slip':dot(gc,q),'gear_input':dot(gl,q),
            'engine_drag_coefficient':drag,'sweeps':sweeps,'contacts':contacts,'energy_error_j':energy_error,'momentum_error_nms':momentum,
            'energy_j':{'kinetic':kinetic,'numerical':numerical,'elastic':elastic,'contact_loss':contact_loss,'brake_loss':brake_loss,
                        'drag_loss':drag_loss,'clutch_loss':clutch_loss,'gear_loss':gear_loss,'engine_work':engine_work}}


def main():
    OUT.mkdir(exist_ok=False)
    (OUT/'source.py').write_bytes(Path(__file__).read_bytes())
    (OUT/'three-port-source.py').write_bytes(PORT_PATH.read_bytes())
    before=hashes()
    references=json.loads(Path(__file__).with_name('clutch-rotor-loss-initial').joinpath('summary.json').read_text(encoding='utf-8'))['trials']
    inputs=[r for r in references if r['engine_gyro']]
    trials=[]
    try:
        for reference in inputs:
            # JSON边界还原固定向量字段，内部机械接口仍直接使用tuple。
            restored=[]
            for f in reference['frames']:
                fields={**f,'mobility':Mobility(**f['mobility'])}
                for name in ('tangent','axle','point','hub','response_x','response_y','response_t','spin_axis','moment_x'):
                    fields[name]=tuple(f[name])
                fields['elastic_frame']=tuple(tuple(v) for v in f['elastic_frame'])
                restored.append(ContactFrame(**fields))
            frames=tuple(restored)
            result=advance_joint(reference['initial_velocity'],reference['initial_angular'],reference['initial_wheel_omega'],reference['initial_engine_omega'],
                frames,reference['deformation'],reference['engine_torque_nm'],reference['clutch_capacity_nm'],reference['ratio'],reference['brake_capacities_nm'],reference['h_s'])
            result['case']=reference['case'];result['h']=reference['h_s'];result['bank']=reference['bank_degrees'];result['steering']=reference['steering_degrees']
            result['input']=reference
            result['nested_reference_difference']={'clutch_nm':result['clutch']-reference['clutch_torque_nm'],
                'force_n':max(abs(result['contacts'][i][axis]-reference['wheel_steps'][i][axis]) for i in range(4) for axis in ('fx','fy')),
                'engine_radps':result['qend'][3]-reference['end_engine_omega']}
            trials.append(result)
            (OUT/f'{len(trials):03d}-{reference["case"]}.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
            print(f'PASS {reference["case"]} {reference["h_s"]:g} {reference["bank_degrees"]:g} sweeps={len(result["sweeps"])} energy={result["energy_error_j"]:.3g}',flush=True)
    except (AssertionError,ArithmeticError) as error:
        (OUT/'failure.json').write_text(json.dumps({'error':repr(error),'completed':len(trials),'source_stable':before==hashes(),'input':reference},indent=2),encoding='utf-8')
        raise
    after=hashes()
    assert before==after
    report={'claim':'48 shared-end compliant four-contact/brake/engine/clutch/gear/gyro steps via local active sets; frozen instantaneous axes; no production/native trajectory validation',
        'source_before':before,'source_after':after,'source_stable':before==after,'trials':trials,
        'maximum_energy_error_j':max(abs(t['energy_error_j']) for t in trials),
        'maximum_momentum_error_nms':max(max(abs(v) for v in t['momentum_error_nms']) for t in trials),
        'maximum_sweeps':max(len(t['sweeps']) for t in trials)}
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print({k:report[k] for k in ('maximum_energy_error_j','maximum_momentum_error_nms','maximum_sweeps','source_stable')})


if __name__=='__main__':
    main()
