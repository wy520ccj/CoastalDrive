"""用冻结原模型独立重算残差/能量；只复制数值缓存，不创建或推进物理世界。"""

import copy
from dataclasses import replace

import numpy as np
from lab_solver_model_reference import make_joint_model


def model_for(arguments,keywords):
    options=keywords.copy()
    motion=options.get('finite_motion')
    if motion is not None:
        motion=copy.copy(motion);motion.key,motion.cached=None,None
        options['finite_motion']=motion
    finite=options.get('finite_contact')
    if finite is not None:
        original=finite
        finite=copy.copy(original);finite.roads=copy.copy(original.roads)
        finite.roads.surfaces=tuple(replace(surface) for surface in original.roads.surfaces)
        finite.cache_key,finite.cached=None,None
        finite.query_cache=None if all(s.plane is not None for s in finite.roads.surfaces) else [{} for _ in finite.roads.surfaces]
        if original.finite_motion is keywords.get('finite_motion'):
            finite.finite_motion=motion
        elif original.finite_motion is not None:
            finite.finite_motion=copy.copy(original.finite_motion)
            finite.finite_motion.key,finite.finite_motion.cached=None,None
        options['finite_contact']=finite
    return make_joint_model(*arguments,**options)


def verify_result(model,result):
    evaluate,finish,_state_scale,_row_scale=model
    values=np.r_[result.velocity,result.forces.ravel(),result.port_torques]
    residual,details=evaluate(values)
    errors=tuple(float(np.max(np.abs(part))) for part in (residual[:16],residual[16:24],residual[24:]))
    assert errors[0]<1e-9 and errors[1]<1e-5 and errors[2]<1e-9,errors
    independent=finish(values,details,result.iterations-1,*errors)
    gap=abs(independent.energy_error-result.energy_error)
    assert gap<3e-8,gap
    return {'momentum_error':errors[0],'force_error':errors[1],'port_error':errors[2],'energy_recompute_gap':gap,
            'reported_momentum_error':result.momentum_error,'reported_force_error':result.force_error}
