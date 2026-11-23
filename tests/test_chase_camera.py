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
    assert tuple(position) == pytest.approx((18.,45.,3.75),abs=1e-5)
    assert tuple(camera.target_position) == tuple(position)
    assert tuple(look) == pytest.approx((-2.,45.,1.25),abs=1e-5)


@pytest.mark.parametrize('heading, projected', [(0., 1.), (90., 0.), (180., -1.)])
def test_camera_follows_road_slope_in_its_actual_heading(heading, projected):
    camera = ChaseCamera()
    # 车身悬架俯仰故意不同于道路，不能让镜头追着车身颠簸。
    car = CarState((0., 0., 10.), heading, 0., pitch=20.)
    slope = math.tan(math.radians(7.))*projected
    position, look = camera.update(car, 11., 0., snap=True, road_grade=7., road_heading=0.)
    assert position.z == pytest.approx(10.+3.2-11*slope, abs=1e-6)
    assert look.z == pytest.approx(10.+.7+6*slope, abs=1e-6)
    assert tuple(camera.target_position) == tuple(position)


def test_chassis_pitch_does_not_drive_camera_on_level_road():
    camera = ChaseCamera()
    first = camera.update(CarState((0., 0., .55), 0., 0., pitch=-8.), 11., 0., snap=True)
    second = camera.update(CarState((0., 0., .55), 0., 0., pitch=8.), 11., .04)
    assert tuple(first[0]) == tuple(second[0])
    assert tuple(first[1]) == tuple(second[1])
