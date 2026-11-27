"""高速与生涯赛道的独立写实植被、CC0 岩岸巨石、林冠覆盖场与远树合批。"""

from __future__ import annotations

import math
import random
from bisect import bisect_right
from collections import defaultdict
from functools import lru_cache

import numpy as np
from panda3d.core import (
    BitMask32,
    BoundingSphere,
    Filename,
    Geom,
    GeomNode,
    GeomTriangles,
    GeomVertexArrayFormat,
    GeomVertexData,
    GeomVertexFormat,
    GeomVertexReader,
    GeomVertexWriter,
    InternalName,
    Loader,
    LoaderOptions,
    LODNode,
    Mat4,
    NodePath,
    PTALVecBase3f,
    Shader,
    TexMatrixAttrib,
    Texture,
    TransformState,
    Vec3,
)

from career_courses import CareerCourse
from environment.career_coast import _enabled as coast_candidate
from environment.expressway_landscape_materials import (
    SHADOW_MASK,
    boulder_shader,
    grass_shader,
    rock_shader,
    soft_cutout,
    source_texture,
    tree_shader,
    vegetation_material,
)
from environment.expressway_vegetation import TERRAIN_COLUMNS, ground_point
from paths import resource_root

SOURCE_DTYPE = np.dtype([("p", "<f4", 3), ("n", "<f4", 3), ("c", "u1", 4), ("uv", "<f4", 2)])
FAR_BATCH_CHUNK = 12
_NEG_TERRAIN_COLUMNS = tuple(sorted(-v for v in TERRAIN_COLUMNS))
_POS_TERRAIN_COLUMNS = tuple(sorted(TERRAIN_COLUMNS))
_COURSE_NORMALS_CACHE: dict[str, dict] = {}


@lru_cache(maxsize=3)
def _course_grid(course_id: str):
    from career_terrain import terrain

    return {
        (round(x / 8), round(y / 8)): z
        for vertices, _faces in terrain(course_id).values()
        for x, y, z in vertices
    }


def grass_heightfield(course_id):
    return _grass_heightfield(course_id, coast_candidate(course_id) if course_id is not None else False)


@lru_cache(maxsize=4)
def _grass_heightfield(course_id, coastal: bool):
    if coastal:
        from environment.career_coast import _data

        data = _data(course_id)
        pixels = np.nan_to_num(data["heights"], nan=0.0).astype(np.float32)
        tex = Texture("coastal-course-grass-floor")
        tex.setup2dTexture(pixels.shape[1], pixels.shape[0], Texture.TFloat, Texture.FR32)
        tex.setRamImage(pixels.tobytes())
        tex.setMinfilter(Texture.FTNearest)
        tex.setMagfilter(Texture.FTNearest)
        return tex, tuple(map(float, data["grid_origin"])), 1.0
    grid = _course_grid(course_id) if course_id is not None else {(0, 0): 0.0}
    left, bottom = min(k[0] for k in grid), min(k[1] for k in grid)
    width, height = max(k[0] for k in grid) - left + 1, max(k[1] for k in grid) - bottom + 1
    pixels = np.zeros((height, width), dtype=np.float32)
    for (col, row), z in grid.items():
        pixels[row - bottom, col - left] = z
    tex = Texture("course-grass-floor-" + str(course_id))
    tex.setup2dTexture(width, height, Texture.TFloat, Texture.FR32)
    tex.setRamImage(pixels.tobytes())
    tex.setMinfilter(Texture.FTNearest)
    tex.setMagfilter(Texture.FTNearest)
    return tex, (float(left * 8), float(bottom * 8)), float(course_id is not None)


def _bind_foliage_material(
    node: NodePath,
    diff: Texture,
    normal: Texture,
    gloss: Texture,
    transmission: Texture,
    *,
    cutoff: float = 0.38,
    back_diffuse: float = 0.65,
    transmittance_color=(0.75, 0.92, 0.35),
    specular_color=(0.03, 0.03, 0.03),
    view_dep: float = 0.25,
    two_sided: bool = True,
    root_anchor: float = 0.0,
) -> None:
    node.setTexture(diff, 2)
    node.setShaderInput("local_normal", normal)
    node.setShaderInput("local_gloss", gloss)
    node.setShaderInput("local_transmission", transmission)
    node.setShaderInput("foliage_alpha_cutoff", cutoff)
    node.setShaderInput("local_back_diffuse", back_diffuse)
    node.setShaderInput("local_transmittance_color", transmittance_color)
    node.setShaderInput("local_specular_color", specular_color)
    node.setShaderInput("local_normal_view_dependency", view_dep)
    node.setShaderInput("root_anchor", root_anchor)
    if two_sided:
        node.setTwoSided(True)


def _load_bam_nocache(path) -> NodePath:
    if not path.is_file():
        raise FileNotFoundError(f"缺少独立植被/岩岸运行资源：{path}")
    raw = Loader.getGlobalPtr().loadSync(Filename.fromOsSpecific(str(path)), LoaderOptions(LoaderOptions.LFNoCache))
    if raw is None:
        raise OSError(f"无法读取运行资源：{path}")
    return NodePath(raw)


@lru_cache(maxsize=1)
def _packed_v3n3c4t2():
    """显式注册单数组 36 字节 V3n3c4t2 格式，避免 OpenGL GSG 将 color 拆成第二数组。"""
    arr = GeomVertexArrayFormat()
    arr.addColumn(InternalName.getVertex(), 3, Geom.NTFloat32, Geom.CPoint)
    arr.addColumn(InternalName.getNormal(), 3, Geom.NTFloat32, Geom.CNormal)
    arr.addColumn(InternalName.getColor(), 4, Geom.NTUint8, Geom.CColor)
    arr.addColumn(InternalName.getTexcoord(), 2, Geom.NTFloat32, Geom.CTexcoord)
    fmt = GeomVertexFormat()
    fmt.addArray(arr)
    return GeomVertexFormat.registerFormat(fmt)


def _read_packed_v3n3c4t2(vdata: GeomVertexData) -> np.ndarray:
    fmt = _packed_v3n3c4t2()
    if vdata.getFormat() != fmt:
        vdata = vdata.convertTo(fmt)
    return np.frombuffer(vdata.getArray(0).getHandle().getData(), dtype=SOURCE_DTYPE).copy()


def _build_grass_template(tufts_root: NodePath, maps: tuple[Texture, Texture, Texture, Texture], shader: Shader, *, grid: int) -> NodePath:
    """离线风格构造 4m×4m 共享草格，运行时按实例数绘制，不复制顶点。"""
    tufts = []
    for i in range(8):
        gnode = tufts_root.find(f"**/tuft-{i}")
        geom = gnode.node().getGeom(0)
        vdata = geom.getVertexData()
        packed = _read_packed_v3n3c4t2(vdata)
        prim = geom.getPrimitive(0)
        idx = np.frombuffer(prim.getVertices().getHandle().getData(), dtype="<u4").copy()
        tufts.append((packed, idx))

    all_verts = []
    all_idx = []
    v_offset = 0
    rng = random.Random(24024)
    for row in range(grid):
        for col in range(grid):
            family = (row + col) % 2
            # 约 12% 位置混入极克制的海岸野花草簇，其余为鲜绿/金绿双系草叶
            variant = family * 3 + rng.randrange(3) if rng.random() < 0.88 else 6 + rng.randrange(2)
            base_packed, base_idx = tufts[variant]
            x = (col + 0.5 + rng.uniform(-0.34, 0.34)) * 4.0 / grid - 2.0
            y = (row + 0.5 + rng.uniform(-0.34, 0.34)) * 4.0 / grid - 2.0
            angle = rng.uniform(0.0, math.tau)
            scale = rng.uniform(0.85, 1.28)
            width = scale * (11.5 / grid)
            co, si = math.cos(angle), math.sin(angle)
            v = base_packed.copy()
            px, py, pz = base_packed["p"][:, 0], base_packed["p"][:, 1], base_packed["p"][:, 2]
            v["p"][:, 0] = x + (px * co - py * si) * width
            v["p"][:, 1] = y + (px * si + py * co) * width
            v["p"][:, 2] = pz * scale * 1.25
            nx, ny, nz = base_packed["n"][:, 0], base_packed["n"][:, 1], base_packed["n"][:, 2]
            nn = np.stack(((nx * co - ny * si) / width, (nx * si + ny * co) / width, nz / (scale * 1.25)), axis=-1)
            nlen = np.linalg.norm(nn, axis=1, keepdims=True)
            v["n"] = nn / np.where(nlen > 1e-6, nlen, 1.0)
            meta = np.array(
                (
                    round(max(0.0, min(1.0, (x + 2.0) / 4.0)) * 255.0),
                    round(max(0.0, min(1.0, (y + 2.0) / 4.0)) * 255.0),
                    255 if family else 0,
                    round(rng.uniform(0.01, 0.99) * 255.0),
                ),
                dtype=np.uint8,
            )
            v["c"] = meta
            all_verts.append(v)
            all_idx.append(base_idx + np.uint32(v_offset))
            v_offset += len(v)

    verts = np.concatenate(all_verts, axis=0)
    indices = np.concatenate(all_idx, axis=0)
    vdata = GeomVertexData("standalone-stream-grass", _packed_v3n3c4t2(), Geom.UHStatic)
    vdata.setNumRows(len(verts))
    vdata.modifyArray(0).modifyHandle().setData(verts.tobytes())
    prim = GeomTriangles(Geom.UHStatic)
    if len(verts) <= 65535:
        prim.setIndexType(Geom.NTUint16)
        prim.modifyVertices().modifyHandle().setData(indices.astype("<u2").tobytes())
    else:
        prim.setIndexType(Geom.NTUint32)
        prim.modifyVertices().modifyHandle().setData(indices.astype("<u4").tobytes())
    geom = Geom(vdata)
    geom.addPrimitive(prim)
    gnode = GeomNode("standalone-stream-grass")
    gnode.addGeom(geom)
    template = NodePath(gnode)
    template.setShader(shader, 2)
    _bind_foliage_material(
        template,
        maps[0],
        maps[1],
        maps[2],
        maps[3],
        cutoff=0.35,
        back_diffuse=0.55,
        transmittance_color=(0.70, 0.88, 0.32),
        view_dep=0.15,
        two_sided=True,
    )
    template.hide(SHADOW_MASK)
    soft_cutout(template)
    return template


