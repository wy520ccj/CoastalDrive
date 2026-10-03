"""传动联合原型的世界旋转协变与显式曲轴摩擦/双向效率补充。"""

import json
import math
import runpy
from dataclasses import replace
from pathlib import Path

BASE=Path(__file__).parent
SOURCE=BASE/'drive-contact-joint-r2-probe.py'
module=runpy.run_path(str(SOURCE))
advance,hashes=module['advance_joint'],module['hashes']
ContactFrame,Mobility=module['ContactFrame'],module['Mobility']
INERTIA=module['INERTIA']
OUT=BASE/'drive-contact-world-initial'


def restore(reference):
    frames=[]
    for f in reference['frames']:
        fields={**f,'mobility':Mobility(**f['mobility'])}
        for name in ('tangent','axle','point','hub','response_x','response_y','response_t','spin_axis','moment_x'):
            fields[name]=tuple(f[name])
        fields['elastic_frame']=tuple(tuple(v) for v in f['elastic_frame'])
        frames.append(ContactFrame(**fields))
    return tuple(frames)


def rotate(vector,rotation):
    return tuple(sum(row[a]*vector[a] for a in range(3)) for row in rotation)


def run():
    OUT.mkdir(exist_ok=False)
    (OUT/'source.py').write_bytes(Path(__file__).read_bytes())
    (OUT/'joint-source.py').write_bytes(SOURCE.read_bytes())
    before=hashes()
    references=json.loads((BASE/'drive-contact-joint-r1/summary.json').read_text(encoding='utf-8'))['trials']
    a,b=.63,.4
    rz=((math.cos(b),-math.sin(b),0.),(math.sin(b),math.cos(b),0.),(0.,0.,1.))
    ry=((math.cos(a),0.,math.sin(a)),(0.,1.,0.),(-math.sin(a),0.,math.cos(a)))
    rotation=tuple(tuple(sum(rz[i][k]*ry[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    inertia=tuple(tuple(sum(rotation[i][k]*rotation[j][k]*INERTIA[k] for k in range(3)) for j in range(3)) for i in range(3))
    inverse=tuple(tuple(sum(rotation[i][k]*rotation[j][k]/INERTIA[k] for k in range(3)) for j in range(3)) for i in range(3))
    trials=[]
    try:
        for old in references:
            r=old['input']
            frames=tuple(replace(f,**{name:rotate(getattr(f,name),rotation) for name in ('tangent','axle','point','hub','response_x','response_y','response_t','spin_axis','moment_x')},
                                 elastic_frame=tuple(rotate(v,rotation) for v in f.elastic_frame)) for f in restore(r))
            # 世界旋转只改向量/惯量，接触标量与实际广义约束必须同值。
            result=advance(rotate(r['initial_velocity'],rotation),rotate(r['initial_angular'],rotation),r['initial_wheel_omega'],r['initial_engine_omega'],
                frames,r['deformation'],r['engine_torque_nm'],r['clutch_capacity_nm'],r['ratio'],r['brake_capacities_nm'],r['h_s'],
                engine_axis=rotate((0.,1.,0.),rotation),body_inertia=inertia,inverse_tensor=inverse)
            expected=rotate(old['qend'][:3],rotation)+tuple(old['qend'][3:])
            error=max(abs(result['qend'][i]-expected[i]) for i in range(8))
            force_error=max(abs(result['contacts'][i][key]-old['contacts'][i][key]) for i in range(4) for key in ('fx','fy','brake_torque'))
            assert error<1e-9 and force_error<1e-6,(r['case'],error,force_error)
            result.update({'kind':'world-rotation','case':r['case'],'input':r,'body_inertia':inertia,'inverse_tensor':inverse,'rotation':rotation,
                           'covariance_state_error':error,'covariance_force_error':force_error})
            trials.append(result)
        for old in references:
            if old['bank']!=0.:
                continue
            r=old['input']
            for drag in (.12,.6):
                for eta in (.88,1.):
                    result=advance(r['initial_velocity'],r['initial_angular'],r['initial_wheel_omega'],r['initial_engine_omega'],restore(r),r['deformation'],
                        r['engine_torque_nm'],r['clutch_capacity_nm'],r['ratio'],r['brake_capacities_nm'],r['h_s'],drag=drag,eta=eta)
                    result.update({'kind':'drag-efficiency','case':r['case'],'input':r,'drag':drag,'eta':eta})
                    trials.append(result)
    except (AssertionError,ArithmeticError) as error:
        (OUT/'failure.json').write_text(json.dumps({'error':repr(error),'completed':len(trials),'input':r,'source_stable':before==hashes()},indent=2),encoding='utf-8')
        raise
    after=hashes()
    assert before==after
    report={'claim':'48 full-tensor world rotations +64 implicit-engine-drag/efficiency steps; instantaneous axes only, no native/full trajectories',
        'source_before':before,'source_after':after,'source_stable':before==after,'trials':trials,
        'maximum_energy_error_j':max(abs(t['energy_error_j']) for t in trials),
        'maximum_momentum_error_nms':max(max(abs(v) for v in t['momentum_error_nms']) for t in trials),
        'maximum_covariance_state_error':max(t['covariance_state_error'] for t in trials if t['kind']=='world-rotation'),
        'maximum_covariance_force_error':max(t['covariance_force_error'] for t in trials if t['kind']=='world-rotation'),
        'maximum_sweeps':max(len(t['sweeps']) for t in trials)}
    (OUT/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print({k:report[k] for k in ('maximum_energy_error_j','maximum_momentum_error_nms','maximum_covariance_state_error','maximum_covariance_force_error','maximum_sweeps','source_stable')})


if __name__=='__main__':
    run()
