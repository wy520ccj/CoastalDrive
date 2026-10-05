"""真实GLB/BAM装配与真实Bullet外廓、快照轮姿之间的工程尺寸契约。"""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from panda3d.core import NodePath, Quat
from physics.export_reference import shape_axis_limits, shape_volume_center

from scene import Scene
from simulation import Simulation
from skins import vehicle_definition
from vehicle_config import wheel_hubs
from vehicle_designs import REFERENCE_DESIGN
from vehicle_visual import load_vehicle


@pytest.mark.parametrize("model_id", ["reference-rwd", "sedan"])
def test_modified_geometry_matches_native_shape_and_snapshot(model_id):
    config = replace(REFERENCE_DESIGN, mass=1450, body_inertia=(700, 950, 1100),
                     wheel_radius=.37, wheel_width=.245, wheelbase=2.6, track_width=1.9,
                     center_of_mass_height=.48, front_weight_share=.6,
                     collision_half_width=1.15, collision_half_length=2.45,
                     collision_half_height=.7, body_center_height=.85)
    world = Simulation(23, track="test", traffic_count=0, config=config)
    scene = Scene.__new__(Scene)
    scene.render = NodePath("engineering-geometry")
    scene.sky = scene.render.attachNewNode("sky")
    scene.base = SimpleNamespace(session=SimpleNamespace(simulation=world))
    scene.player, scene.wheels = load_vehicle(scene.render, vehicle_definition(model_id), config=config)
    scene.traffic, scene.traffic_wheels, scene.traffic_signals = [], [], []
    try:
        low, high = scene.player.getTightBounds(scene.player)
        limits = shape_axis_limits(world.player._chassis)
        center = shape_volume_center(world.player._chassis)
        for axis in range(3):
            assert (low[axis], high[axis]) == pytest.approx(
                tuple(edge+center[axis] for edge in limits[axis]), abs=2e-6)
        for pivot, hub in zip(scene.wheels, wheel_hubs(config)):
            assert tuple(pivot.getPos()) == pytest.approx((hub[0], hub[1], .37-.48))
        scene.apply(world.snapshot())
        for pivot, wheel in zip(scene.wheels, world.snapshot().player.wheels):
            assert tuple(pivot.getScale()) == (1., 1., 1.)
            assert tuple(pivot.getPos()) == pytest.approx(wheel.position)
            assert abs(pivot.getQuat().dot(Quat(*wheel.orientation))) == pytest.approx(1, abs=1e-5)
            low, high = pivot.getTightBounds(pivot)
            assert tuple(high-low) == pytest.approx((.245, .74, .74), abs=2e-6)
            assert tuple((low+high)/2) == pytest.approx((0., 0., 0.), abs=2e-6)
    finally:
        world.close()