def tree_batch_shaders(source: Shader) -> tuple[Shader, Shader]:
    """近远分档共享木本着色；248–280m 平滑过渡，680–700m 远端柔和消隐。"""
    source_fragment = source.getText(Shader.STFragment)
    if "float foliage_visibility = 1.;" not in source_fragment:
        raise RuntimeError("木本着色器缺少 foliage_visibility 接口")
    source_vertex = source.getText(Shader.STVertex)
    result = []
    for far in (False, True):
        fragment = source_fragment.replace("void main() {", "flat in float tree_range_alpha;\nvoid main() {").replace(
            "float foliage_visibility = 1.;", "float foliage_visibility = tree_range_alpha;"
        )
        center = "in vec3 tree_center;" if far else "uniform vec3 tree_center;"
        alpha_expr = (
            "smoothstep(248.,266.,tree_distance)*(1.-smoothstep(680.,700.,tree_distance));"
            if far
            else "1.-smoothstep(262.,280.,tree_distance);"
        )
        vertex = source_vertex.replace(
            "void main() {",
            center
            + f'''
uniform vec3 camera_world_position;
flat out float tree_range_alpha;
void main() {{
float tree_distance = length((p3d_ModelMatrix*vec4(tree_center,1.)).xyz-camera_world_position);
tree_range_alpha = {alpha_expr}
if (tree_range_alpha <= .0001) {{
    gl_Position=vec4(2.,2.,2.,1.);
    return;
}}
''',
        )
        result.append(Shader.make(Shader.SLGLSL, vertex, fragment))
    return tuple(result)


def load_standalone_pack(parent: NodePath, kit: dict, old_trees, *, coastal: bool = False) -> None:
    """加载独立开放许可橡树、幼橡、灌丛、蕨草、4m 实例化草格及 CC0 岩岸/巨石。"""
    foliage_dir = resource_root() / "assets/game/expressway/standalone-foliage"
    tex_dir = foliage_dir / "textures"
    rocks_dir = resource_root() / "assets/game/expressway/runtime-rocks"

    bark_maps = (
        source_texture(tex_dir / "oak-bark-diff.png", color=True),
        source_texture(tex_dir / "oak-bark-normal.png"),
        source_texture(tex_dir / "oak-bark-gloss.png"),
        source_texture(tex_dir / "oak-bark-transmission.png"),
    )
    leaf_maps = (
        source_texture(tex_dir / "oak-leaf-diff.png", color=True),
        source_texture(tex_dir / "oak-leaf-normal.png"),
        source_texture(tex_dir / "oak-leaf-gloss.png"),
        source_texture(tex_dir / "oak-leaf-transmission.png"),
    )
    shrub_maps = (
        source_texture(tex_dir / "shrub-leaf-diff.png", color=True),
        leaf_maps[1],
        leaf_maps[2],
        leaf_maps[3],
    )
    grass_maps = (
        source_texture(tex_dir / "grass-diff.png", color=True),
        source_texture(tex_dir / "grass-normal.png"),
        source_texture(tex_dir / "grass-gloss.png"),
        source_texture(tex_dir / "grass-transmission.png"),
    )
    fern_maps = (
        source_texture(tex_dir / "fern-diff.png", color=True),
        source_texture(tex_dir / "fern-normal.png"),
        source_texture(tex_dir / "fern-gloss.png"),
        source_texture(tex_dir / "fern-transmission.png"),
    )

    veg_shader = vegetation_material(kit["foliage-shader"])
    kit["standalone-foliage-shader"] = veg_shader
    rooted_oak_shader = tree_shader(veg_shader)
    young_shader = tree_shader(veg_shader, fade_range=(250.0, 290.0))
    shrub_shader = tree_shader(veg_shader, fade_range=(195.0, 235.0))
    fern_shader = tree_shader(veg_shader, filtered_shadows=False, fade_range=(105.0, 135.0))

    def style_oak_subparts(node: NodePath, shader: Shader) -> None:
        bark = node.find("**/bark")
        if not bark.isEmpty():
            bark.setShader(shader, 2)
            _bind_foliage_material(
                bark, *bark_maps, cutoff=0.01, back_diffuse=0.0, view_dep=0.0, two_sided=False
            )
            bark.setShaderInput("local_sky_transmission", 0.0)
        leaves = node.find("**/leaves")
        if not leaves.isEmpty():
            leaves.setShader(shader, 2)
            _bind_foliage_material(
                leaves, *leaf_maps, cutoff=0.42, back_diffuse=0.45, view_dep=0.14, two_sided=True
            )
            leaves.setShaderInput("local_sky_transmission", 0.35)
            soft_cutout(leaves)

    # 1) 5 种成年橡树（LODNode: 0=LOD1, 1=LOD1近景, 2=LOD2远景与阴影代理）
    oaks_bam = _load_bam_nocache(foliage_dir / "oaks.bam")
    trees = []
    for letter in "abcde":
        src = oaks_bam.find(f"**/oak-{letter}")
        lod = LODNode(f"standalone-oak-{letter}")
        node = parent.attachNewNode(lod)
        h = float(src.getTag("source-height"))
        r = float(src.getTag("source-crown-radius"))
        lod.setCenter(Vec3(0, 0, h * 0.5))
        lod1_src = src.find("**/lod1")
        lod2_src = src.find("**/lod2")
        for level, (src_level, sw) in enumerate(((lod1_src, (120, 0)), (lod1_src, (290, 120)), (lod2_src, (1050, 290)))):
            part = src_level.copyTo(node)
            part.setName(f"oak-{letter}-lod{level}")
            style_oak_subparts(part, rooted_oak_shader)
            lod.addSwitch(*sw)
        node.setTag("source-height", f"{h:.4f}")
        node.setTag("source-crown-radius", f"{r:.4f}")
        node.setTag("source-base", "0.0")
        trees.append(node)
    kit["standalone-trees"] = trees
    kit["standalone-tree-batch-shaders"] = tree_batch_shaders(rooted_oak_shader)

    # 更新碰撞树显示模板（保持 tree-0/tree-1 根底 low.z == -0.05、高度 4.5m > 4m，兼容全部测试与城市种植）
    for variant in range(len(old_trees)):
        if f"tree-{variant}" in kit:
            kit[f"tree-{variant}"].removeNode()
        holder = parent.attachNewNode(f"collision-tree-{variant}")
        body = trees[variant].copyTo(holder)
        scale = 4.5 / float(trees[variant].getTag("source-height"))
        low, _high = trees[variant].getChild(0).getTightBounds(trees[variant])
        body.setScale(scale)
        body.setZ(-0.05 - low.z * scale)
        kit[f"tree-{variant}"] = holder

    # 2) 3 种幼橡
    young_bam = _load_bam_nocache(foliage_dir / "young-oaks.bam")
    youngs = []
    for letter in "abc":
        src = young_bam.find(f"**/young-{letter}")
        lod = LODNode(f"standalone-young-{letter}")
        node = parent.attachNewNode(lod)
        h = float(src.getTag("source-height"))
        lod.setCenter(Vec3(0, 0, h * 0.5))
        part = src.copyTo(node)
        style_oak_subparts(part, young_shader)
        lod.addSwitch(296.0, 0.0)
        node.setTag("source-height", f"{h:.4f}")
        youngs.append(node)
    kit["standalone-young-oaks"] = youngs

    # 3) 3 种沿海阔叶灌丛
    shrub_bam = _load_bam_nocache(foliage_dir / "shrubs.bam")
    shrubs = []
    for letter in "abc":
        src = shrub_bam.find(f"**/shrub-{letter}")
        lod = LODNode(f"standalone-shrub-{letter}")
        node = parent.attachNewNode(lod)
        h = float(src.getTag("source-height"))
        lod.setCenter(Vec3(0, 0, h * 0.5))
        part = src.copyTo(node)
        part.setShader(shrub_shader, 2)
        _bind_foliage_material(
            part, *shrub_maps, cutoff=0.38, back_diffuse=0.35, view_dep=0.18, two_sided=True
        )
        part.setShaderInput("local_sky_transmission", 0.4)
        soft_cutout(part)
        lod.addSwitch(242.0, 0.0)
        node.setTag("source-height", f"{h:.4f}")
        shrubs.append(node)
    kit["standalone-shrubs"] = shrubs
    kit["city-shrub"] = shrubs[0]

    # 4) 2 种林下高草/蕨丛
    fern_bam = _load_bam_nocache(foliage_dir / "ferns.bam")
    ferns = []
    for letter in "ab":
        src = fern_bam.find(f"**/fern-{letter}")
        lod = LODNode(f"standalone-fern-{letter}")
        node = parent.attachNewNode(lod)
        h = float(src.getTag("source-height"))
        lod.setCenter(Vec3(0, 0, h * 0.5))
        part = src.copyTo(node)
        part.setShader(fern_shader, 2)
        _bind_foliage_material(
            part, *fern_maps, cutoff=0.35, back_diffuse=0.55, view_dep=0.15, two_sided=True
        )
        part.setShaderInput("local_sky_transmission", 0.0)
        soft_cutout(part)
        node.hide(SHADOW_MASK)
        lod.addSwitch(140.0, 0.0)
        node.setTag("source-height", f"{h:.4f}")
        ferns.append(node)
    kit["standalone-ferns"] = ferns

    # 5) 4m 硬件实例化草格（近 10×10 / 中 6×6）
    tufts_bam = _load_bam_nocache(foliage_dir / "grass-tufts.bam")
    g_shader = grass_shader(veg_shader, coastal=coastal)
    kit["standalone-grass"] = _build_grass_template(tufts_bam, grass_maps, g_shader, grid=10)
    kit["standalone-grass"].reparentTo(parent)
    kit["standalone-grass-mid"] = _build_grass_template(tufts_bam, grass_maps, g_shader, grid=6)
    kit["standalone-grass-mid"].reparentTo(parent)

    # 6) CC0 岩岸与 5 种路旁巨石
    r_shader = rock_shader()
    coastal_bam = _load_bam_nocache(rocks_dir / "coastal-rocks.bam")
    driving_bam = _load_bam_nocache(rocks_dir / "driving-rocks.bam")
    banks = {}
    for label in ("bank-a", "bank-b", "bank-c", "shore"):
        lod = LODNode(f"standalone-coastal-{label}")
        node = parent.attachNewNode(lod)
        lod.setCenter((0, 0, 4 if label != "shore" else 0))
        for level, sw in enumerate(((110, 0), (320, 110), (1050, 320))):
            part = (coastal_bam if label == "shore" else driving_bam).find(f"**/{label}-lod{level}")
            part.copyTo(node)
            lod.addSwitch(*sw)
        node.setShader(r_shader, 3)
        banks[label] = node
    for asset in (coastal_bam, driving_bam):
        for tex in asset.findAllTextures():
            tex.setMinfilter(Texture.FTLinearMipmapLinear)
            tex.setAnisotropicDegree(8)
    kit["standalone-banks"] = banks

    boulder_diff = source_texture(tex_dir / "boulder-diff.png", color=True)
    boulder_nor = source_texture(tex_dir / "boulder-normal.png")
    boulder_gloss = source_texture(tex_dir / "boulder-gloss.png")
    b_shader = boulder_shader()
    boulders_bam = _load_bam_nocache(foliage_dir / "boulders.bam")
    boulders = {}
    for label in ("huge", "large_a", "large_b", "medium", "small"):
        src = boulders_bam.find(f"**/boulder-{label}")
        lod = LODNode(f"standalone-boulder-{label}")
        node = parent.attachNewNode(lod)
        h = float(src.getTag("source-height"))
        lod.setCenter((0, 0, h * 0.5))
        for level, sw in enumerate(((160, 0), (1050, 160))):
            src.find(f"**/lod{level}").copyTo(node)
            lod.addSwitch(*sw)
        node.setTexture(boulder_diff, 2)
        node.setShader(b_shader, 3)
        node.setShaderInput("boulder_normal", boulder_nor)
        node.setShaderInput("boulder_gloss", boulder_gloss)
        node.setTag("source-height", src.getTag("source-height"))
        node.setTag("source-base", src.getTag("source-base"))
        boulders[label] = node
    kit["standalone-boulders"] = boulders


