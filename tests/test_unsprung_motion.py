"""独立几何展开核对末压缩/速度，不用冻结行程近似生成期望。"""

import numpy as np
import pytest
from test_unsprung_joint import hardware

from unsprung_motion import FiniteSuspensionMotion
from vehicle_designs import REFERENCE_DESIGN


def case():
    graph,_contacts,_partition = hardware(REFERENCE_DESIGN)
    position = np.array((1.,2.,.8))
    arms = graph.mechanical.wheel_arms
    q0 = np.array((.02,.03,.04,.01))
    bias = np.array(((.01,-.02,0.),)*4)
    motion = FiniteSuspensionMotion(position,np.eye(3),position+arms,q0,graph.mechanical,bias,1/240)
    return motion,arms,q0,bias


def test_translation_and_axial_travel_have_no_geometric_correction():
    motion,_arms,q0,_bias = case()
    z = np.zeros(16);z[:3]=(.4,10.,-.2);z[6:10]=(.2,-.1,.3,-.2)
    result = motion.evaluate(z)
    assert result.compression==pytest.approx(q0+motion.dt*z[6:10],abs=1e-15)
    assert result.relative_velocity==pytest.approx(z[6:10],abs=1e-15)


def test_finite_pitch_uses_true_projected_length_and_time_derivative():
    motion,arms,q0,bias = case()
    z = np.zeros(16);z[:3]=(.2,3.,.1);z[4]=.7;z[6:10]=(.1,-.2,.15,-.1)
    h,theta = motion.dt,motion.dt*z[4]
    guide = np.array((np.sin(theta),0.,np.cos(theta)))
    speeds = z[:3]+np.cross((0.,.7,0.),arms)+z[6:10,None]*np.array((0.,0.,1.))+bias
    end_arms = arms+h*(speeds-z[:3])
    projected = q0+end_arms@guide-arms[:,2]
    actual_rate = (speeds-z[:3]-np.cross((0.,.7,0.),end_arms))@guide
    result = motion.evaluate(z)
    assert result.compression==pytest.approx(projected,abs=4e-16)
    assert result.relative_velocity==pytest.approx(actual_rate,abs=4e-16)
    assert np.max(np.abs(result.compression-(q0+h*z[6:10])))>1e-7
    assert np.max(np.abs(result.relative_velocity-z[6:10]))>1e-4
    assert motion.evaluate(z) is result
