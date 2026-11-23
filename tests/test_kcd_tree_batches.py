"""远树合批保持原根部变换、着色数据与索引；不依赖原安装。"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/environment'))

from kcd_tree_batches import baked_far_mesh, batch_steps, shaders
from local_kcd_drive import set_root_slope
from panda3d.core import BitMask32, FadeLODNode, NodePath, Shader, Texture, Vec3

from environment.surface_mesh import surface_mesh


def tree_fixture(parent):
    tree = parent.attachNewNode(FadeLODNode('kcd-oak-fixture'))
    for level, switch in enumerate(((45, 0), (130, 45), (700, 130))):
        part = surface_mesh('source-'+str(level), [(0, 0, 0), (1, 0, 0), (0, 1, 3)], [(0, 1, 2)],
                            [(0, 0, 1)]*3, [(1, .5, .25, 1)]*3, [(0, 0), (1, 0), (0, 1)])
        part.reparentTo(tree)
        part.setZ(-.03)
        part.setTexture(Texture('atlas'))
        part.setShaderInput('root_anchor', -.03)
        tree.node().addSwitch(*switch)
    tree.node().setCenter(Vec3(0, 0, 1.5))
    return tree


def test_baked_far_mesh_keeps_root_deformation_and_source_attributes():
    root = NodePath('segment')
    tree = tree_fixture(root)
    tree.setPos(5, 20, 2)
    tree.setScale(2)
    set_root_slope(tree, (.2, -.1))
    packed, centers, indices = baked_far_mesh(tree, root)
    assert packed['p'] == pytest.approx(np.array([[5, 20, 1.94], [7, 20, 2.34], [5, 22, 7.94]]), abs=1e-6)
    assert packed['n'] == pytest.approx(np.array([[0, 0, 1]]*3))
    assert packed['uv'] == pytest.approx(np.array([[0, 0], [1, 0], [0, 1]]))
    assert np.array_equal(indices, (0, 1, 2))
    assert np.array_equal(packed['c'], [[255, 128, 64, 255]]*3)
    assert centers == pytest.approx(np.array([[5, 20, 5]]*3))


def test_tree_batch_accepts_identity_slope_and_keeps_original_shadow_tree():
    root = NodePath('segment')
    cell = root.attachNewNode('detail-cell-0')
    original = tree_fixture(cell)
    source = Shader.make(Shader.SLGLSL, '''#version 330
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
void main() { gl_Position=p3d_ModelMatrix*p3d_Vertex; }
''', '''#version 330
out vec4 color;
void main() { float foliage_visibility = 1.; color=vec4(foliage_visibility); }
''')
    phases = list(batch_steps(root, {'local-tree-batch-shaders': shaders(source)}))
    assert phases == ['local-far-tree-bake', 'local-far-tree-batch']
    assert original.getNumChildren() == 3
    assert not original.isHidden(BitMask32.bit(28))
    assert original.isHidden(BitMask32.bit(0))
    assert not root.find('**/local-near-kcd-oak-fixture').isEmpty()
    batch = root.find('**/local-far-tree-batch-0')
    assert batch.node().getGeom(0).getVertexData().getNumRows() == 3
    assert root.getPythonTag('far-tree-batches')[0]['trees'] == 1


def test_reparented_tree_batches_inherit_live_ancestor_inputs():
    from panda3d.core import ShaderAttrib

    root = NodePath('segment')
    root.setShaderInput('camera_world_position', (1., 2., 3.))
    root.setShaderInput('local_origin_y', 0.)
    cell = root.attachNewNode('detail-cell-0')
    tree_fixture(cell)
    source = Shader.make(Shader.SLGLSL, '''#version 330
uniform mat4 p3d_ModelMatrix;
in vec4 p3d_Vertex;
void main() { gl_Position=p3d_ModelMatrix*p3d_Vertex; }
''', '''#version 330
out vec4 color;
void main() { float foliage_visibility = 1.; color=vec4(foliage_visibility); }
''')
    list(batch_steps(root, {'local-tree-batch-shaders': shaders(source)}))
    root.setShaderInput('camera_world_position', (11., 12., 13.))
    root.setShaderInput('local_origin_y', 2000.)
    for path in (root.find('**/local-near-kcd-oak-fixture'), root.find('**/local-far-tree-batch-0')):
        attrib = path.getNetState().getAttrib(ShaderAttrib)
        assert tuple(attrib.getShaderInput('camera_world_position').getVector())[:3] == (11., 12., 13.)
        assert attrib.getShaderInput('local_origin_y').getVector().x == 2000.
