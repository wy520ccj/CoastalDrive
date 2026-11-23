"""与原生整次合批比较实际几何和状态，不用分支调用次数代替结果。"""

import pytest
from panda3d.core import (
    ConfigVariableBool,
    GeomVertexReader,
    Material,
    NodePath,
    Texture,
    Vec3,
    Vec4,
)

from environment.surface_mesh import flatten_steps, set_rail_shadow_coordinates
from scene import make_quad


def records(root):
    result = []
    for path in root.findAllMatches('**/+GeomNode'):
        for geom in path.node().getGeoms():
            data = geom.getVertexData()
            reader = GeomVertexReader(data, 'vertex')
            positions = []
            while not reader.isAtEnd():
                positions.append(tuple(root.getRelativePoint(path, reader.getData3f())))
            result.append((positions, path.getState(root), data.getFormat(),
                           tuple(bytes(a.getHandle().getData()) for a in data.getArrays()),
                           tuple((p.getPrimitiveType(), p.isIndexed(),
                                  tuple(p.getVertex(i) for i in range(p.getNumVertices())))
                                 for p in geom.getPrimitives())))
    return result


@pytest.mark.parametrize('flatten_geoms', [False, True])
def test_staged_batches_equal_original_native_geometry_and_states(flatten_geoms):
    setting = ConfigVariableBool('flatten-geoms')
    previous = setting.getValue()
    setting.setValue(flatten_geoms)
    root = NodePath('source')
    material = Material('road')
    material.setRoughness(.7)
    texture = Texture('road')
    for i in range(40):
        node = make_quad('surface', Vec3(i, 0, 0), 1, 2, Vec4(1, .5, .25, 1))
        node.reparentTo(root)
        node.setPos(i*.2, i*.3, .1)
        node.setH(i*.7)
        node.setMaterial(material, i % 2)
        node.setTexture(texture)
        if i % 2:
            set_rail_shadow_coordinates(node, [(i, j) for j in range(6)])
    first, second = root.copyTo(NodePath('original')), root.copyTo(NodePath('staged'))
    try:
        first.flattenStrong()
        phases = list(flatten_steps(second))
        assert records(first) == records(second)
        assert first.getTightBounds() == second.getTightBounds()
        assert len(phases) == (5 if flatten_geoms else 2)
    finally:
        setting.setValue(previous)
        first.removeNode()
        second.removeNode()
        root.removeNode()
