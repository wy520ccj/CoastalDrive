"""跟车相机的帧率无关积分、原点移动和复位。"""

import math

import pytest

from chase_camera import ChaseCamera
from vehicle_state import CarState


@pytest.mark.parametrize('intervals', [[1/120]*600, [1/60]*300, [.008,.025,.011,.056]*50])
def test_constant_velocity_follow_matches_continuous_solution(intervals):
    camera = ChaseCamera()
    camera.update(CarState((0.,0.,.55),0.,20.),11.,0.,snap=True)
    elapsed = 0.
    for dt in intervals:
        elapsed += dt
        position,_ = camera.update(CarState((0.,20*elapsed,.55),0.,20.),11.,dt)
        expected = 20*elapsed-11-20*.08*(1-math.exp(-elapsed/.08))
        assert position.y == pytest.approx(expected,abs=3e-5)


def test_origin_shift_and_snap_preserve_current_target_and_pose():
    camera = ChaseCamera()
    camera.update(CarState((0.,2005.,.55),0.,20.),11.,0.,snap=True)
    camera.shift_origin(2000.)
    position,_ = camera.update(CarState((0.,5.2,.55),0.,20.),11.,.01)
    expected = 5.2-11-20*.08*(1-math.exp(-.01/.08))
    assert position.y == pytest.approx(expected,abs=1e-5)
    car = CarState((4.,45.,.55),90.,0.)
    position,look = camera.update(car,14.,.02,snap=True)
    assert tuple(position) == pytest.approx((18.,45.,4.75),abs=1e-5)
    assert tuple(camera.target_position) == tuple(position)
    assert tuple(look) == pytest.approx((-2.,45.,1.25),abs=1e-5)
