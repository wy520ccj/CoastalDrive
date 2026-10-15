"""实际道路与轮心位置决定径向压缩和加载半径。"""

import numpy as np
import pytest
from panda3d.bullet import BulletPlaneShape, BulletRigidBodyNode, BulletWorld
from panda3d.core import BitMask32, Vec3

from unsprung_geometry import read_unsprung_geometry
from vehicle_designs import REFERENCE_DESIGN


def test_loaded_plane_geometry_uses_actual_hub_and_radius_not_suspension_load():
    world = BulletWorld()
    body = BulletRigidBodyNode("query-only-body")
    road = BulletRigidBodyNode("actual-road")
    road.addShape(BulletPlaneShape(Vec3(0,0,1),0))
    road.setIntoCollideMask(BitMask32.bit(0)|BitMask32.bit(1))
    world.attachRigidBody(road)
    centers = np.array(((-.84,1.1,.31),(.84,1.1,.32),(-.84,-1.1,.33),(.84,-1.1,.34)))
    geometry = read_unsprung_geometry(world,body,centers,(0.,0.,1.),((1.,0.,0.),)*4,REFERENCE_DESIGN)
    assert all(hit.node==road for hit in geometry.hits)
    assert geometry.deflection == pytest.approx((.02,.01,0.,-.01),abs=1e-12)
    assert geometry.offsets[:,2] == pytest.approx(-centers[:,2],abs=1e-12)
    assert geometry.normals == pytest.approx(np.tile((0.,0.,1.),(4,1)),abs=1e-12)
    assert geometry.tangents == pytest.approx(np.tile((0.,1.,0.),(4,1)),abs=1e-12)
    assert geometry.laterals == pytest.approx(np.tile((1.,0.,0.),(4,1)),abs=1e-12)
    world.removeRigidBody(road)
    air = read_unsprung_geometry(world,body,centers,(0.,0.,1.),((1.,0.,0.),)*4,REFERENCE_DESIGN)
    assert all(hit is None for hit in air.hits) and np.max(air.deflection)<0.
