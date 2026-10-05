"""CG参数改变地图初始质心，保持车身/轮连接点世界几何；显式reset不换坐标语义。"""

import math
from dataclasses import replace

import pytest
from panda3d.core import Vec3

from simulation import Simulation
from vehicle_config import body_center, wheel_hubs
from vehicle_designs import REFERENCE_DESIGN


def geometry(car):
    pose = car._chassis.getTransform().getMat()
    return tuple(tuple(pose.xformPoint(Vec3(*point))) for point in (
        body_center(car.config), *wheel_hubs(car.config)))


@pytest.mark.parametrize("track,shape", [("test", "straight"), ("highway", "straight"), ("endless", "hills")])
def test_high_cg_initial_and_recycled_geometry_has_no_artificial_ground_penetration(track, shape):
    base = Simulation(23, track=track, road_shape=shape, traffic_count=1, config=REFERENCE_DESIGN)
    high = Simulation(23, track=track, road_shape=shape, traffic_count=1,
                      config=replace(REFERENCE_DESIGN, center_of_mass_height=.82))
    try:
        for a, b in zip((base.player, *base.npcs), (high.player, *high.npcs)):
            for old, new in zip(geometry(a), geometry(b)):
                assert new == pytest.approx(old, abs=3e-6)
        first = geometry(high.player)
        high.reset(23)
        assert geometry(high.player) == first
        if track == "endless":
            for world in (base, high):
                world.npcs[0].shift(-5000)
                world._update_stream()
                assert world.traffic_cycles == 1
            for old, new in zip(geometry(base.npcs[0]), geometry(high.npcs[0])):
                # 回收点约1km，Float32矩阵的加法/坐标变换各占一个坐标ULP。
                ulp = math.ldexp(1., math.frexp(max(abs(v) for v in old))[1]-24)
                assert new == pytest.approx(old, rel=0, abs=max(3e-6, 2*ulp))
        for world in (base, high):
            world.reset_player()
        for old, new in zip(geometry(base.player), geometry(high.player)):
            assert new == pytest.approx(old, abs=3e-6)
        high.reset_player((95, 4, 1.25), 17, 5)
        assert high.snapshot().player.position == (95., 4., 1.25)
    finally:
        base.close()
        high.close()
