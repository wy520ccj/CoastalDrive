"""合批只共享完全相同的材质，保留各动态轮枢轴及材质数值。"""

from panda3d.core import GeomVertexReader, Material, MaterialAttrib, NodePath, Vec3, Vec4

from scene import make_quad
from vehicle_visual import batch_driving_geometry


def test_equal_materials_batch_without_merging_distinct_surfaces():
    root = NodePath('vehicle')
    body = root.attachNewNode('body')
    material = Material('body-paint')
    material.setBaseColor((.3, .5, .7, 1))
    material.setRoughness(.3)
    for number in range(3):
        surface = make_quad(str(number), Vec3(number*3, 0, 0), 1, 1, Vec4(1), 0)
        copied = Material(material)
        if number == 2:
            copied.setRoughness(.7)
        surface.setMaterial(copied, 2)
        surface.reparentTo(body)
    wheels = [root.attachNewNode('wheel-'+str(number)) for number in range(4)]
    batch_driving_geometry(root, wheels)
    nodes = list(body.findAllMatches('**/+GeomNode'))
    assert sum(node.node().getNumGeoms() for node in nodes) == 2
    roughness = []
    vertices = []
    for node in nodes:
        for number in range(node.node().getNumGeoms()):
            state = node.getNetState().compose(node.node().getGeomState(number))
            roughness.append(round(state.getAttrib(MaterialAttrib).getMaterial().getRoughness(), 3))
            assert state.getOverride(MaterialAttrib.getClassSlot()) == 2
            reader = GeomVertexReader(node.node().getGeom(number).getVertexData(), 'vertex')
            while not reader.isAtEnd():
                vertices.append(tuple(reader.getData3f()))
            del reader
    assert sorted(roughness) == [.3, .7]
    assert len(vertices) == 18
    assert min(p[0] for p in vertices) == -1.
    assert max(p[0] for p in vertices) == 7.
    assert all(not wheel.isEmpty() and wheel.getParent() == root for wheel in wheels)
