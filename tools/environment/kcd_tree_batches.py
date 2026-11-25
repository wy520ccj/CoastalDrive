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
        # 两级轮廓使用互补交错梯度噪声交接，消除 4×4 规则网格点阵颗粒感，同时避免双层 A2C 孔洞。
        coverage = '''
float tree_threshold = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
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


def baked_far_mesh(tree, root, _cache=None):
    """只烘焙原LOD2的种植变换与坡根，UV/顶点遮蔽/索引保持原值。"""
    part = tree.getChild(2)
    geom = part.node().getGeom(0)
    data = geom.getVertexData()
    if data.getFormat() != GeomVertexFormat.getV3n3c4t2() or geom.getNumPrimitives() != 1:
        raise ValueError('远树合批需要原V3n3c4t2索引三角网格：'+part.getName())
    primitive = geom.getPrimitive(0)
    if primitive.getIndexType() != Geom.NTUint32:
        raise ValueError('原树三角形索引应为uint32：'+part.getName())
    key = (id(data), id(primitive))
    cached = _cache.get(key) if _cache is not None else None
    if cached is None:
        base_packed = np.frombuffer(data.getArray(0).getHandle().getData(), dtype=SOURCE_DTYPE).copy()
        base_points = base_packed['p'].astype(np.float64)
        base_normals = base_packed['n'].astype(np.float64)
        base_indices = np.frombuffer(primitive.getVertices().getHandle().getData(), dtype='<u4').copy()
        stage = part.findAllTextureStages()[0]
        cached = (base_packed, base_points, base_normals, base_indices, stage)
        if _cache is not None:
            _cache[key] = cached
    else:
        base_packed, base_points, base_normals, base_indices, stage = cached
    packed = base_packed.copy()
    points = base_points.copy()
    texture_matrix = part.getNetState().getAttribDef(TexMatrixAttrib.getClassSlot()).getTransform(stage).getMat()
    slope = np.array((texture_matrix.getCell(2, 0), texture_matrix.getCell(2, 1)))
    anchor = part.getShaderInput('root_anchor').getVector().x
    t = np.clip((points[:, 2]+anchor)/2., 0, 1)
    points[:, 2] += (1-t*t*(3-2*t))*(points[:, :2]@slope)
    matrix = part.getMat(root)
    transform = np.array([[matrix.getCell(r, c) for c in range(4)] for r in range(4)])
    packed['p'] = points@transform[:3, :3]+transform[3, :3]
    normals = base_normals@np.linalg.inv(transform[:3, :3]).T
    packed['n'] = normals/np.linalg.norm(normals, axis=1)[:, None]
    center = np.array(tree.getMat(root).xformPoint(tree.node().getCenter()), dtype=np.float32)
    return packed, np.broadcast_to(center, (len(packed), 3)), base_indices


def make_batch(root, name, meshes, state, shader):
    format = GeomVertexFormat(GeomVertexFormat.getV3n3c4t2())
    extra = GeomVertexArrayFormat()
    extra.addColumn(InternalName.make('tree_center'), 3, Geom.NTFloat32, Geom.COther)
    format.addArray(extra)
    data = GeomVertexData(name, GeomVertexFormat.registerFormat(format), Geom.UHStatic)
    total_vertices = sum(len(row[0]) for row in meshes)
    total_indices = sum(len(row[2]) for row in meshes)
    vertices = np.empty(total_vertices, dtype=SOURCE_DTYPE)
    centers = np.empty((total_vertices, 3), dtype=np.float32)
    indices = np.empty(total_indices, dtype='<u4')
    v_pos = 0
    i_pos = 0
    for packed, center_arr, idx in meshes:
        v_len = len(packed)
        i_len = len(idx)
        vertices[v_pos:v_pos + v_len] = packed
        centers[v_pos:v_pos + v_len] = center_arr
        indices[i_pos:i_pos + i_len] = idx + np.uint32(v_pos)
        v_pos += v_len
        i_pos += i_len
    data.setNumRows(total_vertices)
    data.modifyArray(0).modifyHandle().setData(vertices.tobytes())
    data.modifyArray(1).modifyHandle().setData(centers.tobytes())
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
    city = root.find('**/mainland-city')
    if not city.isEmpty():
        city_trees = [tree for tree in city.findAllMatches('**/kcd-oak-*') if isinstance(tree.node(), LODNode)]
        if city_trees:
            groups['city'] = city_trees
    # 只收LOD根且跳过已隐藏节点（含被父节点隐藏的越界树），不能把同名前缀的各级Geom算成另一株。
    groups = {
        key: [
            tree for tree in trees
            if isinstance(tree.node(), LODNode) and not tree.isHidden() and not tree.getParent().isHidden()
        ]
        for key, trees in groups.items()
    }
    mesh_cache = {}
    report = []
    for cell, trees in sorted(groups.items(), key=lambda item: (isinstance(item[0], str), item[0])):
        if not trees:
            continue
        lod = LODNode('local-near-tree-distance')
        near_group = root.attachNewNode(lod).attachNewNode('local-near-trees')
        near_group.hide(SHADOW_MASK)
        meshes, centers = [], []
        # 新节点仍挂在当前路段下；只携带相对状态，不能冻结相机等祖先的逐帧输入。
        state = trees[0].getChild(2).getState(root)
        for tree in trees:
            meshes.append(baked_far_mesh(tree, root, _cache=mesh_cache))
            centers.append(meshes[-1][1][0])
            near = tree.copyTo(tree.getParent())
            near.setName('local-near-'+tree.getName())
            near.setState(tree.getState(root))
            near.wrtReparentTo(near_group)
            # 近组直接使用完整3D枝叶的LOD1（不再在30-45m眼前做LOD0/LOD1变形切换与双倍绘制），远距由合批接管。
            near.getChild(2).removeNode()
            near.getChild(0).removeNode()
            near.node().clearSwitches()
            near.node().addSwitch(10000, 0)
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