def set_root_slope(node: NodePath, slope: tuple[float, float]) -> None:
    """借用二维 UV 未用的纹理矩阵 Z 列向着色器传递坡度，避免逐树拆分材质状态。"""
    matrix = Mat4(Mat4.identMat())
    matrix.setCell(2, 0, slope[0])
    matrix.setCell(2, 1, slope[1])
    transform = TransformState.makeMat(matrix)
    for stage in node.findAllTextureStages():
        node.setTexTransform(stage, transform)


def set_world_lod_range(node: NodePath, world_distance: float) -> None:
    scale = max(float(node.getSx()), float(node.getSy()), float(node.getSz()), 0.05)
    current = float(node.node().getIn(0)) * scale
    if current < world_distance:
        node.node().clearSwitches()
        node.node().addSwitch(world_distance / scale, 0.0)


def floor_point(curve, d: float, s: float, seed: int):
    if not isinstance(curve, CareerCourse):
        if not TERRAIN_COLUMNS[0] <= abs(d) <= TERRAIN_COLUMNS[-1]:
            return None
        return ground_point(curve, d, s, seed)
    pose = curve.sample(s, d)
    if coast_candidate(curve.course_id):
        from environment.career_coast import _height

        z = _height(curve.course_id, pose.x, pose.y)
        return None if z is None else Vec3(pose.x, pose.y, z)
    grid = _course_grid(curve.course_id)
    col, row = math.floor(pose.x / 8), math.floor(pose.y / 8)
    u, v = pose.x / 8 - col, pose.y / 8 - row
    keys = ((col, row), (col + 1, row), (col + 1, row + 1), (col, row + 1))
    if not all(key in grid for key in keys):
        return None
    a, b, c, e = (grid[key] for key in keys)
    z = a * (1 - u) + b * (u - v) + c * v if u >= v else a * (1 - v) + c * u + e * (v - u)
    return Vec3(pose.x, pose.y, z)


def _fast_endless_floor(curve, d: float, s: float, seed: int, terrain_cache: dict):
    from environment import expressway_route

    if not TERRAIN_COLUMNS[0] <= abs(d) <= TERRAIN_COLUMNS[-1]:
        return None
    columns = _NEG_TERRAIN_COLUMNS if d < 0 else _POS_TERRAIN_COLUMNS
    idx = max(0, min(len(columns) - 2, bisect_right(columns, d) - 1))
    left, right = columns[idx], columns[idx + 1]
    first = math.floor(s / 5) * 5
    u, v = (d - left) / (right - left), (s - first) / 5
    corners = []
    for x, y in ((left, first), (right, first), (right, first + 5), (left, first + 5)):
        key = (x, y)
        pt = terrain_cache.get(key)
        if pt is None:
            tp = expressway_route.terrain_point(curve, x, y, seed)
            pt = (tp.x, tp.y, tp.z)
            terrain_cache[key] = pt
        corners.append(pt)
    a, b, c, e = corners
    if u >= v:
        w0, w1, w2 = 1.0 - u, u - v, v
        return Vec3(
            a[0] * w0 + b[0] * w1 + c[0] * w2,
            a[1] * w0 + b[1] * w1 + c[1] * w2,
            a[2] * w0 + b[2] * w1 + c[2] * w2,
        )
    w0, w1, w2 = 1.0 - v, u, v - u
    return Vec3(
        a[0] * w0 + c[0] * w1 + e[0] * w2,
        a[1] * w0 + c[1] * w1 + e[1] * w2,
        a[2] * w0 + c[2] * w1 + e[2] * w2,
    )


def _valid_verge(curve, p: Vec3, s: float, minimum: float) -> bool:
    if not isinstance(curve, CareerCourse):
        return True
    distance, lateral = curve.project(tuple(p))
    return abs(lateral) >= minimum and abs(distance - s) < 40


def _outside_road(node: NodePath, root: NodePath, origin: Vec3, curve) -> bool:
    low, high = node.getTightBounds(root)
    xs = [low.x, *range(math.ceil(low.x / 4) * 4, math.floor(high.x / 4) * 4 + 1, 4), high.x]
    ys = [low.y, *range(math.ceil(low.y / 4) * 4, math.floor(high.y / 4) * 4 + 1, 4), high.y]
    for x in xs:
        for y in ys:
            world = (x + origin.x, y + origin.y)
            _s, lateral = curve.project(world) if curve else (world[1], world[0])
            if abs(lateral) < 13:
                return False
    return True


def _urban_roadside(curve, d: float, s: float, seed: int) -> bool:
    from environment.expressway_route import city_weight

    return d > 0 and not isinstance(curve, CareerCourse) and city_weight(s, seed) >= 0.95


def rock_steps(root: NodePath, index: int, seed: int, curve, kit: dict, detail_parent):
    """放置 CC0 扫描岩岸、5 种路旁巨石与海侧礁岩，并检查道路净空。"""
    from environment.expressway_route import anchor

    origin = Vec3(*anchor(curve, index))
    is_endless = not isinstance(curve, CareerCourse)
    terrain_cache = {}
    sampler = (lambda d_v, s_v: _fast_endless_floor(curve, d_v, s_v, seed, terrain_cache)) if is_endless else (
        lambda d_v, s_v: floor_point(curve, d_v, s_v, seed)
    )

    for number, (lateral, local, height_scale) in enumerate(((-38, 54, 0.7), (-38, 151, 0.65))):
        distance = index * 200 + local
        p = sampler(lateral, distance)
        if p is None:
            continue
        label = "bank-" + "abc"[(index + number) % 3]
        node = kit["standalone-banks"][label].copyTo(detail_parent(distance))
        node.setPos(p - origin - Vec3(0, 0, 1.2))
        node.setScale(0.85, 1.0, height_scale)
        node.setH((curve.sample(distance).heading if curve else 0) + 90)
        if not _outside_road(node, root, origin, curve):
            node.removeNode()
            yield "rock-clearance"
            continue
        yield "coastal-cliff"

    stones = (
        (-29, 50, "huge", 4.4),
        (-34, 55, "large_b", 3.4),
        (-21, 45, "large_a", 2.0),
        (-30, 58, "huge", 2.6),
        (-22, 56, "small", 1.1),
        (-24, 172, "medium", 4.2),
        (-35, 178, "large_a", 3.2),
        (-18, 165, "large_b", 2.0),
        (-25, 176, "huge", 2.8),
        (-19, 168, "medium", 1.3),
        (22, 151, "large_a", 1.2),
        (27, 161, "small", 0.7),
    )
    for number, (lateral, local, label, height) in enumerate(stones):
        distance = index * 200 + local
        p = sampler(lateral, distance)
        if p is None or p.z < -2:
            continue
        node = kit["standalone-boulders"][label].copyTo(detail_parent(distance))
        scale = height / float(node.getTag("source-height"))
        node.setScale(scale)
        node.setH((index * 71 + (137 if number == 5 else number * 137)) % 360)
        node.setPos(p - origin + Vec3(0, 0, -float(node.getTag("source-base")) * scale - height * 0.23))
        if not _outside_road(node, root, origin, curve):
            node.removeNode()
            continue
        yield "roadside-boulder"

    for local in (48, 146):
        distance = index * 200 + local
        p = sampler(69, distance)
        if p is None or p.z > 0:
            continue
        node = kit["standalone-banks"]["shore"].copyTo(detail_parent(distance))
        node.setPos(p.x - origin.x, p.y - origin.y, -2.4 - origin.z)
        node.setH((curve.sample(distance).heading if curve else 0) + 90)
        yield "coastal-shore"


def _grove_regions(index: int, seed: int):
    start = index * 200
    for cell in range(math.floor((start - 60) / 96), math.ceil((start + 260) / 96)):
        for side, tier in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
            if tier and (cell + side) % 3:
                continue
            group_seed = seed * 971 + cell * 23399 + side * 3581 + tier * 9173
            rng = random.Random(group_seed)
            center_s = cell * 96 + rng.uniform(-12, 12)
            center_d = side * ((47 if side < 0 else 53) + tier * 60 + rng.uniform(-10, 12))
            radius_d, radius_s = rng.uniform(27, 34), rng.uniform(35, 48)
            skew = rng.uniform(-0.28, 0.28)
            yield side, tier, center_d, center_s, radius_d, radius_s, skew, group_seed


