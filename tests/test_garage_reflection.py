"""实际车型镜像保持接地点、源资源和UI边界。"""

import pytest
from panda3d.core import GeomVertexReader, NodePath

from career_garage import GARAGE_CARS
from skins import vehicle_for_design
from ui.garage_reflection import reflect_vehicle
from vehicle_designs import vehicle_design
from vehicle_visual import WHEEL_NAMES, load_vehicle


@pytest.mark.parametrize('design_id', [car.design_id for car in GARAGE_CARS])
def test_reflection_uses_source_mesh_and_mirrors_about_tire_ground(design_id):
    scene = NodePath('reflection-contract')
    source = scene.attachNewNode('car')
    config = vehicle_design(design_id).config
    _, wheels = load_vehicle(source, vehicle_for_design(design_id, 'sports'), config=config)
    source.setZ(config.center_of_mass_height)
    source.attachNewNode('part-highlight')
    wheels[0].setColorScale(1, .72, .30, 1)
    before = source.getTransform()
    mirror = reflect_vehicle(source, scene, False)
    try:
        assert source.getTransform() == before
        assert not source.find('part-highlight').isEmpty()
        assert source.find(WHEEL_NAMES[0]).hasColorScale()
        for reflected in mirror.getChildren():
            assert reflected.find('part-highlight').isEmpty()
            assert not reflected.find(WHEEL_NAMES[0]).hasColorScale()
            originals = source.findAllMatches('**/+GeomNode')
            copies = reflected.findAllMatches('**/+GeomNode')
            assert len(originals) == len(copies)
            for original, copy in zip(originals, copies):
                for index in range(original.node().getNumGeoms()):
                    geom = original.node().getGeom(index)
                    assert copy.node().getGeom(index) == geom
                    reader = GeomVertexReader(geom.getVertexData(), 'vertex')
                    vertex = reader.getData3f()
                    a = scene.getRelativePoint(original, vertex)
                    b = scene.getRelativePoint(copy, vertex)
                    assert tuple(b) == pytest.approx((a.x, a.y, -a.z), abs=1e-5)
    finally:
        scene.removeNode()
