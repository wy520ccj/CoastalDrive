"""Bullet ray/support checks for the curved highway display mesh."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from curve_surface_check import run


def test_driven_surface_keeps_authored_meter_samples_without_refining_distant_ground():
    from career_courses import CareerCourse
    from curve_mesh import anchor, surfaces

    curve = CareerCourse('ridge-club')
    mesh = surfaces(curve, 0)
    origin = anchor(curve, 0)
    for name, edges in (('road', (-6.75, 6.75)), ('shoulder-left', (-8.5, -6.75)),
                        ('shoulder-right', (6.75, 8.5))):
        vertices, faces = mesh[name]
        assert len(vertices) == 402
        assert len(faces) == 400
        for s in range(201):
            for side, lateral in enumerate(edges):
                pose = curve.sample(s, lateral)
                assert vertices[s*2+side] == pytest.approx(
                    (pose.x-origin[0], pose.y-origin[1], pose.z-origin[2]), abs=1e-12)
    # 护栏仍是原5m采样；远地形沿用自己的8m网格。
    assert len(mesh['rail-left'][0]) == 41*4


def test_equal_extension_meshes_share_shapes_with_independent_real_world_transforms():
    from panda3d.bullet import BulletTriangleMeshShape, BulletWorld
    from panda3d.core import BitMask32, Vec3

    from career_courses import CareerCourse
    from curve_mesh import surfaces
    from streamed_road import StreamedRoad

    curve, world = CareerCourse('ridge-club'), BulletWorld()
    stream = StreamedRoad(world, 0, curve)
    stream.add(6, 0)
    stream.add(7, 0)
    edge_sdk = getattr(BulletTriangleMeshShape, "enable_internal_edge_adjustment", None) is not None
    for offset, name in enumerate(surfaces(curve, 6)):
        first, second = stream.segments[6][offset], stream.segments[7][offset]
        assert stream.meshes[6][name] == stream.meshes[7][name]
        assert first.getShape(0) == second.getShape(0)
        assert first.notifiesCollisions() == second.notifiesCollisions() == (edge_sdk and name == "road")
        assert first.getPythonTag('suspension_mesh') is second.getPythonTag('suspension_mesh')
        assert first != second and first.getTransform() != second.getTransform()
    for distance in (1300, 1500):
        pose = curve.sample(distance, 3.)
        hit = world.rayTestClosest(Vec3(pose.x, pose.y, pose.z+1),
                                   Vec3(pose.x, pose.y, pose.z-1), BitMask32.bit(0))
        assert hit.hasHit() and hit.getHitPos().z == pytest.approx(pose.z, abs=.015)
    before = stream.segments[7][0].getShape(0)
    stream.add(0, 0)
    assert stream.segments[0][0].getShape(0) != before


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize("hills", [False, True])
def test_curve_mesh_support(seed, hills):
    result = run(seed, hills)
    assert result["max_error_m"] <= 0.015
    assert result["max_marking_error_m"] <= 0.015
    assert result["max_join_gap_m"] <= 1e-8
    assert result["join_comparisons"] > 0
    assert result["min_tree_clearance_m"] >= 20.0