def _grove_positions(index: int, seed: int):
    start = index * 200
    for _side, tier, center_d, center_s, radius_d, radius_s, skew, group_seed in _grove_regions(index, seed):
        rng = random.Random(group_seed + 5171)
        for row in range(-4, 5):
            for col in range(-3, 4):
                u = col / 3 + rng.uniform(-0.1, 0.1)
                v = row / 4 + rng.uniform(-0.08, 0.08)
                if u * u + v * v > 1 or rng.random() < (0.18 if tier else 0.08):
                    continue
                d = center_d + radius_d * u + skew * radius_s * v
                s = center_s + radius_s * v
                variant = rng.choices(range(5), (4, 2, 1, 3, 3))[0]
                height = rng.uniform(13, 18) + 1.2 * (1 - u * u - v * v) + tier * 2
                heading, detail_seed = rng.uniform(0, 360), rng.randrange(2**30)
                if start <= s < start + 200:
                    yield d, s, variant, height, heading, detail_seed, u * u + v * v


def _foreground_layout(is_endless: bool):
    # 前排混排活橡(0)、高榆(1)、地中海伞松(2)、暖阳橡(4)，起步即展现丰富海岸林相。
    return (
        (
            (-19.5, 44, 0, 14.0),
            (-20.0, 88, 2, 14.8),
            (-20.0, 120, 1, 15.0),
            (-19.2, 178, 4, 13.0),
            (25, 155, 2, 14.2),
            (33, 164, 0, 13.8),
        )
        if is_endless
        else (
            (-13, 44, 0, 14.0),
            (-14, 88, 2, 14.8),
            (-13, 120, 1, 15.0),
            (-15, 178, 4, 13.0),
            (25, 155, 2, 14.2),
            (33, 164, 0, 13.8),
        )
    )


def _companion_sites(d: float, s: float, variant: int):
    if d < 0:
        return ((d - 10, s - 7, 4, 10.5), (d - 18, s + 12, 3, 11.5))
    return ((d + 18, s + 13, 4, 11.0),) if variant == 0 else ()


def _ridge_sites(index: int, seed: int):
    rng = random.Random(index * 7919 + seed * 971)
    for width in (18, 43, 76, 116, 166):
        for local in range(10, 200, 26):
            s = index * 200 + local + rng.uniform(-5, 5)
            w = width + rng.uniform(-7, 7)
            variant = rng.randrange(3)
            height = rng.uniform(12, 18)
            heading = rng.uniform(0, 360)
            yield width, s, w, variant, height, heading


def _endless_grass_corners(curve, start: int, seed: int):
    from environment import expressway_route

    cols = np.array(_NEG_TERRAIN_COLUMNS + _POS_TERRAIN_COLUMNS, dtype=np.float64)
    rows_s = np.arange(start, start + 201, 5, dtype=np.float64)[:, None]
    p_rows = expressway_route._row_params_2d(rows_s, seed)
    d_mat = np.broadcast_to(cols[None, :], (41, len(cols)))
    if curve is not None:
        cx, cy, cz, rx, ry = expressway_route._curve_cols_2d(curve, start, 41, 0.0)
        gx = cx + d_mat * rx
        gy = cy + d_mat * ry
        gz = cz + expressway_route._height_2d(d_mat, p_rows, cz)
    else:
        gx = d_mat
        gy = np.broadcast_to(rows_s, (41, len(cols)))
        gz = expressway_route._height_2d(d_mat, p_rows, np.zeros((41, 1), dtype=np.float64))

    def eval_grid(d_vals, s_vals):
        d_arr = np.asarray(d_vals, dtype=np.float64)
        s_arr = np.asarray(s_vals, dtype=np.float64)
        neg_count = len(_NEG_TERRAIN_COLUMNS)
        c_idx = np.empty(len(d_arr), dtype=np.intp)
        u = np.empty(len(d_arr), dtype=np.float64)
        for idx, dv in enumerate(d_arr):
            sub = _NEG_TERRAIN_COLUMNS if dv < 0 else _POS_TERRAIN_COLUMNS
            pos = max(0, min(len(sub) - 2, bisect_right(sub, dv) - 1))
            left, right = sub[pos], sub[pos + 1]
            c_idx[idx] = pos if dv < 0 else neg_count + pos
            u[idx] = (dv - left) / (right - left)
        r_idx = np.clip(np.floor((s_arr - start) / 5.0).astype(np.intp), 0, 39)
        v = (s_arr - (start + r_idx * 5.0)) / 5.0
        r0, r1 = r_idx[:, None], r_idx[:, None] + 1
        c0, c1 = c_idx[None, :], c_idx[None, :] + 1
        u2, v2 = u[None, :], v[:, None]
        upper = u2 >= v2
        w_a = np.where(upper, 1.0 - u2, 1.0 - v2)
        w_b = np.where(upper, u2 - v2, 0.0)
        w_c = np.where(upper, v2, u2)
        w_e = np.where(upper, 0.0, v2 - u2)
        px = gx[r0, c0] * w_a + gx[r0, c1] * w_b + gx[r1, c1] * w_c + gx[r1, c0] * w_e
        py = gy[r0, c0] * w_a + gy[r0, c1] * w_b + gy[r1, c1] * w_c + gy[r1, c0] * w_e
        pz = gz[r0, c0] * w_a + gz[r0, c1] * w_b + gz[r1, c1] * w_c + gz[r1, c0] * w_e
        return px, py, pz

    d_corners = list(range(-105, -8, 4)) + list(range(9, 106, 4))
    s_corners = list(range(start, start + 201, 4))
    cx_m, cy_m, cz_m = eval_grid(d_corners, s_corners)
    d_centers = list(range(-103, -10, 4)) + list(range(11, 104, 4))
    s_centers = list(range(start + 2, start + 200, 4))
    _, _, center_z = eval_grid(d_centers, s_centers)
    return cx_m, cy_m, cz_m, {dv: i for i, dv in enumerate(d_corners)}, center_z, {dv: i for i, dv in enumerate(d_centers)}


