"""独立俯仰解析核对悬架功差展开阶数；材料力不由能量残差反推。"""

import math

import numpy as np
import pytest
from physics.suspension_work import leading_work


def test_pitch_projection_and_end_rate_have_predicted_second_order_work():
    arm=np.array(((1.,0.,-.2),))
    guide=np.array((0.,0.,1.))
    angular=np.array((0.,.7,0.))
    translation=np.array(((.13,0.,-.11),))
    frozen=np.array((translation[0,2]+.7*arm[0,0],))
    spring,damper=np.array((2400.,)),np.array((-160.,))
    remainders=[]
    for h in (.02,.01,.005):
        angle=.7*h
        g=np.array((math.sin(angle),0.,math.cos(angle)))
        r=arm[0]+h*translation[0]
        delta=float(r@g-arm[0]@guide)
        # 独立写出Ω沿Y的叉积，不调用生产旋转/末运动函数。
        relative=translation[0]-np.array((.7*r[2],0.,-.7*r[0]))
        rate=float(relative@g)
        exact=spring[0]*(delta-h*frozen[0])+h*damper[0]*(rate-frozen[0])
        terms=leading_work(arm,guide,angular,translation,frozen,spring,damper,h)
        assert abs(terms["rate_drift_work"])<1e-14
        remainders.append(abs(exact-sum(terms.values())))
    assert 7.5<remainders[0]/remainders[1]<8.5
    assert 7.5<remainders[1]/remainders[2]<8.5


def test_frozen_rate_drift_has_distinct_first_order_contribution():
    arm=np.zeros((1,3))
    terms=leading_work(arm,np.array((0.,0.,1.)),np.zeros(3),np.array(((0.,0.,.2),)),
        np.array((.19,)),np.array((1200.,)),np.array((40.,)),.01)
    assert terms["rate_drift_work"]==pytest.approx(.124)
    assert terms["rotation_leading_work"]==0.


def test_pure_translation_consistent_port_has_zero_geometric_work():
    terms=leading_work(np.array(((1.,2.,3.),)),np.array((0.,0.,1.)),np.zeros(3),np.array(((.3,.4,.5),)),
        np.array((.5,)),np.array((1700.,)),np.array((30.,)),1/240)
    assert terms=={"rate_drift_work":0.,"rotation_leading_work":0.}
