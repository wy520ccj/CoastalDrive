"""本机原树的远景合批；近树与原阴影保留，远模按固定距离交接。"""

from collections import defaultdict

import numpy as np
from panda3d.core import (
    BitMask32,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    InternalName,
    LODNode,
    Shader,
    TexMatrixAttrib,
    Vec3,
)

SHADOW_MASK = BitMask32.bit(28)
SOURCE_DTYPE = np.dtype([('p', '<f4', 3), ('n', '<f4', 3), ('c', 'u1', 4), ('uv', '<f4', 2)])


def shaders(source):
    """近远分档共享原木本着色，140m内只交接轮廓，不移动或缩放植株。"""
    result = []
    for far in (False, True):
        # 两级轮廓使用互补屏幕样本；把同一alpha交给两次A2C会重叠覆盖并留下孔洞。
        coverage = '''
ivec2 tree_cell = ivec2(gl_FragCoord.xy) & ivec2(3);
int tree_bayer[16] = int[16](0,8,2,10,12,4,14,6,3,11,1,9,15,7,13,5);
float tree_threshold = (float(tree_bayer[tree_cell.x + tree_cell.y * 4])+.5)/16.;
'''
        coverage += ('if (tree_threshold <= 1.-tree_range_alpha) discard;' if far else
                     'if (tree_threshold > tree_range_alpha) discard;')
        fragment = source.getText(Shader.STFragment).replace('void main() {',
            'flat in float tree_range_alpha;\nvoid main() {\n'+coverage)
        center = 'in vec3 tree_center;' if far else 'uniform vec3 tree_center;'
        vertex = source.getText(Shader.STVertex).replace('void main() {', center + '''
uniform vec3 camera_world_position;
flat out float tree_range_alpha;
void main() {
float tree_distance = length((p3d_ModelMatrix*vec4(tree_center,1.)).xyz-camera_world_position);
float far_alpha = smoothstep(120.,140.,tree_distance);
tree_range_alpha = ''' + ('far_alpha*(1.-smoothstep(680.,700.,tree_distance));' if far else '1.-far_alpha;') + '''
if (tree_range_alpha <= .0001) {
    gl_Position=vec4(2.,2.,2.,1.);
    return;
}
''')
        result.append(Shader.make(Shader.SLGLSL, vertex, fragment))
    return tuple(result)


def baked_far_mesh(tree, root):
    """只烘焙原LOD2的种植变换与坡根，UV/顶点遮蔽/索引保持原值。"""
    part = tree.getChild(2)
    geom = part.node().getGeom(0)
    data = geom.getVertexData()
    if data.getFormat() != GeomVertexFormat.getV3n3c4t2() or geom.getNumPrimitives() != 1:
        raise ValueError('远树合批需要原V3n3c4t2索引三角网格：'+part.getName())
    packed = np.frombuffer(data.getArray(0).getHandle().getData(), dtype=SOURCE_DTYPE).copy()
    points = packed['p'].astype(np.float64)
    stage = part.findAllTextureStages()[0]
    texture_matrix = part.getNetState().getAttribDef(TexMatrixAttrib.getClassSlot()).getTransform(stage).getMat()
    slope = np.array((texture_matrix.getCell(2, 0), texture_matrix.getCell(2, 1)))
    anchor = part.getShaderInput('root_anchor').getVector().x
    t = np.clip((points[:, 2]+anchor)/2., 0, 1)
    points[:, 2] += (1-t*t*(3-2*t))*(points[:, :2]@slope)
    matrix = part.getMat(root)
    transform = np.array([[matrix.getCell(r, c) for c in range(4)] for r in range(4)])
    packed['p'] = points@transform[:3, :3]+transform[3, :3]
    normals = packed['n'].astype(np.float64)@np.linalg.inv(transform[:3, :3]).T
    packed['n'] = normals/np.linalg.norm(normals, axis=1)[:, None]
    center = np.array(tree.getMat(root).xformPoint(tree.node().getCenter()), dtype=np.float32)
    primitive = geom.getPrimitive(0)
    if primitive.getIndexType() != Geom.NTUint32:
        raise ValueError('原树三角形索引应为uint32：'+part.getName())
    indices = np.frombuffer(primitive.getVertices().getHandle().getData(), dtype='<u4').copy()
    return packed, np.tile(center, (len(packed), 1)), indices