def foliage_steps(root: NodePath, index: int, seed: int, curve, kit: dict, detail_parent):
    """铺设写实橡树群落、幼橡、灌丛、林下蕨草、4m 实例化草格及远山脊林。"""
    from environment import expressway_route

    origin = Vec3(*expressway_route.anchor(curve, index))
    start = index * 200
    is_endless = not isinstance(curve, CareerCourse)
    coastal = isinstance(curve, CareerCourse) and coast_candidate(curve.course_id)
    rng = random.Random(seed * 971 + index * 23399)
    fern_sites = []
    rock_bounds = [
        node.getTightBounds(root)
        for node in root.findAllMatches("**/+LODNode")
        if node.getName().startswith(("standalone-coastal-bank-", "standalone-boulder-"))
    ]
    terrain_cache = {}

    def sample_floor(d_val: float, s_val: float):
        if is_endless:
            return _fast_endless_floor(curve, d_val, s_val, seed, terrain_cache)
        return floor_point(curve, d_val, s_val, seed)

    def root_clear(point: Vec3, gap: float) -> bool:
        local = point - origin
        return all(
            local.x < low.x - gap or local.x > high.x + gap or local.y < low.y - gap or local.y > high.y + gap
            for low, high in rock_bounds
        )

    def fast_slope(node: NodePath, d_val: float, s_val: float) -> None:
        across = [sample_floor(d_val + off, s_val) for off in (-1, 1)]
        along = [sample_floor(d_val, s_val + off) for off in (-1, 1)]
        if any(pt is None for pt in (*across, *along)):
            return
        normal = (across[1] - across[0]).cross(along[1] - along[0])
        if normal.lengthSquared() < 1e-12:
            return
        normal.normalize()
        x, y = -normal.x / normal.z, -normal.y / normal.z
        ang = math.radians(node.getH())
        sc = node.getScale()
        set_root_slope(
            node,
            (
                (x * math.cos(ang) + y * math.sin(ang)) * sc.x / sc.z,
                (-x * math.sin(ang) + y * math.cos(ang)) * sc.y / sc.z,
            ),
        )

    # 1) 前排主树、伴生树与幼橡
    foreground = _foreground_layout(is_endless)
    for fg_idx, (d, local, variant, height) in enumerate(foreground):
        s = start + local
        if _urban_roadside(curve, d, s, seed):
            continue
        p = sample_floor(d, s)
        if p is None or p.z < -2 or not _valid_verge(curve, p, s, 12) or not root_clear(p, 1.5):
            continue
        tree = kit["standalone-trees"][variant].copyTo(detail_parent(s))
        tree.setPos(p - origin)
        tree.setScale(height / float(tree.getTag("source-height")))
        if variant == 1:
            crown_cap = 7.4 if is_endless else 8.0
            horiz = crown_cap / float(tree.getTag("source-crown-radius"))
            tree.setScale(horiz, horiz, height / float(tree.getTag("source-height")))
        tree.setH(rng.uniform(0, 360))
        fast_slope(tree, d, s)
        if fg_idx % 2 == 1 or fg_idx == len(foreground) - 1:
            yield "driving-view-tree"
        fern_sites.append((d + math.copysign(2.4, d), s - 3.0, variant % 2, 1.45, (index * 47 + s) % 360))
        for cd, cs, family, ch in _companion_sites(d, s, variant):
            behind = sample_floor(cd, cs)
            if behind is None or behind.z < -2 or not root_clear(behind, 1.5) or not _valid_verge(curve, behind, cs, 16):
                continue
            comp = kit["standalone-trees"][family].copyTo(detail_parent(cs))
            comp.setPos(behind - origin)
            comp.setH(rng.uniform(0, 360))
            comp.setScale(ch / float(comp.getTag("source-height")))
            fast_slope(comp, cd, cs)
        for offset in (-6, 6):
            yd = d + (-5 if d < 0 else 5)
            under = sample_floor(yd, s + offset)
            if under is None or not _valid_verge(curve, under, s + offset, 14) or not root_clear(under, 0.7):
                continue
            young = kit["standalone-young-oaks"][rng.randrange(3)].copyTo(detail_parent(s + offset))
            young.setPos(under - origin - Vec3(0, 0, 0.15))
            young.setH(rng.uniform(0, 360))
            young.setScale(rng.uniform(3.0, 4.8) / float(young.getTag("source-height")))
            set_world_lod_range(young, 296.0)
            fast_slope(young, yd, s + offset)
        yield "driving-understory"

    # 2) 林缘灌丛
    understory_placed = 0
    for center, side in ((start + 28, -1), (start + 96, -1), (start + 164, -1), (start + 90, 1)):
        for n in range(4 if side < 0 else 2):
            s = center + rng.uniform(-16, 16)
            d = side * (14 + rng.uniform(0, 17))
            p = sample_floor(d, s)
            if p is None or p.z < -2 or not _valid_verge(curve, p, s, 12) or not root_clear(p, 0.7):
                continue
            node = kit["standalone-shrubs"][n % 3].copyTo(detail_parent(s))
            node.setPos(p - origin - Vec3(0, 0, 0.12))
            node.setH(rng.uniform(0, 360))
            node.setScale(rng.uniform(1.2, 2.2) / float(node.getTag("source-height")))
            set_world_lod_range(node, 242.0)
            fast_slope(node, d, s)
            understory_placed += 1
            if understory_placed % 8 == 0:
                yield "understory-shrubs"
    if understory_placed % 8:
        yield "understory-shrubs"

    # 3) 主岩群周边林冠与低灌
    outcrop_placed = 0
    for center in (start + 50, start + 172):
        back = sample_floor(-42, center + 24)
        if back is not None and back.z >= -2 and _valid_verge(curve, back, center + 24, 18) and root_clear(back, 1.5):
            tree = kit["standalone-trees"][0].copyTo(detail_parent(center + 24))
            tree.setPos(back - origin)
            tree.setScale(12.0 / float(tree.getTag("source-height")))
            tree.setH((index * 47 + center) % 360)
            fast_slope(tree, -42, center + 24)
            yield "outcrop-canopy"
        edge = (
            (-17, -12, 1.5, False),
            (-29, -14, 1.8, False),
            (-39, 1, 3.5, True),
            (-33, 15, 3.8, True),
            (-20, 16, 3.2, True),
            (-16, 3, 1.4, False),
            (-39, -9, 1.7, False),
        )
        for number, (d, offset, height, is_young) in enumerate(edge):
            s = center + offset
            p = sample_floor(d, s)
            if p is None or p.z < -2 or not _valid_verge(curve, p, s, 14) or not root_clear(p, 0.7):
                continue
            plants = kit["standalone-young-oaks" if is_young else "standalone-shrubs"]
            node = plants[number % len(plants)].copyTo(detail_parent(s))
            node.setPos(p - origin - Vec3(0, 0, 0.12))
            node.setH((index * 47 + number * 83) % 360)
            node.setScale(height / float(node.getTag("source-height")))
            set_world_lod_range(node, 296.0 if is_young else 242.0)
            fast_slope(node, d, s)
            outcrop_placed += 1
            if outcrop_placed % 8 == 0:
                yield "outcrop-understory"
    if outcrop_placed % 8:
        yield "outcrop-understory"

    # 4) 成片林冠地块
    grove_trees = grove_under = 0
    for number, (d, s, variant, height, heading, detail_seed, edge) in enumerate(_grove_positions(index, seed)):
        if number % 16 == 0:
            yield "grove-site-checks"
        if _urban_roadside(curve, d, s, seed):
            continue
        if d > 0 and is_endless and s % 320 < 240:
            continue
        if -42 < d < 0 and any(start + loc - 35 < s < start + loc + 5 for loc in (50, 172)):
            continue
        p = sample_floor(d, s)
        if p is None or p.z < -2 or not _valid_verge(curve, p, s, 18) or not root_clear(p, 1.5):
            continue
        template = kit["standalone-trees"][variant]
        if is_endless:
            crown_r = height / float(template.getTag("source-height")) * float(template.getTag("source-crown-radius"))
            if abs(d) - crown_r < 10.5:
                continue
        if coastal and abs(d) > 36:
            from environment.career_coast import _shoreline

            if p.x > _shoreline(p.y) - 30 and (s + seed * 11) % 192 > 64:
                continue
        tree = template.copyTo(detail_parent(s))
        tree.setPos(p - origin)
        tree.setScale(height / float(tree.getTag("source-height")))
        tree.setH(heading)
        fast_slope(tree, d, s)
        grove_trees += 1
        if grove_trees % 8 == 0:
            yield "grove-canopy"
        plants_rng = random.Random(detail_seed)
        if abs(d) > 65:
            continue
        if detail_seed % 5 == 0:
            is_young = edge > 0.55
            if is_young or abs(d) <= 45:
                ud, us = d + plants_rng.uniform(-4, 4), s + plants_rng.uniform(-4, 4)
                under = sample_floor(ud, us)
                if under is not None and _valid_verge(curve, under, us, 18) and root_clear(under, 0.7):
                    plants = kit["standalone-young-oaks" if is_young else "standalone-shrubs"]
                    shrub = plants[plants_rng.randrange(3)].copyTo(detail_parent(us))
                    shrub.setPos(under - origin - Vec3(0, 0, 0.12))
                    shrub.setH(plants_rng.uniform(0, 360))
                    shrub.setScale(
                        (plants_rng.uniform(3.0, 4.8) if is_young else plants_rng.uniform(1.1, 1.9))
                        / float(shrub.getTag("source-height"))
                    )
                    set_world_lod_range(shrub, 296.0 if is_young else 242.0)
                    fast_slope(shrub, ud, us)
                    grove_under += 1
                    if grove_under % 8 == 0:
                        yield "grove-understory"
        if abs(d) > 48 or detail_seed % 6:
            continue
        fern_sites.append((d + 2.5, s + 1.5, plants_rng.randrange(2), plants_rng.uniform(1.1, 1.5), plants_rng.uniform(0, 360)))
    if grove_trees % 8:
        yield "grove-canopy"
    if grove_under % 8:
        yield "grove-understory"

    # 5) 林缘灌丛收边
    grove_edge_count = 0
    for side, tier, center_d, center_s, radius_d, radius_s, skew, group_seed in _grove_regions(index, seed):
        if tier or _urban_roadside(curve, center_d, center_s, seed):
            continue
        edge_rng = random.Random(group_seed + 7321)
        for v in (-0.58, 0.0, 0.58):
            edge_s = center_s + radius_s * v
            edge_d = center_d - side * radius_d * math.sqrt(1 - v * v) + skew * radius_s * v
            for offset in (-3.6, 2.2):
                s = edge_s + offset + edge_rng.uniform(-0.5, 0.5)
                d = edge_d + edge_rng.uniform(-1.7, 1.7)
                if not start <= s < start + 200 or (is_endless and abs(d) < 11.5):
                    continue
                p = sample_floor(d, s)
                if p is None or p.z < -2 or not _valid_verge(curve, p, s, 15) or not root_clear(p, 0.7):
                    continue
                shrub = kit["standalone-shrubs"][edge_rng.randrange(3)].copyTo(detail_parent(s))
                scale = edge_rng.uniform(0.7, 1.45) / float(shrub.getTag("source-height"))
                width = scale * edge_rng.uniform(1.2, 1.6)
                shrub.setScale(width, width, scale)
                set_world_lod_range(shrub, 242.0)
                shrub.setPos(p - origin - Vec3(0, 0, 0.10))
                shrub.setH(edge_rng.uniform(0, 360))
                fast_slope(shrub, d, s)
                grove_edge_count += 1
                if grove_edge_count % 8 == 0:
                    yield "grove-edge"
    if grove_edge_count % 8:
        yield "grove-edge"

    # 6) 林下蕨草
    ferns_placed = 0
    for d, s, variant, scale, heading in fern_sites:
        pt = sample_floor(d, s)
        if pt is None or not _valid_verge(curve, pt, s, 11.5) or not root_clear(pt, 0.2):
            continue
        fern = kit["standalone-ferns"][variant].copyTo(detail_parent(s))
        fern.setPos(pt - origin - Vec3(0, 0, 0.035))
        fern.setScale(scale)
        fern.setH(heading)
        fast_slope(fern, d, s)
        ferns_placed += 1
        if ferns_placed % 8 == 0:
            yield "grove-ferns"
    if ferns_placed % 8:
        yield "grove-ferns"

    # 7) 4m 硬件实例化草格
    grass_floor_cache = {}
    grass_grid = _endless_grass_corners(curve, start, seed) if is_endless else None

    def cached_grass_floor(d_val: float, s_val: float):
        key = (d_val, s_val)
        if key not in grass_floor_cache:
            pt = floor_point(curve, d_val, s_val, seed)
            grass_floor_cache[key] = None if pt is None else (pt.x, pt.y, pt.z)
        return grass_floor_cache[key]

    bands = (
        (-39, -35, -31, -27, -23, -19, -15, -11, 11, 15, 19, 23, 27, 31, 35, 39),
        (-71, -67, -63, -59, -55, -51, -47, -43, 43, 47, 51, 55, 59, 63, 67, 71),
        (-103, -99, -95, -91, -87, -83, -79, -75, 75, 79, 83, 87, 91, 95, 99, 103),
    )
    for cell_start in range(start, start + 200, 20):
        center_s = cell_start + 10
        center = expressway_route.sample(curve, center_s)
        heading = math.radians(curve.sample(center_s).heading) if curve else 0.0
        co, si = math.cos(heading), math.sin(heading)
        cx, cy, cz = center.x, center.y, center.z
        for band, columns in enumerate(bands):
            controls = {name: PTALVecBase3f.emptyArray(80) for name in ("00", "10", "01", "11")}
            c00, c10, c01, c11 = controls["00"], controls["10"], controls["01"], controls["11"]
            max_r2 = 0.0
            count = 0
            if grass_grid is not None:
                gx_m, gy_m, gz_m, d_ci, center_z, d_mi = grass_grid
                for s in range(cell_start + 2, cell_start + 20, 4):
                    s_row = (s - start - 2) // 4
                    r0, r1 = s_row, s_row + 1
                    urban_cutoff = 59 + expressway_route._city_shift(s, seed) if _urban_roadside(curve, 1.0, s, seed) else 1e9
                    for col_i, d in enumerate(columns):
                        if col_i % 16 == 0:
                            yield "grass-site-checks"
                        if d >= urban_cutoff or center_z[s_row, d_mi[d]] < -2.0:
                            continue
                        col0, col1 = d_ci[d - 2], d_ci[d + 2]
                        for arr, rr, cc in ((c00, r0, col0), (c10, r0, col1), (c01, r1, col0), (c11, r1, col1)):
                            dx, dy, dz = float(gx_m[rr, cc]) - cx, float(gy_m[rr, cc]) - cy, float(gz_m[rr, cc]) - cz
                            rx, ry = dx * co + dy * si, -dx * si + dy * co
                            arr[count] = (rx, ry, dz)
                            max_r2 = max(max_r2, rx * rx + ry * ry + dz * dz)
                        count += 1
                        if count % 40 == 0:
                            yield "grass-controls"
            else:
                for s in range(cell_start + 2, cell_start + 20, 4):
                    for col_i, d in enumerate(columns):
                        if col_i % 16 == 0:
                            yield "grass-site-checks"
                        if _urban_roadside(curve, d, s, seed) and d >= 59 + expressway_route._city_shift(s, seed):
                            continue
                        p = cached_grass_floor(d, s)
                        if p is None or p[2] < -2 or not _valid_verge(curve, Vec3(*p), s, 10):
                            continue
                        floors = (
                            cached_grass_floor(d - 2, s - 2),
                            cached_grass_floor(d + 2, s - 2),
                            cached_grass_floor(d - 2, s + 2),
                            cached_grass_floor(d + 2, s + 2),
                        )
                        if any(pt is None for pt in floors) or (coastal and any(pt[2] < -2 for pt in floors)):
                            continue
                        for arr, fl in ((c00, floors[0]), (c10, floors[1]), (c01, floors[2]), (c11, floors[3])):
                            dx, dy, dz = fl[0] - cx, fl[1] - cy, fl[2] - cz
                            rx, ry = dx * co + dy * si, -dx * si + dy * co
                            arr[count] = (rx, ry, dz)
                            max_r2 = max(max_r2, rx * rx + ry * ry + dz * dz)
                        count += 1
                        if count % 40 == 0:
                            yield "grass-controls"
            if count % 40:
                yield "grass-controls"
            if count:
                lod = LODNode("standalone-grass-distance")
                lod.addSwitch(220, 0)
                patch = detail_parent(center_s).attachNewNode(lod)
                patch.setPos(center - origin)
                patch.setH(math.degrees(heading))
                batch = kit["standalone-grass-mid" if band else "standalone-grass"].copyTo(patch)
                batch.setInstanceCount(count)
                batch.node().setBounds(BoundingSphere(Vec3(0, 0, 0), math.sqrt(max_r2) + 3.0))
                batch.node().setFinal(True)
                for name, values in controls.items():
                    batch.setShaderInput("grass_floor" + name, values)
                yield "grass-batch"

    # 8) 无限高速左侧远山脊林
    if is_endless:
        from environment.expressway_mountains import mountain_point

        for count, (width, s, w, variant, height, heading) in enumerate(_ridge_sites(index, seed)):
            p = mountain_point(curve, -1, w, s, seed)
            tree = kit["standalone-trees"][variant].copyTo(detail_parent(s))
            tree.setPos(p - origin)
            tree.setScale(height / float(tree.getTag("source-height")))
            tree.setH(heading)
            across = mountain_point(curve, -1, width + 1, s, seed) - mountain_point(curve, -1, width - 1, s, seed)
            along = mountain_point(curve, -1, width, s + 1, seed) - mountain_point(curve, -1, width, s - 1, seed)
            normal = across.cross(along)
            x, y = -normal.x / normal.z, -normal.y / normal.z
            ang = math.radians(tree.getH())
            set_root_slope(tree, (x * math.cos(ang) + y * math.sin(ang), -x * math.sin(ang) + y * math.cos(ang)))
            if count % 8 == 7 or count == 39:
                yield "forest-ridge"


