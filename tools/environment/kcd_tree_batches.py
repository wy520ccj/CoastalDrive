"""本机原树的远景合批；近树与原阴影保留，远模按固定距离交接。"""

from collections import defaultdict
from functools import lru_cache

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
FAR_BATCH_CHUNK = 12


def shaders(source):
    """近远分档共享原木本着色；250–280m 利用 MSAA 覆盖率平滑交接，绝不叠屏幕噪声。"""
    source_fragment = source.getText(Shader.STFragment)
    if 'float foliage_visibility = 1.;' not in source_fragment:
        raise RuntimeError('木本着色器缺少 foliage_visibility 接口')
    source_vertex = source.getText(Shader.STVertex)
    result = []
    for far in (False, True):
        fragment = source_fragment.replace('void main() {', 'flat in float tree_range_alpha;\nvoid main() {').replace(
            'float foliage_visibility = 1.;', 'float foliage_visibility = tree_range_alpha;'
        )
        center = 'in vec3 tree_center;' if far else 'uniform vec3 tree_center;'
        alpha_expr = (
            'smoothstep(248.,266.,tree_distance)*(1.-smoothstep(680.,700.,tree_distance));'
            if far
            else '1.-smoothstep(262.,280.,tree_distance);'
        )
        vertex = source_vertex.replace('void main() {', center + f'''
uniform vec3 camera_world_position;
flat out float tree_range_alpha;
void main() {{
float tree_distance = length((p3d_ModelMatrix*vec4(tree_center,1.)).xyz-camera_world_position);
tree_range_alpha = {alpha_expr}
if (tree_range_alpha <= .0001) {{
    gl_Position=vec4(2.,2.,2.,1.);
    return;
}}
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
        base_points = base_packed['p'].copy()
        base_normals = base_packed['n'].copy()
        base_indices = np.frombuffer(primitive.getVertices().getHandle().getData(), dtype='<u4').copy()
        stage = part.findAllTextureStages()[0]
        anchor = part.getShaderInput('root_anchor').getVector().x
        cached = (base_packed, base_points, base_normals, base_indices, stage, anchor)
        if _cache is not None:
            _cache[key] = cached
    else:
        base_packed, base_points, base_normals, base_indices, stage, anchor = cached
    packed = base_packed.copy()
    tex_attrib = tree.getAttrib(TexMatrixAttrib)
    if tex_attrib is None:
        tex_attrib = part.getAttrib(TexMatrixAttrib)
    if tex_attrib is not None and tex_attrib.hasStage(stage):
        texture_matrix = tex_attrib.getTransform(stage).getMat()
        slope_x = texture_matrix.getCell(2, 0)
        slope_y = texture_matrix.getCell(2, 1)
    else:
        slope_x = slope_y = 0.0
    if slope_x != 0.0 or slope_y != 0.0:
        points = base_points.copy()
        t = np.clip((points[:, 2]+anchor)/2., 0.0, 1.0)
        points[:, 2] += (1.0-t*t*(3.0-2.0*t))*(points[:, 0]*slope_x + points[:, 1]*slope_y)
    else:
        points = base_points
    tree_mat = tree.getMat(root)
    matrix = part.getMat(tree) * tree_mat
    m3 = np.array((tuple(matrix.getRow3(0)), tuple(matrix.getRow3(1)), tuple(matrix.getRow3(2))), dtype=np.float32)
    translation = np.array(matrix.getRow3(3), dtype=np.float32)
    packed['p'] = points @ m3 + translation
    tree_scale = tree.getScale()
    if abs(tree_scale.x - tree_scale.y) < 1e-4 and abs(tree_scale.x - tree_scale.z) < 1e-4 and tree_scale.x > 1e-6:
        packed['n'] = base_normals @ (m3 / np.float32(tree_scale.x))
    else:
        inv_t = matrix.getUpper3()
        inv_t.invertInPlace()
        inv_t.transposeInPlace()
        n3 = np.array((tuple(inv_t.getRow(0)), tuple(inv_t.getRow(1)), tuple(inv_t.getRow(2))), dtype=np.float32)
        normals = base_normals @ n3
        packed['n'] = normals / np.linalg.norm(normals, axis=1)[:, None]
    center = np.array(tree_mat.xformPoint(tree.node().getCenter()), dtype=np.float32)
    return packed, np.broadcast_to(center, (len(packed), 3)), base_indices


@lru_cache(maxsize=1)
def _batch_vertex_format():
    format = GeomVertexFormat(GeomVertexFormat.getV3n3c4t2())
    extra = GeomVertexArrayFormat()
    extra.addColumn(InternalName.make('tree_center'), 3, Geom.NTFloat32, Geom.COther)
    format.addArray(extra)
    return GeomVertexFormat.registerFormat(format)


def make_batch(root, name, meshes, state, shader):
    data = GeomVertexData(name, _batch_vertex_format(), Geom.UHStatic)
    total_vertices = sum(len(row[0]) for row in meshes)
    total_indices = sum(len(row[2]) for row in meshes)
    vertices = np.empty(total_vertices, dtype=SOURCE_DTYPE)
    centers = np.empty((total_vertices, 3), dtype=np.float32)
    use_u16 = total_vertices <= 65535
    idx_dtype = '<u2' if use_u16 else '<u4'
    indices = np.empty(total_indices, dtype=idx_dtype)
    v_pos = 0
    i_pos = 0
    for packed, center_arr, idx in meshes:
        v_len = len(packed)
        i_len = len(idx)
        vertices[v_pos:v_pos + v_len] = packed
        centers[v_pos:v_pos + v_len] = center_arr
        indices[i_pos:i_pos + i_len] = idx.astype(idx_dtype) + v_pos if use_u16 else idx + np.uint32(v_pos)
        v_pos += v_len
        i_pos += i_len
    data.setNumRows(total_vertices)
    data.modifyArray(0).modifyHandle().setData(vertices.tobytes())
    data.modifyArray(1).modifyHandle().setData(centers.tobytes())
    triangles = GeomTriangles(Geom.UHStatic)
    triangles.setIndexType(Geom.NTUint16 if use_u16 else Geom.NTUint32)
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
    """每组组织远模与近树；核心视距 285m 内保留稳定 3D LOD1，并拆小批抑制单帧尖峰。"""
    near_shader, far_shader = kit['local-tree-batch-shaders']
    groups = defaultdict(list)
    details = root.find('**/expressway-detail-distance')
    if not details.isEmpty() and details.getNumChildren() > 0:
        for cell in details.getChild(0).getChildren():
            name = cell.getName()
            if name.startswith('detail-cell-'):
                bucket = groups[int(name.split('-')[-1])//2]
                for child in cell.getChildren():
                    if child.getName().startswith('kcd-oak-'):
                        bucket.append(child)
    else:
        for cell in root.findAllMatches('**/detail-cell-*'):
            bucket = groups[int(cell.getName().split('-')[-1])//2]
            for child in cell.getChildren():
                if child.getName().startswith('kcd-oak-'):
                    bucket.append(child)
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
    mesh_cache = kit.setdefault('_far-mesh-cache', {})
    report = []
    for cell, trees in sorted(groups.items(), key=lambda item: (isinstance(item[0], str), item[0])):
        if not trees:
            continue
        state = trees[0].getChild(2).getState(root)
        single_chunk = len(trees) <= FAR_BATCH_CHUNK
        for chunk_index, start in enumerate(range(0, len(trees), FAR_BATCH_CHUNK)):
            chunk = trees[start:start + FAR_BATCH_CHUNK]
            lod = LODNode('local-near-tree-distance')
            near_group = root.attachNewNode(lod).attachNewNode('local-near-trees')
            near_group.setShader(near_shader, 2)
            near_group.hide(SHADOW_MASK)
            meshes, centers = [], []
            for idx, tree in enumerate(chunk):
                meshes.append(baked_far_mesh(tree, root, _cache=mesh_cache))
                centers.append(meshes[-1][1][0])
                # 近组使用普通节点承载完整3D枝叶的LOD1，去掉冗余FadeLODNode避免高速淡入打架导致树突然消失。
                near = near_group.attachNewNode('local-near-'+tree.getName())
                near.setTransform(tree.getTransform(root))
                near.setState(tree.getState())
                tree_center = tree.node().getCenter()
                part = tree.getChild(1).copyTo(near)
                if isinstance(part.node(), GeomNode):
                    part.setShaderInput('tree_center', tree_center-part.getPos())
                # 阴影源树锁定轻量LOD2避免太阳移动时树影LOD跳变闪烁，并大幅减轻4K阴影绘制负载。
                tree.node().forceSwitch(2)
                # Panda第31位是全局隐藏开关；只屏蔽真正的主相机位，保留原太阳投影。
                tree.hide(BitMask32.lowerOn(31) & ~SHADOW_MASK)
                if (idx + 1) % 2 == 0 or idx == len(chunk) - 1:
                    yield 'local-far-tree-bake'
            center = np.mean(centers, axis=0)
            max_r = max(float(np.linalg.norm(p-center)) for p in centers)
            lod.setCenter(Vec3(*center))
            lod.addSwitch(285.0 + max_r, 0.0)
            batch_name = 'local-far-tree-batch-' + str(cell) + ('' if single_chunk else '-' + str(chunk_index))
            batch = make_batch(root, batch_name, meshes, state, far_shader)
            report.append({'trees': len(chunk), 'vertices': batch.node().getGeom(0).getVertexData().getNumRows(),
                           'bytes': sum(row[0].nbytes+row[1].nbytes+row[2].nbytes for row in meshes)})
            yield 'local-far-tree-batch'
    root.setPythonTag('far-tree-batches', report)