def make_batch(root, name, meshes, state, shader):
    format = GeomVertexFormat(GeomVertexFormat.getV3n3c4t2())
    extra = GeomVertexArrayFormat()
    extra.addColumn(InternalName.make('tree_center'), 3, Geom.NTFloat32, Geom.COther)
    format.addArray(extra)
    data = GeomVertexData(name, GeomVertexFormat.registerFormat(format), Geom.UHStatic)
    vertices = np.concatenate([row[0] for row in meshes])
    data.setNumRows(len(vertices))
    data.modifyArray(0).modifyHandle().setData(vertices.tobytes())
    data.modifyArray(1).modifyHandle().setData(np.concatenate([row[1] for row in meshes]).tobytes())
    offsets = np.cumsum([0]+[len(row[0]) for row in meshes[:-1]])
    indices = np.concatenate([row[2]+offset for row, offset in zip(meshes, offsets, strict=True)]).astype('<u4')
    triangles = GeomTriangles(Geom.UHStatic)
    triangles.setIndexType(Geom.NTUint32)
    triangles.modifyVertices().modifyHandle().setData(indices.tobytes())
    geom = Geom(data)
    geom.addPrimitive(triangles)
    node = GeomNode(name)
    node.addGeom(geom)
    path = root.attachNewNode(node)
    path.setState(state.removeAttrib(TexMatrixAttrib.getClassType()))
    path.setShader(shader, 2)
    path.hide(SHADOW_MASK)
    return path


def batch_steps(root, kit):
    """每40m组织一批原远模；原树只供太阳，显示近模保持逐树原生45m渐变。"""
    near_shader, far_shader = kit['local-tree-batch-shaders']
    groups = defaultdict(list)
    for cell in root.findAllMatches('**/detail-cell-*'):
        groups[int(cell.getName().split('-')[-1])//2].extend(cell.findAllMatches('**/kcd-oak-*'))
    # 只收LOD根，不能把同名前缀的各级Geom算成另一株。
    groups = {key: [tree for tree in trees if isinstance(tree.node(), LODNode)] for key, trees in groups.items()}
    report = []
    for cell, trees in sorted(groups.items()):
        if not trees:
            continue
        lod = LODNode('local-near-tree-distance')
        near_group = root.attachNewNode(lod).attachNewNode('local-near-trees')
        near_group.hide(SHADOW_MASK)
        meshes, centers = [], []
        # 新节点仍挂在当前路段下；只携带相对状态，不能冻结相机等祖先的逐帧输入。
        state = trees[0].getChild(2).getState(root)
        for tree in trees:
            meshes.append(baked_far_mesh(tree, root))
            centers.append(meshes[-1][1][0])
            near = tree.copyTo(tree.getParent())
            near.setName('local-near-'+tree.getName())
            near.setState(tree.getState(root))
            near.wrtReparentTo(near_group)
            # 近组已有距离剔除；中模在shader归零前不再向空级做第二次时间渐变。
            near.node().clearSwitches()
            near.node().addSwitch(45, 0)
            near.node().addSwitch(701, 45)
            near.getChild(2).removeNode()
            for part in near.getChildren():
                if isinstance(part.node(), GeomNode):
                    part.setShader(near_shader, 2)
                    part.setShaderInput('tree_center', near.node().getCenter()-part.getPos())
            # Panda第31位是全局隐藏开关；只屏蔽真正的主相机位，保留原太阳投影。
            tree.hide(BitMask32.lowerOn(31) & ~SHADOW_MASK)
            yield 'local-far-tree-bake'
        center = np.mean(centers, axis=0)
        lod.setCenter(Vec3(*center))
        lod.addSwitch(141+max(np.linalg.norm(p-center) for p in centers), 0)
        batch = make_batch(root, 'local-far-tree-batch-'+str(cell), meshes, state, far_shader)
        report.append({'trees': len(trees), 'vertices': batch.node().getGeom(0).getVertexData().getNumRows(),
                       'bytes': sum(row[0].nbytes+row[1].nbytes+row[2].nbytes for row in meshes)})
        yield 'local-far-tree-batch'
    root.setPythonTag('far-tree-batches', report)