def _woodland_texture(centers: np.ndarray, radii: np.ndarray, bounds: tuple[float, float, float, float]):
    left, bottom = (math.floor(v / 2) * 2 for v in bounds[:2])
    width = max(1, math.ceil((bounds[2] - left) / 2))
    height = max(1, math.ceil((bounds[3] - bottom) / 2))
    selected = (
        (centers[:, 0] + radii * 4 >= left)
        & (centers[:, 0] - radii * 4 <= left + width * 2)
        & (centers[:, 1] + radii * 4 >= bottom)
        & (centers[:, 1] - radii * 4 <= bottom + height * 2)
    )
    centers, radii = centers[selected], radii[selected]
    if len(centers) == 0:
        tex = Texture("shared-woodland-coverage")
        tex.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRed)
        tex.setRamImage(b"\x00")
        tex.setMinfilter(Texture.FTLinear)
        tex.setMagfilter(Texture.FTLinear)
        tex.setWrapU(Texture.WMClamp)
        tex.setWrapV(Texture.WMClamp)
        return tex, (float(left), float(bottom), 0.5, 0.5)
    pad = radii * 4.0 + 2.0
    t_left = max(left, math.floor(float(np.min(centers[:, 0] - pad)) / 2) * 2)
    t_bottom = max(bottom, math.floor(float(np.min(centers[:, 1] - pad)) / 2) * 2)
    t_right = min(left + width * 2, math.ceil(float(np.max(centers[:, 0] + pad)) / 2) * 2)
    t_top = min(bottom + height * 2, math.ceil(float(np.max(centers[:, 1] + pad)) / 2) * 2)
    left, bottom = t_left, t_bottom
    width, height = max(1, (t_right - left) // 2), max(1, (t_top - bottom) // 2)
    influence = np.zeros((height, width), dtype=np.float32)
    x = left + (np.arange(width, dtype=np.float32) + 0.5) * 2
    y = bottom + (np.arange(height, dtype=np.float32) + 0.5) * 2
    inv_sigma = 1.0 / (radii * np.float32(1.2))
    for st in range(0, len(centers), 32):
        bc = centers[st : st + 32]
        bi = inv_sigma[st : st + 32]
        hor = np.exp(-((x[:, None] - bc[None, :, 0]) * bi[None, :]) ** 2)
        vert = np.exp(-((y[:, None] - bc[None, :, 1]) * bi[None, :]) ** 2)
        influence += (vert @ hor.T) * np.float32(0.8)
        yield "woodland-coverage"
    weight = np.clip((influence - 0.3) / 1.1, 0, 1)
    pixels = np.rint(weight * weight * (3 - 2 * weight) * 255).astype(np.uint8)
    tex = Texture("shared-woodland-coverage")
    tex.setup2dTexture(width, height, Texture.TUnsignedByte, Texture.FRed)
    tex.setRamImage(pixels.tobytes())
    tex.setMinfilter(Texture.FTLinear)
    tex.setMagfilter(Texture.FTLinear)
    tex.setWrapU(Texture.WMClamp)
    tex.setWrapV(Texture.WMClamp)
    return tex, (float(left), float(bottom), 1 / (width * 2), 1 / (height * 2))


def _neighbor_oaks(index: int, seed: int, curve, tree_dims, *, include_current: bool = False):
    from environment import expressway_route
    from highway_segments import segment

    is_endless = not isinstance(curve, CareerCourse)
    coastal = isinstance(curve, CareerCourse) and coast_candidate(curve.course_id)
    margin_min, margin_max = index * 200 - 40, (index + 1) * 200 + 40
    centers, radii = [], []
    terrain_cache = {}

    def sample_floor(d_val: float, s_val: float):
        if is_endless:
            return _fast_endless_floor(curve, d_val, s_val, seed, terrain_cache)
        return floor_point(curve, d_val, s_val, seed)

    for adj in (index - 1, index, index + 1):
        for number, (d, local, scale, _heading) in enumerate(segment(seed, adj).trees):
            s = adj * 200 + local
            if not margin_min <= s <= margin_max:
                continue
            if not is_endless and sample_floor(d, s) is None:
                continue
            p = expressway_route.sample(curve, s, d)
            h_v, r_v = tree_dims[(adj + number) % 2]
            centers.append((p.x, p.y))
            radii.append(scale * (4.5 / h_v) * r_v)

    foreground = _foreground_layout(is_endless)
    for adj in ((index - 1, index, index + 1) if include_current else (index - 1, index + 1)):
        adj_start = adj * 200
        for d, local, variant, height in foreground:
            s = adj_start + local
            if margin_min <= s <= margin_max and not _urban_roadside(curve, d, s, seed):
                p = sample_floor(d, s)
                if p is not None and p.z >= -2 and _valid_verge(curve, p, s, 12):
                    h_v, r_v = tree_dims[variant]
                    r = (7.4 if is_endless else 8.0) if variant == 1 else (height / h_v * r_v)
                    centers.append((p.x, p.y))
                    radii.append(r)
            for cd, cs, family, ch in _companion_sites(d, s, variant):
                if margin_min <= cs <= margin_max:
                    behind = sample_floor(cd, cs)
                    if behind is not None and behind.z >= -2 and _valid_verge(curve, behind, cs, 16):
                        h_v, r_v = tree_dims[family]
                        centers.append((behind.x, behind.y))
                        radii.append(ch / h_v * r_v)
        for center in (adj_start + 50, adj_start + 172):
            s = center + 24
            if margin_min <= s <= margin_max:
                back = sample_floor(-42, s)
                if back is not None and back.z >= -2 and _valid_verge(curve, back, s, 18):
                    h_v, r_v = tree_dims[0]
                    centers.append((back.x, back.y))
                    radii.append(12.0 / h_v * r_v)
        for d, s, variant, height, _h, _ds, _e in _grove_positions(adj, seed):
            if not margin_min <= s <= margin_max or _urban_roadside(curve, d, s, seed):
                continue
            if d > 0 and is_endless and s % 320 < 240:
                continue
            if -42 < d < 0 and any(adj_start + loc - 35 < s < adj_start + loc + 5 for loc in (50, 172)):
                continue
            p = sample_floor(d, s)
            if p is None or p.z < -2 or not _valid_verge(curve, p, s, 18):
                continue
            h_v, r_v = tree_dims[variant]
            r = height / h_v * r_v
            if is_endless and abs(d) - r < 10.5:
                continue
            if coastal and abs(d) > 36:
                from environment.career_coast import _shoreline

                if p.x > _shoreline(p.y) - 30 and (s + seed * 11) % 192 > 64:
                    continue
            centers.append((p.x, p.y))
            radii.append(r)
        if is_endless:
            from environment.expressway_mountains import mountain_point

            for _width, s, w, variant, height, _heading in _ridge_sites(adj, seed):
                if margin_min <= s <= margin_max:
                    p = mountain_point(curve, -1, w, s, seed)
                    h_v, r_v = tree_dims[variant]
                    centers.append((p.x, p.y))
                    radii.append(height / h_v * r_v)
        yield "woodland-coverage"
    return centers, radii


def _course_normal_steps(course_id: str):
    from career_terrain import terrain

    normals = {}
    for vertices, faces in terrain(course_id).values():
        for face_idx, (a, b, c) in enumerate(faces):
            normal = (Vec3(*vertices[b]) - Vec3(*vertices[a])).cross(Vec3(*vertices[c]) - Vec3(*vertices[a]))
            for num in (a, b, c):
                x, y, _z = vertices[num]
                key = round(x / 8), round(y / 8)
                normals[key] = normals.get(key, Vec3(0)) + normal
            if face_idx % 96 == 95:
                yield "course-normals"
    result = {}
    for idx, (key, normal) in enumerate(normals.items()):
        result[key] = tuple(normal.normalized())
        if idx % 128 == 127:
            yield "course-normals"
    return result


def woodland_and_normals_steps(root: NodePath, index: int, curve, seed: int, kit: dict):
    """生成 2m 林冠覆盖场并绑定到地表与实例化草格，同时平滑有限赛道地形法线。"""
    from environment import expressway_route

    if not isinstance(curve, CareerCourse):
        start = index * 200
        enabled = bool(expressway_route.city_weight(start, seed) or expressway_route.city_weight(start + 200, seed))
        root.setShaderInput("city_lawn_phase", (start % 8000 - start % 600 + seed % 5 * 160, float(enabled)))

    trees = [node for node in root.findAllMatches("**/standalone-oak-*") if isinstance(node.node(), LODNode)]
    origin = Vec3(*expressway_route.anchor(curve, index))
    centers_list = [tuple(node.getPos(root) + origin)[:2] for node in trees]
    radii_list = [node.getSx(root) * float(node.getTag("source-crown-radius")) for node in trees]
    yield "woodland-coverage"

    tree_dims = [
        (float(t.getTag("source-height")), float(t.getTag("source-crown-radius"))) for t in kit["standalone-trees"]
    ]
    extra_c, extra_r = yield from _neighbor_oaks(index, seed, curve, tree_dims, include_current=not trees)
    centers_list.extend(extra_c)
    radii_list.extend(extra_r)
    centers = np.array(centers_list, dtype=np.float32).reshape(-1, 2)
    radii = np.array(radii_list, dtype=np.float32)

    low_x = low_y = math.inf
    high_x = high_y = -math.inf
    for child in root.getChildren():
        if child.getName() not in ("course-landscape", "route-landscape"):
            continue
        tight = child.getTightBounds(root)
        if tight is None:
            continue
        n_low, n_high = tight
        low_x, low_y = min(low_x, n_low.x + origin.x), min(low_y, n_low.y + origin.y)
        high_x, high_y = max(high_x, n_high.x + origin.x), max(high_y, n_high.y + origin.y)
    if low_x > high_x:
        vol = root.getBounds()
        lo, hi = vol.getMin(), vol.getMax()
        bounds = (lo.x + origin.x - 4.0, lo.y + origin.y - 4.0, hi.x + origin.x + 4.0, hi.y + origin.y + 4.0)
    else:
        bounds = (low_x - 4.0, low_y - 4.0, high_x + 4.0, high_y + 4.0)

    tex, coords = yield from _woodland_texture(centers, radii, bounds)
    root.setPythonTag("woodland-coverage", (tex, coords))
    for child in root.getChildren():
        if child.getName() in ("course-landscape", "route-landscape", "standalone-stream-grass"):
            child.setShaderInput("local_forest_coverage", tex)
            child.setShaderInput("local_forest_bounds", coords)
    details = root.find("**/expressway-detail-distance")
    grass_scope = root if details.isEmpty() else details
    for node in grass_scope.findAllMatches("**/standalone-stream-grass"):
        node.setShaderInput("local_forest_coverage", tex)
        node.setShaderInput("local_forest_bounds", coords)
    yield "woodland-coverage"

    if isinstance(curve, CareerCourse) and not coast_candidate(curve.course_id):
        from career_terrain import terrain

        if index in terrain(curve.course_id):
            if curve.course_id not in _COURSE_NORMALS_CACHE:
                _COURSE_NORMALS_CACHE[curve.course_id] = yield from _course_normal_steps(curve.course_id)
            smooth_normals = _COURSE_NORMALS_CACHE[curve.course_id]
            for node in root.findAllMatches("**/+GeomNode"):
                if node.getName() != "course-landscape" or node.hasTag("smoothed-ground"):
                    continue
                for num in range(node.node().getNumGeoms()):
                    data = node.node().modifyGeom(num).modifyVertexData()
                    pos_r = GeomVertexReader(data, "vertex")
                    nrm_w = GeomVertexWriter(data, "normal")
                    for row in range(data.getNumRows()):
                        pt = pos_r.getData3f()
                        key = round((pt.x + origin.x) / 8), round((pt.y + origin.y) / 8)
                        nrm_w.setData3f(*smooth_normals[key])
                        if row % 120 == 119:
                            yield "course-normals"
                node.setTag("smoothed-ground", "1")


def ground_collision_trees(root: NodePath, index: int, seed: int, curve, origin: Vec3, terrain_cache: dict) -> None:
    """将碰撞树显示模型对齐真实地形与坡度，超出有限赛道地形边界时隐藏。"""
    is_endless = not isinstance(curve, CareerCourse)
    details = root.find("**/expressway-detail-distance")
    scope = root if details.isEmpty() else details
    for node in scope.findAllMatches("**/collision-tree-*"):
        if node.hasTag("root-grounded"):
            continue
        p = node.getPos(root) + origin
        s, d = curve.project(tuple(p)) if curve else (p.y, p.x)
        fl = _fast_endless_floor(curve, d, s, seed, terrain_cache) if is_endless else floor_point(curve, d, s, seed)
        if fl is None:
            node.hide()
        else:
            node.setZ(fl.z - origin.z + 0.05 * node.getSz())
            across = [
                _fast_endless_floor(curve, d + off, s, seed, terrain_cache) if is_endless else floor_point(curve, d + off, s, seed)
                for off in (-1, 1)
            ]
            along = [
                _fast_endless_floor(curve, d, s + off, seed, terrain_cache) if is_endless else floor_point(curve, d, s + off, seed)
                for off in (-1, 1)
            ]
            if not any(pt is None for pt in (*across, *along)):
                normal = (across[1] - across[0]).cross(along[1] - along[0])
                if normal.lengthSquared() > 1e-12:
                    normal.normalize()
                    x, y = -normal.x / normal.z, -normal.y / normal.z
                    ang = math.radians(node.getH())
                    sc = node.getScale()
                    set_root_slope(
                        node,
                        (
                            (x * math.cos(ang) + y * math.sin(ang)) * sc.x / sc.z,
                            (-x * math.sin(ang) + y * math.cos(ang)) * sc.y / sc.z,
                        ),
                    )
        node.setTag("root-grounded", "1")


def optimize_city_steps(root: NodePath, kit: dict):
    """合批城市静态表面并优化城内灌木/乔木的阴影掩码与 LOD 范围。"""
    from environment.surface_mesh import flatten_steps

    lamp_name = kit["lamp"].getName()
    for group in root.findAllMatches("**/mainland-city"):
        batches = [group.attachNewNode("city-static-surfaces")]
        batches.extend(group.attachNewNode(f"city-static-surfaces-garden-{n}") for n in range(4))
        for child in tuple(group.getChildren()):
            if isinstance(child.node(), GeomNode) or child.getName() == lamp_name:
                child.wrtReparentTo(batches[0])
            elif child.getName() in ("city-garden", "city-foundation"):
                batch = batches[1 + int(child.getTag("city-lot")) % 4]
                for part in tuple(child.getChildren()):
                    if isinstance(part.node(), GeomNode):
                        part.wrtReparentTo(batch)
            yield "city-static-collect"
        for batch in batches:
            batch.clearModelNodes()
            yield from flatten_steps(batch)
        yield "city-static-complete"

        loose_shrubs = []
        for child in tuple(group.getChildren()):
            if child.hasTag("city-courtyard-shrub") or child.hasTag("city-greenbelt-shrub"):
                child.hide(SHADOW_MASK)
                set_world_lod_range(child, 242.0)
                loose_shrubs.append(child)
            elif child.hasTag("city-tree") or child.hasTag("city-courtyard-tree"):
                child.hide(SHADOW_MASK)
            elif child.getName() == "city-garden":
                for sub in tuple(child.getChildren()):
                    if sub.hasTag("city-garden-tree"):
                        sub.hide(SHADOW_MASK)
                    elif sub.getName() == "garden-plants-distance":
                        shrub_nodes = list(sub.findAllMatches("**/standalone-shrub-*"))
                        positions = [sn.getPos(sub) for sn in shrub_nodes]
                        center = sum(positions, Vec3(0)) / len(positions) if positions else sub.node().getCenter()
                        lod = LODNode("garden-plants-distance")
                        lod.setCenter(center)
                        lod.addSwitch(242.0, 0.0)
                        replacement = child.attachNewNode(lod)
                        replacement.setTransform(sub.getTransform())
                        replacement.hide(SHADOW_MASK)
                        for grand in tuple(sub.getChildren()):
                            grand.reparentTo(replacement)
                        sub.removeNode()
                        for shrub in shrub_nodes:
                            if isinstance(shrub.node(), LODNode):
                                set_world_lod_range(shrub, 242.0)
        if loose_shrubs:
            buckets = defaultdict(list)
            for shrub in loose_shrubs:
                buckets[int(shrub.getPos(group).y // 50)].append(shrub)
            for key, items in sorted(buckets.items()):
                center = sum((it.getPos(group) for it in items), Vec3(0)) / len(items)
                radius = max((it.getPos(group) - center).length() for it in items)
                lod = LODNode(f"city-shrubs-distance-{key}")
                lod.setCenter(center)
                lod.addSwitch(242.0 + radius, 0.0)
                holder = group.attachNewNode(lod)
                for it in items:
                    it.wrtReparentTo(holder)
        yield "city-foliage-optimize"


@lru_cache(maxsize=1)
def _batch_vertex_format():
    fmt = GeomVertexFormat(_packed_v3n3c4t2())
    extra = GeomVertexArrayFormat()
    extra.addColumn(InternalName.make("tree_center"), 3, Geom.NTFloat32, Geom.COther)
    fmt.addArray(extra)
    return GeomVertexFormat.registerFormat(fmt)


def _baked_far_part(tree: NodePath, part: NodePath, root: NodePath, cache: dict):
    geom = part.node().getGeom(0)
    data = geom.getVertexData()
    prim = geom.getPrimitive(0)
    # 必须使用底层 C++ 指针地址，避免 Python 临时包装对象回收后 id() 复用导致跨树种串缓存。
    key = (int(data.this), int(prim.this))
    cached = cache.get(key)
    if cached is None:
        base_packed = _read_packed_v3n3c4t2(data)
        base_points = base_packed["p"].copy()
        base_normals = base_packed["n"].copy()
        base_indices = np.frombuffer(prim.getVertices().getHandle().getData(), dtype="<u4").copy()
        stages = part.findAllTextureStages()
        stage = stages[0] if stages.getNumTextureStages() > 0 else None
        anchor_in = part.getShaderInput("root_anchor")
        anchor_val = anchor_in.getVector().x if anchor_in.getValueType() != anchor_in.MInvalid else 0.0
        cached = (base_packed, base_points, base_normals, base_indices, stage, anchor_val)
        cache[key] = cached
    else:
        base_packed, base_points, base_normals, base_indices, stage, anchor_val = cached

    packed = base_packed.copy()
    slope_x = slope_y = 0.0
    if stage is not None:
        tex_attrib = tree.getAttrib(TexMatrixAttrib) or part.getAttrib(TexMatrixAttrib)
        if tex_attrib is not None and tex_attrib.hasStage(stage):
            tmat = tex_attrib.getTransform(stage).getMat()
            slope_x, slope_y = tmat.getCell(2, 0), tmat.getCell(2, 1)
    if slope_x != 0.0 or slope_y != 0.0:
        pts = base_points.copy()
        t = np.clip((pts[:, 2] + anchor_val) / 2.0, 0.0, 1.0)
        pts[:, 2] += (1.0 - t * t * (3.0 - 2.0 * t)) * (pts[:, 0] * slope_x + pts[:, 1] * slope_y)
    else:
        pts = base_points

    tree_mat = tree.getMat(root)
    matrix = part.getMat(tree) * tree_mat
    m3 = np.array((tuple(matrix.getRow3(0)), tuple(matrix.getRow3(1)), tuple(matrix.getRow3(2))), dtype=np.float32)
    trans = np.array(matrix.getRow3(3), dtype=np.float32)
    packed["p"] = pts @ m3 + trans
    sc = tree.getScale()
    if abs(sc.x - sc.y) < 1e-4 and abs(sc.x - sc.z) < 1e-4 and sc.x > 1e-6:
        packed["n"] = base_normals @ (m3 / np.float32(sc.x))
    else:
        inv_t = matrix.getUpper3()
        inv_t.invertInPlace()
        inv_t.transposeInPlace()
        n3 = np.array((tuple(inv_t.getRow(0)), tuple(inv_t.getRow(1)), tuple(inv_t.getRow(2))), dtype=np.float32)
        nrm = base_normals @ n3
        nlen = np.linalg.norm(nrm, axis=1, keepdims=True)
        packed["n"] = nrm / np.where(nlen > 1e-6, nlen, 1.0)
    center = np.array(tree_mat.xformPoint(tree.node().getCenter()), dtype=np.float32)
    return packed, np.broadcast_to(center, (len(packed), 3)), base_indices


def _make_far_batch(root: NodePath, name: str, meshes: list, state, shader: Shader) -> NodePath:
    data = GeomVertexData(name, _batch_vertex_format(), Geom.UHStatic)
    total_v = sum(len(row[0]) for row in meshes)
    total_i = sum(len(row[2]) for row in meshes)
    vertices = np.empty(total_v, dtype=SOURCE_DTYPE)
    centers = np.empty((total_v, 3), dtype=np.float32)
    use_u16 = total_v <= 65535
    idx_dtype = "<u2" if use_u16 else "<u4"
    indices = np.empty(total_i, dtype=idx_dtype)
    v_pos = i_pos = 0
    for packed, c_arr, idx in meshes:
        vl, il = len(packed), len(idx)
        vertices[v_pos : v_pos + vl] = packed
        centers[v_pos : v_pos + vl] = c_arr
        indices[i_pos : i_pos + il] = idx.astype(idx_dtype) + v_pos if use_u16 else idx + np.uint32(v_pos)
        v_pos += vl
        i_pos += il
    data.setNumRows(total_v)
    data.modifyArray(0).modifyHandle().setData(vertices.tobytes())
    data.modifyArray(1).modifyHandle().setData(centers.tobytes())
    tris = GeomTriangles(Geom.UHStatic)
    tris.setIndexType(Geom.NTUint16 if use_u16 else Geom.NTUint32)
    tris.modifyVertices().modifyHandle().setData(indices.tobytes())
    geom = Geom(data)
    geom.addPrimitive(tris)
    node = GeomNode(name)
    node.addGeom(geom)
    path = root.attachNewNode(node)
    path.setState(state.removeAttrib(TexMatrixAttrib.getClassType()))
    path.setShader(shader, 2)
    path.hide(SHADOW_MASK)
    return path


def tree_batch_steps(root: NodePath, kit: dict):
    """按 40m 单元拆分近树 LOD1 与合批远树 LOD2（树干与树叶分两批合批），原树锁定 LOD2 作 4K 阴影代理。"""
    near_shader, far_shader = kit["standalone-tree-batch-shaders"]
    groups = defaultdict(list)
    details = root.find("**/expressway-detail-distance")
    if not details.isEmpty() and details.getNumChildren() > 0:
        for cell in details.getChild(0).getChildren():
            name = cell.getName()
            if name.startswith("detail-cell-"):
                bucket = groups[int(name.split("-")[-1]) // 2]
                for child in cell.getChildren():
                    if child.getName().startswith("standalone-oak-"):
                        bucket.append(child)
                    elif child.getName().startswith("collision-tree-"):
                        sub = child.find("standalone-oak-*")
                        if not sub.isEmpty():
                            bucket.append(sub)
    city = root.find("**/mainland-city")
    if not city.isEmpty():
        city_trees = [t for t in city.findAllMatches("**/standalone-oak-*") if isinstance(t.node(), LODNode)]
        if city_trees:
            groups["city"] = city_trees

    groups = {
        key: [
            t
            for t in items
            if isinstance(t.node(), LODNode) and not t.isHidden() and not t.getParent().isHidden()
        ]
        for key, items in groups.items()
    }
    mesh_cache = kit.setdefault("_standalone-far-mesh-cache", {})
    for cell, trees in sorted(groups.items(), key=lambda item: (isinstance(item[0], str), item[0])):
        if not trees:
            continue
        single_chunk = len(trees) <= FAR_BATCH_CHUNK
        for chunk_idx, start in enumerate(range(0, len(trees), FAR_BATCH_CHUNK)):
            chunk = trees[start : start + FAR_BATCH_CHUNK]
            lod = LODNode("standalone-near-tree-distance")
            near_group = root.attachNewNode(lod).attachNewNode("standalone-near-trees")
            near_group.setShader(near_shader, 2)
            near_group.hide(SHADOW_MASK)
            bark_meshes, leaf_meshes, centers = [], [], []
            bark_state = leaf_state = None
            for idx, tree in enumerate(chunk):
                lod2_root = tree.getChild(2)
                bark_part = lod2_root.find("**/bark")
                leaf_part = lod2_root.find("**/leaves")
                if not bark_part.isEmpty():
                    if bark_state is None:
                        bark_state = bark_part.getState(root)
                    bark_meshes.append(_baked_far_part(tree, bark_part, root, mesh_cache))
                if not leaf_part.isEmpty():
                    if leaf_state is None:
                        leaf_state = leaf_part.getState(root)
                    leaf_meshes.append(_baked_far_part(tree, leaf_part, root, mesh_cache))
                    centers.append(leaf_meshes[-1][1][0])
                near = near_group.attachNewNode("near-" + tree.getName())
                near.setTransform(tree.getTransform(root))
                near.setState(tree.getState())
                tree_center = tree.node().getCenter()
                near_copy = tree.getChild(1).copyTo(near)
                for gp in near_copy.findAllMatches("**/+GeomNode"):
                    gp.setShaderInput("tree_center", tree_center - gp.getPos(near))
                tree.node().forceSwitch(2)
                tree.hide(BitMask32.lowerOn(31) & ~SHADOW_MASK)
                if (idx + 1) % 2 == 0 or idx == len(chunk) - 1:
                    yield "far-tree-bake"
            center = np.mean(centers, axis=0)
            max_r = max(float(np.linalg.norm(p - center)) for p in centers)
            lod.setCenter(Vec3(*center))
            lod.addSwitch(285.0 + max_r, 0.0)
            suffix = str(cell) if single_chunk else f"{cell}-{chunk_idx}"
            if bark_meshes and bark_state is not None:
                _make_far_batch(root, f"standalone-far-bark-{suffix}", bark_meshes, bark_state, far_shader)
            if leaf_meshes and leaf_state is not None:
                _make_far_batch(root, f"standalone-far-leaves-{suffix}", leaf_meshes, leaf_state, far_shader)
            yield "far-tree-batch"
