"""本机KCD2草木试驾入口；只替换表现函数，资源留在ignored logs。"""

import argparse
import json
import math
import random
import sys
import traceback
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAYLIGHT = ROOT / 'logs/visual-upgrade-20261024/daylight-29'
CANOPY_VISIBILITY = ROOT / 'logs/local-kcd-canopy-visibility'
sys.path.insert(0, str(ROOT / 'src'))

from city_static_candidate import batch_static_steps as city_static_batch_steps
from kcd_local_assets import (
    load_ferns,
    load_local,
    load_sandstone,
    load_shrubs,
    load_young_oaks,
    model,
)
from kcd_tree_batches import batch_steps as tree_batch_steps
from kcd_tree_batches import shaders as tree_batch_shaders
from panda3d.core import (
    AlphaTestAttrib,
    BitMask32,
    BoundingSphere,
    FadeLODNode,
    GeomVertexReader,
    GeomVertexWriter,
    LODNode,
    Mat4,
    PTALVecBase3f,
    Shader,
    ShaderAttrib,
    Texture,
    TransformState,
    TransparencyAttrib,
    Vec3,
)

from career_courses import CareerCourse
from environment import expressway, expressway_route
from environment.career_coast import _enabled as coast_candidate
from environment.expressway_vegetation import TERRAIN_COLUMNS, ground_point

SHADOW_MASK = BitMask32.bit(28)


@lru_cache(maxsize=3)
def course_grid(course_id):
    from career_terrain import terrain

    return {(round(x / 8), round(y / 8)): z for vertices, _faces in terrain(course_id).values()
            for x, y, z in vertices}


def grass_heightfield(course_id):
    """有限赛道草根读取对应表现地形；默认仍为原8米网格。"""
    return _grass_heightfield(course_id, coast_candidate(course_id))


@lru_cache(maxsize=4)
def _grass_heightfield(course_id, coastal):
    import numpy as np

    if coastal:
        from environment.career_coast import _data

        data = _data(course_id)
        pixels = np.nan_to_num(data['heights'], nan=0.)
        texture = Texture('coastal-course-grass-floor')
        texture.setup2dTexture(pixels.shape[1], pixels.shape[0], Texture.TFloat, Texture.FR32)
        texture.setRamImage(pixels.tobytes())
        texture.setMinfilter(Texture.FTNearest)
        texture.setMagfilter(Texture.FTNearest)
        return texture, tuple(map(float, data['grid_origin'])), 1.
    grid = course_grid(course_id) if course_id is not None else {(0, 0): 0.}
    left, bottom = min(key[0] for key in grid), min(key[1] for key in grid)
    width, height = max(key[0] for key in grid) - left + 1, max(key[1] for key in grid) - bottom + 1
    pixels = np.zeros((height, width), dtype=np.float32)
    for (col, row), z in grid.items():
        pixels[row - bottom, col - left] = z
    texture = Texture('original-grass-floor-' + str(course_id))
    texture.setup2dTexture(width, height, Texture.TFloat, Texture.FR32)
    texture.setRamImage(pixels.tobytes())
    texture.setMinfilter(Texture.FTNearest)
    texture.setMagfilter(Texture.FTNearest)
    return texture, (float(left * 8), float(bottom * 8)), float(course_id is not None)


def woodland_texture(centers, radii, bounds):
    """世界对齐的2m林冠覆盖；逐冠计算，纹理完成后才交给渲染线程。"""
    import numpy as np

    left, bottom = (math.floor(value / 2) * 2 for value in bounds[:2])
    width = max(1, math.ceil((bounds[2] - left) / 2))
    height = max(1, math.ceil((bounds[3] - bottom) / 2))
    selected = ((centers[:, 0] + radii * 4 >= left) & (centers[:, 0] - radii * 4 <= left + width * 2)
                & (centers[:, 1] + radii * 4 >= bottom) & (centers[:, 1] - radii * 4 <= bottom + height * 2))
    centers, radii = centers[selected], radii[selected]
    if len(centers) == 0:
        texture = Texture('shared-woodland-coverage')
        texture.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRed)
        texture.setRamImage(b'\x00')
        texture.setMinfilter(Texture.FTLinear)
        texture.setMagfilter(Texture.FTLinear)
        texture.setWrapU(Texture.WMClamp)
        texture.setWrapV(Texture.WMClamp)
        return texture, (float(left), float(bottom), 1 / 2, 1 / 2)
    # 覆盖场着色器对越界 UV 恒返回 0；裁剪到实际树冠影响盒加 2m 零边可保持逐像素等价。
    pad = radii * 4.0 + 2.0
    t_left = max(left, math.floor(float(np.min(centers[:, 0] - pad)) / 2) * 2)
    t_bottom = max(bottom, math.floor(float(np.min(centers[:, 1] - pad)) / 2) * 2)
    t_right = min(left + width * 2, math.ceil(float(np.max(centers[:, 0] + pad)) / 2) * 2)
    t_top = min(bottom + height * 2, math.ceil(float(np.max(centers[:, 1] + pad)) / 2) * 2)
    left, bottom = t_left, t_bottom
    width = max(1, (t_right - left) // 2)
    height = max(1, (t_top - bottom) // 2)
    influence = np.zeros((height, width), dtype=np.float32)
    x = left + (np.arange(width, dtype=np.float32) + .5) * 2
    y = bottom + (np.arange(height, dtype=np.float32) + .5) * 2
    # 高斯可分离，逐冠只写有效局部；不创建整图像素×全部树的大数组。
    for number, (center, radius) in enumerate(zip(centers, radii, strict=True)):
        x0 = max(0, math.floor((float(center[0] - radius * 4) - left) / 2))
        x1 = min(width, math.ceil((float(center[0] + radius * 4) - left) / 2))
        y0 = max(0, math.floor((float(center[1] - radius * 4) - bottom) / 2))
        y1 = min(height, math.ceil((float(center[1] + radius * 4) - bottom) / 2))
        horizontal = np.exp(-((x[x0:x1] - center[0]) / (radius * 1.2)) ** 2)
        vertical = np.exp(-((y[y0:y1] - center[1]) / (radius * 1.2)) ** 2)
        influence[y0:y1, x0:x1] += vertical[:, None] * horizontal[None, :] * .8
        if number % 8 == 7:
            yield 'local-woodland-coverage'
    weight = np.clip((influence - .3) / 1.1, 0, 1)
    pixels = np.rint(weight * weight * (3 - 2 * weight) * 255).astype(np.uint8)
    texture = Texture('shared-woodland-coverage')
    texture.setup2dTexture(width, height, Texture.TUnsignedByte, Texture.FRed)
    texture.setRamImage(pixels.tobytes())
    texture.setMinfilter(Texture.FTLinear)
    texture.setMagfilter(Texture.FTLinear)
    texture.setWrapU(Texture.WMClamp)
    texture.setWrapV(Texture.WMClamp)
    return texture, (float(left), float(bottom), 1 / (width * 2), 1 / (height * 2))


def apply_woodland_inputs(root, texture, bounds):
    """覆盖场只交给读取它的地表与草，避免每段纹理切换传播到全部树木。"""
    root.setPythonTag('woodland-coverage', (texture, bounds))
    for node in root.findAllMatches('**/+GeomNode'):
        if node.getName() in ('course-landscape', 'route-landscape', 'kcd-stream-grass'):
            node.setShaderInput('local_forest_coverage', texture)
            node.setShaderInput('local_forest_bounds', bounds)


def course_normal_steps(course_id):
    """按原顺序累计原地形面法线；分小批交还预算，完成后才发布结果。"""
    from career_terrain import terrain

    normals = {}
    for vertices, faces in terrain(course_id).values():
        for face_index, (a, b, c) in enumerate(faces):
            normal = (Vec3(*vertices[b]) - Vec3(*vertices[a])).cross(Vec3(*vertices[c]) - Vec3(*vertices[a]))
            for number in (a, b, c):
                x, y, _z = vertices[number]
                key = round(x / 8), round(y / 8)
                normals[key] = normals.get(key, Vec3(0)) + normal
            if face_index % 96 == 95:
                yield 'local-kcd-normal-accumulation'
    result = {}
    for index, (key, normal) in enumerate(normals.items()):
        result[key] = tuple(normal.normalized())
        if index % 128 == 127:
            yield 'local-kcd-normal-normalization'
    return result


def floor_point(curve, d, s, seed):
    if not isinstance(curve, CareerCourse):
        # 无限道路的5m条带只覆盖这些横向列，外侧山体另有采样；不能越界向条带请求插值。
        if not TERRAIN_COLUMNS[0] <= abs(d) <= TERRAIN_COLUMNS[-1]:
            return None
        return ground_point(curve, d, s, seed)
    pose = curve.sample(s, d)
    if coast_candidate(curve.course_id):
        from environment.career_coast import _height

        z = _height(curve.course_id, pose.x, pose.y)
        return None if z is None else Vec3(pose.x, pose.y, z)
    grid = course_grid(curve.course_id)
    col, row = math.floor(pose.x / 8), math.floor(pose.y / 8)
    u, v = pose.x / 8 - col, pose.y / 8 - row
    keys = ((col, row), (col + 1, row), (col + 1, row + 1), (col, row + 1))
    # 有限赛道的预载窗口会越出已生成地形；该处无可种植表面。
    if not all(key in grid for key in keys):
        return None
    a, b, c, e = (grid[key] for key in keys)
    z = a * (1 - u) + b * (u - v) + c * v if u >= v else a * (1 - v) + c * u + e * (v - u)
    return Vec3(pose.x, pose.y, z)


def grass_shader(foliage, *, cull_absent=True, smooth_distance=True, coastal=False):
    from kcd_local_environment import MEADOW_COLOR

    vertex = foliage.getText(Shader.STVertex)
    vertex = vertex.replace('void main() {', MEADOW_COLOR + '''
uniform vec3 grass_floor00[80];
uniform vec3 grass_floor10[80];
uniform vec3 grass_floor01[80];
uniform vec3 grass_floor11[80];
uniform vec3 camera_world_position;
uniform sampler2D grass_heightfield;
uniform vec2 grass_grid_origin;
uniform float grass_surface_mode;
out float grass_height;
flat out float grass_growth;
flat out float grass_present;
flat out float grass_fade;
void main() {''')
    vertex = vertex.replace('vec4 model_position = p3d_Vertex;', '''
grass_height = p3d_Vertex.z;
vec2 cell_uv = (p3d_Vertex.xy + vec2(2.0)) / 4.0;
vec3 floor_position = mix(mix(grass_floor00[gl_InstanceID], grass_floor10[gl_InstanceID], cell_uv.x),
                          mix(grass_floor01[gl_InstanceID], grass_floor11[gl_InstanceID], cell_uv.x), cell_uv.y);
vec2 plant_uv = p3d_Color.rg;
vec3 plant_floor = mix(mix(grass_floor00[gl_InstanceID], grass_floor10[gl_InstanceID], plant_uv.x),
                       mix(grass_floor01[gl_InstanceID], grass_floor11[gl_InstanceID], plant_uv.x), plant_uv.y);
vec3 plant_world = (p3d_ModelMatrix*vec4(plant_floor,1.)).xyz;
float woodland = woodland_cover(plant_world.xy);
grass_growth = meadow_growth(plant_world.xy);
float grass_vertical_scale = mix(.3,1.35,grass_growth)*mix(1.,.55,smoothstep(.25,.9,woodland));
float dry = meadow_patch(plant_world.xy);
grass_height *= mix(.8,1.2,dry)*grass_vertical_scale;
float family_weight = mix(1.-dry,dry,p3d_Color.b);
float distance_weight = 1.-smoothstep(140.,190.,length(plant_world-camera_world_position));
float woodland_density = mix(1.,.12,smoothstep(.35,.9,woodland));
vec2 cell_world = (p3d_ModelMatrix*vec4(grass_floor00[gl_InstanceID],1.)).xy + vec2(0.,local_origin_y);
float cell_seed = dot(floor(cell_world+vec2(.13)),vec2(127.1,311.7));
float plant_seed = fract(sin(cell_seed+p3d_Color.a*73.13)*43758.5453);
grass_present = step(plant_seed,family_weight*distance_weight*woodland_density);
vec4 model_position = vec4(floor_position + vec3(0.0, 0.0, p3d_Vertex.z*mix(.8,1.2,dry)*grass_vertical_scale), 1.0);''')
    present = 'grass_present = step(plant_seed,family_weight*distance_weight*woodland_density);'
    if smooth_distance:
        # 世界中的株位/高度不随相机增生；距离只调原4x MSAA覆盖率，最终在草格卸载前归零。
        vertex = vertex.replace('float distance_weight = 1.-smoothstep(140.,190.,length(plant_world-camera_world_position));',
                                'float distance_weight = 1.-smoothstep(140.,215.,length(plant_world-camera_world_position));')
        replacement = 'grass_present = step(plant_seed,family_weight*woodland_density)*step(.0001,distance_weight);'
        vertex = vertex.replace(present, replacement)
        present = replacement
        vertex = vertex.replace(present, 'grass_fade = distance_weight;\n'+present)
    else:
        vertex = vertex.replace(present, 'grass_fade = 1.;\n'+present)
    if cull_absent:
        growth = '''grass_growth = meadow_growth(plant_world.xy);
float grass_vertical_scale = mix(.3,1.35,grass_growth)*mix(1.,.55,smoothstep(.25,.9,woodland));'''
        height = 'grass_height *= mix(.8,1.2,dry)*grass_vertical_scale;'
        vertex = vertex.replace(growth, '').replace(height, '')
        # 原三角形各顶点的株根/品系/种子相同，此处是整株判定；后面的高度边界仍逐顶点处理。
        vertex = vertex.replace(present, present + '''
if (grass_present < .5) {
    gl_Position = vec4(2.,2.,2.,1.);
    return;
}
''' + growth + '\n' + height)
    # 高度变化后同步校正几何法线；同株的生长值只取根部，不能让叶片各顶点各自缩放。
    vertex = vertex.replace('vec3 model_normal = p3d_Normal;',
        'vec3 model_normal = normalize(vec3(p3d_Normal.xy,p3d_Normal.z/(mix(.8,1.2,dry)*grass_vertical_scale)));')
    # 草格只有绕Z旋转和平移；在世界坐标修正根部高度，原三角面的对角线与地面完全一致。
    vertex = vertex.replace('vec4 view_position = p3d_ModelViewMatrix * model_position;', '''
if (grass_surface_mode > .5) {
    vec3 world_floor = (p3d_ModelMatrix*vec4(floor_position,1.)).xyz;
    vec2 grid = (world_floor.xy+vec2(0.,local_origin_y)-grass_grid_origin)/8.;
    ivec2 cell = ivec2(floor(grid));
    vec2 part = fract(grid);
    if (any(lessThan(cell,ivec2(0))) || any(greaterThanEqual(cell,textureSize(grass_heightfield,0)-1))) {
        grass_present = 0.;
    } else {
        float a = texelFetch(grass_heightfield,cell,0).r;
        float b = texelFetch(grass_heightfield,cell+ivec2(1,0),0).r;
        float c = texelFetch(grass_heightfield,cell+ivec2(1,1),0).r;
        float d = texelFetch(grass_heightfield,cell+ivec2(0,1),0).r;
        float z = part.x >= part.y ? a*(1.-part.x)+b*(part.x-part.y)+c*part.y
                                  : a*(1.-part.y)+c*part.x+d*(part.y-part.x);
        model_position.z += z-world_floor.z;
    }
}
vec4 view_position = p3d_ModelViewMatrix * model_position;''')
    # 草格的顶点色仅保存逐簇坐标/品种/种子，不作为叶片底色或透明度。
    vertex = vertex.replace('v_color = p3d_Color;', 'v_color = vec4(1.);')
    # 该项仅用于木本叶片；草直接编译掉，避免强度为0时仍携带额外SH分支。
    fragment = foliage.getText(Shader.STFragment).replace(
        'uniform float local_sky_transmission;', 'const float local_sky_transmission=0.;').replace(
        'void main() {', 'uniform mat4 p3d_ViewMatrix;\nin float grass_height;\n'
                        'flat in float grass_present;\nflat in float grass_growth;\nflat in float grass_fade;\n'
                        + MEADOW_COLOR + '\nvoid main() {')
    fragment = fragment.replace('float foliage_visibility = 1.;', 'float foliage_visibility = grass_fade;')
    fragment = fragment.replace(
        'if (base_color.a < foliage_alpha_cutoff) discard;', '''
float grass_distance = length(v_world_position - camera_world_position);
if (grass_present < .5) discard;
base_color.rgb = mix(base_color.rgb, meadow_color(v_world_position.xy,
                     (v_world_position.xy+vec2(0.,local_origin_y))*.5),
                     .25*smoothstep(5.,22.,grass_distance));
base_color.rgb *= mix(.62,1.,smoothstep(0.,.18,grass_height));
if (base_color.a < foliage_alpha_cutoff) discard;''')
    fragment = fragment.replace('local_leaf_normal(v_view_tbn[2],v_view_position)',
        'normalize(mix(local_leaf_normal(v_view_tbn[2],v_view_position), '
        'normalize((p3d_ViewMatrix*vec4(0.,0.,1.,0.)).xyz), mix(.88,.62,grass_growth)*smoothstep(8.,25.,grass_distance)))')
    fragment = fragment.replace('local_leaf_normal(v_world_tbn[2],v_world_position)',
        'normalize(mix(local_leaf_normal(v_world_tbn[2],v_world_position), '
        'vec3(0.,0.,1.), mix(.88,.62,grass_growth)*smoothstep(8.,25.,grass_distance)))')
    if coastal:
        vertex = vertex.replace('/8.;', '/2.;')
        vertex = vertex.replace('mix(.3,1.35,grass_growth)*mix(1.,.55,smoothstep(.25,.9,woodland))',
                                'mix(.3,1.35,grass_growth)*mix(1.,.55,smoothstep(.25,.9,woodland))*.45')
    return Shader.make(Shader.SLGLSL, vertex, fragment)


def rooted_vertex(vertex, position_line, position_name):
    vertex = vertex.replace('void main() {', '''
uniform float root_anchor;
void main() {''')
    return vertex.replace(position_line, position_line + f'''
vec2 root_slope = p3d_TextureMatrix[2].xy;
float root_blend = 1.0 - smoothstep(0.0, 2.0, p3d_Vertex.z + root_anchor);
{position_name}.z += root_blend * dot(root_slope, p3d_Vertex.xy);
''')


def tree_shader(foliage, *, filtered_shadows=True):
    fragment = foliage.getText(Shader.STFragment)
    if filtered_shadows:
        # 仅木本材质对原太阳深度做3×3帐篷滤波，缓和叶卡的二值碎影；投影几何和偏移不变。
        fragment = fragment.replace('return mix(1.0, texture(shadowmap, p), coverage);', '''
    vec2 texel = 2. / vec2(textureSize(shadowmap, 0));
    float filtered = 0.;
    for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
        float weight = (x == 0 ? 2. : 1.) * (y == 0 ? 2. : 1.);
        filtered += weight * texture(shadowmap, vec3(p.xy + vec2(x,y)*texel, p.z));
    }
    return mix(1., filtered/16., coverage);
''')
    return Shader.make(Shader.SLGLSL,
                       rooted_vertex(foliage.getText(Shader.STVertex),
                                     'vec4 model_position = p3d_Vertex;', 'model_position'),
                       fragment)


def set_root_slope(node, slope):
    """借用二维UV不使用的矩阵Z列，避免逐树ShaderAttrib重绑整套叶材质。"""
    matrix = Mat4(Mat4.identMat())
    matrix.setCell(2, 0, slope[0])
    matrix.setCell(2, 1, slope[1])
    transform = TransformState.makeMat(matrix)
    for stage in node.findAllTextureStages():
        node.setTexTransform(stage, transform)


def root_slope(node, curve, d, s, seed):
    across = [floor_point(curve, d + offset, s, seed) for offset in (-1, 1)]
    along = [floor_point(curve, d, s + offset, seed) for offset in (-1, 1)]
    if any(point is None for point in (*across, *along)):
        return
    normal = (across[1] - across[0]).cross(along[1] - along[0])
    normal.normalize()
    x, y = -normal.x / normal.z, -normal.y / normal.z
    angle = math.radians(node.getH())
    scale = node.getScale()
    set_root_slope(node, ((x * math.cos(angle) + y * math.sin(angle)) * scale.x / scale.z,
                         (-x * math.sin(angle) + y * math.cos(angle)) * scale.y / scale.z))


def grass_template(grasses, shader, *, grid=11):
    """离线式准备一个4米共享草格，流送只实例化，不复制其顶点。"""
    points, normals, uv, faces, colors = [], [], [], [], []
    rng = random.Random(24024)
    for row in range(grid):
        for col in range(grid):
            family = (row + col) % 2
            variant = family * 3 + rng.randrange(3) if rng.random() < .8 else 6 + rng.randrange(2)
            mesh, texture = grasses[variant]
            x = (col + .5 + rng.uniform(-.32, .32)) * 4 / grid - 2
            y = (row + .5 + rng.uniform(-.32, .32)) * 4 / grid - 2
            angle, scale = rng.uniform(0, math.tau), rng.uniform(.45, .65)
            width = scale * 11 / grid
            vertical = min(1., .65 / max(point[2] for point in mesh['points']))
            co, si, offset = math.cos(angle), math.sin(angle), len(points)
            metadata = ((x + 2) / 4, (y + 2) / 4, family, rng.uniform(.01, .99))
            for p, n, t in zip(mesh['points'], mesh['normals'], mesh['uv'], strict=True):
                points.append((x + (p[0] * co - p[1] * si) * width,
                               y + (p[0] * si + p[1] * co) * width, p[2] * scale * 2.2 * vertical))
                normal = Vec3((n[0] * co - n[1] * si) / width, (n[0] * si + n[1] * co) / width,
                              n[2] / (scale * 2.2 * vertical))
                normals.append(tuple(normal.normalized()))
                uv.append(t)
                colors.append(metadata)
            faces.extend(tuple(offset + i for i in face) for face in mesh['faces'])
    template = model('kcd-stream-grass', {'points': points, 'normals': normals,
                                        'uv': uv, 'faces': faces, 'colors': colors, 'maps': grasses[0][0]['maps'],
                                        'foliage': grasses[0][0]['foliage']}, texture, shader)
    template.hide(SHADOW_MASK)
    soft_cutout(template)
    return template


def soft_cutout(node):
    """先把源遮罩转为覆盖率，再用已有4x MSAA；叶面内部保持完整，不把整树当半透明层。"""
    node.setTransparency(TransparencyAttrib.MMultisample, 3)
    node.setAttrib(AlphaTestAttrib.make(AlphaTestAttrib.MNone, 0.), 3)


def set_world_lod_range(node, world_distance):
    """只为过小缩放的灌木/幼树兜底下限距离，避免 45m 眼前闪现且不拉高远距渲染开销。"""
    scale = max(float(node.getSx()), float(node.getSy()), float(node.getSz()), .05)
    current = float(node.node().getIn(0)) * scale
    if current < world_distance:
        node.node().clearSwitches()
        node.node().addSwitch(world_distance / scale, 0.)


def valid_verge(curve, p, s, minimum):
    if not isinstance(curve, CareerCourse):
        return True
    distance, lateral = curve.project(tuple(p))
    # 回头弯另一支道路可能更近；草木不能跨到那支道路的路面上。
    return abs(lateral) >= minimum and abs(distance - s) < 40


def grove_regions(index, seed):
    """近侧林缘与疏远的上坡林片共用绝对里程地块，不在200m段界重置。"""
    start = index * 200
    for cell in range(math.floor((start-60)/96), math.ceil((start+260)/96)):
        for side, tier in ((-1, 0), (1, 0), (-1, 1), (1, 1)):
            if tier and (cell+side) % 3:
                continue
            group_seed = seed*971 + cell*23399 + side*3581 + tier*9173
            rng = random.Random(group_seed)
            center_s = cell * 96 + rng.uniform(-12, 12)
            center_d = side * ((47 if side < 0 else 53) + tier*60 + rng.uniform(-10, 12))
            radius_d, radius_s = rng.uniform(27, 34), rng.uniform(35, 48)
            skew = rng.uniform(-.28, .28)
            yield side, tier, center_d, center_s, radius_d, radius_s, skew, group_seed


def grove_positions(index, seed):
    """按完整地块生成树位再分段；组内枝冠相接，组间保留草甸开口。"""
    start = index * 200
    for _side, tier, center_d, center_s, radius_d, radius_s, skew, group_seed in grove_regions(index, seed):
        rng = random.Random(group_seed+5171)
        for row in range(-4, 5):
            for col in range(-3, 4):
                u = col/3 + rng.uniform(-.1, .1)
                v = row/4 + rng.uniform(-.08, .08)
                if u*u+v*v > 1 or rng.random() < (.18 if tier else .08):
                    continue
                d = center_d + radius_d*u + skew*radius_s*v
                s = center_s + radius_s*v
                variant = rng.choices(range(5), (4, 2, 1, 3, 3))[0]
                height = rng.uniform(13, 18) + 1.2*(1-u*u-v*v) + tier*2
                heading, detail_seed = rng.uniform(0, 360), rng.randrange(2**30)
                if start <= s < start+200:
                    yield d, s, variant, height, heading, detail_seed, u*u+v*v


class LocalVegetation:
    """仅供本地试驾的直接替换；生产入口、打包资源与存档规则不变。"""

    def __init__(self, cache, environment=None, *, daylight=DAYLIGHT, canopy_visibility=CANOPY_VISIBILITY,
                 sky_transmission=1., hd2_rocks=False):
        self.cache = cache
        self.environment = environment
        self.parameters = (None if environment is None else
                           json.loads((environment / 'original-environment.json').read_text(encoding='utf-8')))
        self.daylight = None if environment is None or daylight is None else daylight
        self.canopy_visibility = canopy_visibility
        self.sky_transmission = sky_transmission
        self.hd2_rocks = hd2_rocks
        self.forest_canopies = {}
        self.surface_normals = {}
        self._coastal_course = False
        self.original_load = expressway.load_kit
        self.original_landscape = expressway_route.landscape_steps
        self.original_vegetation = expressway_route.vegetation_steps
        self.original_segment = expressway_route.segment_steps

    def install(self):
        from panda3d.core import Filename

        from scene import Scene
        from ui import theme as ui_theme

        self.original_asset_filename = ui_theme.asset_filename
        local_previews = self.cache.parent / 'career-previews'

        def local_asset_filename(relative):
            if relative.startswith('career/'):
                candidate = local_previews / Path(relative).name
                if candidate.is_file():
                    return Filename.fromOsSpecific(str(candidate))
            return self.original_asset_filename(relative)

        ui_theme.asset_filename = local_asset_filename
        self.original_setup = Scene.setup_endless
        self.original_init = Scene.__init__
        self.original_lighting = Scene.update_lighting
        self.original_rail_shadow = expressway_route.rail_shadow_coordinate
        expressway.load_kit = self.load_kit
        expressway_route.landscape_steps = self.landscape
        expressway_route.vegetation_steps = self.vegetation
        expressway_route.segment_steps = self.segment

        def setup(scene):
            self.forest_canopies.clear()
            scene.render.setShaderInput('local_canopy_occlusion', .7)
            scene.render.setShaderInput('local_sky_transmission', 0.)
            empty = Texture('empty-woodland-coverage')
            empty.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRed)
            empty.setRamImage(bytes([0]))
            scene.render.setShaderInput('local_forest_coverage', empty)
            scene.render.setShaderInput('local_forest_bounds', (0., 0., 1., 1.))
            curve = scene.base.session.simulation.stream.curve
            self._coastal_course = isinstance(curve, CareerCourse) and coast_candidate(curve.course_id)
            texture, origin, mode = grass_heightfield(curve.course_id if isinstance(curve, CareerCourse) else None)
            scene.render.setShaderInput('grass_heightfield', texture)
            scene.render.setShaderInput('grass_grid_origin', origin)
            scene.render.setShaderInput('grass_surface_mode', mode)
            self.original_setup(scene)
            cutout_shadows(scene)
            # 原树只供太阳投影，主相机使用近树及原远模合批。
            camera = scene.base.cam.node()
            camera.setCameraMask(camera.getCameraMask() & ~SHADOW_MASK)

        def initialize(scene, base, *, initial_stream_budget_ms=None):
            self.original_init(scene, base, initial_stream_budget_ms=initial_stream_budget_ms)
            from kcd_local_environment import DAYLIGHT_SH_SCALE, landscape_lighting

            if base.session.simulation.track == 'endless' and scene.coastal_daylight is None:
                landscape_lighting(scene, DAYLIGHT_SH_SCALE if self.daylight is not None else .65)

        Scene.setup_endless = setup
        Scene.__init__ = initialize

        if self.parameters is not None:
            from kcd_local_environment import DAYLIGHT_SUN_SCALE, source_rail_shadow, source_sun

            if self.daylight is not None:
                metadata = json.loads((self.daylight / 'daylight-manifest.json').read_text(encoding='utf-8'))
                self.parameters['lighting']['SunVector'] = ','.join(str(-v) for v in metadata['directional_sun'])

            def lighting(scene, position):
                self.original_lighting(scene, position)
                if scene.base.session.simulation.track == 'endless':
                    origin = float(scene.base.session.render_origin())
                    current = scene.render.getShaderInput('local_origin_y')
                    if current.getValueType() == current.MInvalid or current.getVector().x != origin:
                        scene.render.setShaderInput('local_origin_y', origin)
                    if scene.coastal_daylight is None:
                        source_sun(scene, position, self.parameters,
                                   intensity=DAYLIGHT_SUN_SCALE if self.daylight is not None else .8)

            def rail_shadow(curve, distance, lateral, height=0):
                if isinstance(curve, CareerCourse) and curve.course_id in ('coast-club', 'coast-final'):
                    return self.original_rail_shadow(curve, distance, lateral, height)
                return source_rail_shadow(curve, distance, lateral, self.parameters, height)

            Scene.update_lighting = lighting
            expressway_route.rail_shadow_coordinate = rail_shadow

    def restore(self):
        from scene import Scene
        from ui import theme as ui_theme

        ui_theme.asset_filename = self.original_asset_filename
        expressway.load_kit = self.original_load
        expressway_route.landscape_steps = self.original_landscape
        expressway_route.vegetation_steps = self.original_vegetation
        expressway_route.segment_steps = self.original_segment
        Scene.setup_endless = self.original_setup
        Scene.__init__ = self.original_init
        Scene.update_lighting = self.original_lighting
        expressway_route.rail_shadow_coordinate = self.original_rail_shadow

    def load_kit(self, loader, parent, old_trees):
        from kcd_local_environment import vegetation_material
        from local_coastal_landscape import landscape_materials, load_rocks, sandstone_shader

        kit = self.original_load(loader, parent, old_trees)
        kit['foliage-shader'] = vegetation_material(kit['foliage-shader'])
        kit['local-rocks'] = load_rocks(parent)
        asphalt = kit['road-asphalt-shader']
        fragment = asphalt.getText(Shader.STFragment).replace(
            'return vec4(mix(photograph,vec3(gray),0.85),1.0);',
            'return vec4(mix(photograph,vec3(gray),0.85)*.42,1.0);')
        kit['road-asphalt-shader'] = Shader.make(Shader.SLGLSL, asphalt.getText(Shader.STVertex), fragment)
        rooted_foliage = tree_shader(kit['foliage-shader'])
        trees, grasses, ground = load_local(self.cache, rooted_foliage, distance_lods=True, tree_letters='abcde',
                                           canopy_visibility=self.canopy_visibility)
        kit['local-kcd-rocks'] = load_sandstone(self.cache, sandstone_shader())
        for rock in kit['local-kcd-rocks'].values():
            rock.reparentTo(parent)
        if self.hd2_rocks:
            from hd2_local_rocks import load_rock

            kit['local-hd2-rock'] = load_rock()
            kit['local-hd2-rock'].reparentTo(parent)
        kit['ground'] = ground
        terrain_shader = kit['route-terrain-shader']
        fragment = terrain_shader.getText(Shader.STFragment).replace(
            'vec3 tint = clamp(v_color.rgb * vec3(3.2,2.7,4.8), .35, 1.0);',
            'vec3 tint = vec3(.92,.95,.96);')
        kit['route-terrain-shader'] = Shader.make(
            Shader.SLGLSL, terrain_shader.getText(Shader.STVertex), fragment)
        kit['local-kcd-trees'] = []
        kit['local-kcd-shrubs'] = load_shrubs(self.cache, rooted_foliage)
        kit['local-kcd-young-oaks'] = load_young_oaks(self.cache, rooted_foliage, trees[0].getChild(0))
        kit['local-kcd-ferns'] = load_ferns(self.cache, tree_shader(kit['foliage-shader'], filtered_shadows=False), grasses)
        for fern in kit['local-kcd-ferns']:
            fern.setShaderInput('local_sky_transmission', 0.)
            # 低地被与原草一样接收树影，不增加低于1m的微细投影。
            fern.hide(SHADOW_MASK)
            soft_cutout(fern)
            fern.reparentTo(parent)
        for young in kit['local-kcd-young-oaks']:
            young.setShaderInput('local_sky_transmission', self.sky_transmission)
            soft_cutout(young)
            young.reparentTo(parent)
        for shrub in kit['local-kcd-shrubs']:
            shrub.setShaderInput('local_sky_transmission', self.sky_transmission)
            soft_cutout(shrub)
            shrub.reparentTo(parent)
        for tree in trees:
            tree.setShaderInput('local_sky_transmission', self.sky_transmission)
            soft_cutout(tree)
            tree.reparentTo(parent)
            kit['local-kcd-trees'].append(tree)
        kit['local-tree-batch-shaders'] = tree_batch_shaders(trees[0].getChild(0).getShader())
        for name in ('broadleaf-a', 'broadleaf-b', 'fine-shrubs', 'source-grass'):
            kit[name].removeNode()
            kit[name] = parent.attachNewNode('local-empty-' + name)
        kit['city-shrub'] = kit['local-kcd-shrubs'][0]
        for variant in range(len(old_trees)):
            kit['tree-' + str(variant)].removeNode()
            tree = parent.attachNewNode('local-collision-tree-' + str(variant))
            body = trees[variant].copyTo(tree)
            # 原外层2.2–3.2倍约定保留；各原始树高不同，先归一到同一4.5m模板高度。
            body.setScale(4.5 / float(trees[variant].getTag('source-height')))
            body.setZ(-.05)
            kit['tree-' + str(variant)] = tree
        grass = grass_shader(kit['foliage-shader'], coastal=self._coastal_course)
        kit['local-kcd-grass'] = grass_template(grasses, grass)
        kit['local-kcd-grass'].reparentTo(parent)
        kit['local-kcd-grass-mid'] = grass_template(grasses, grass, grid=6)
        kit['local-kcd-grass-mid'].reparentTo(parent)
        if self.environment is not None:
            from kcd_local_environment import load_environment

            load_environment(kit, parent.getParent(), self.environment)
            if self.daylight is not None:
                from kcd_local_environment import load_daylight

                load_daylight(kit, self.daylight)
        else:
            # 无原始环境探针的对照模式仍提供草地融合输入。
            parent.getParent().setShaderInput('local_ground_meadow', ground)
            parent.getParent().setShaderInput('local_ground_dry', ground)
            parent.getParent().setShaderInput('local_origin_y', 0.)
        landscape_materials(kit)
        return kit

    def landscape(self, root, index, seed, curve, kit, detail_parent):
        from local_coastal_landscape import rock_steps

        # 岩群先确定实际外廓，后续树木才能留出根部净距，而非只猜测名义坐标。
        yield from rock_steps(root, index, seed, curve, kit, detail_parent, floor_point)
        yield from self.original_landscape(root, index, seed, curve, kit, detail_parent)
        if isinstance(curve, CareerCourse):
            yield from self.vegetation(root, index, seed, curve, kit, detail_parent)
        else:
            from environment.expressway_mountains import mountain_point

            origin = Vec3(*expressway_route.anchor(curve, index))
            rng = random.Random(index * 7919 + seed * 971)
            for width in (18, 43, 76, 116, 166):
                for local in range(10, 200, 26):
                    s = index * 200 + local + rng.uniform(-5, 5)
                    p = mountain_point(curve, -1, width + rng.uniform(-7, 7), s, seed)
                    tree = kit['local-kcd-trees'][rng.randrange(3)].copyTo(detail_parent(s))
                    tree.setPos(p - origin)
                    tree.setScale(rng.uniform(12, 18) / float(tree.getTag('source-height')))
                    tree.setH(rng.uniform(0, 360))
                    across = (mountain_point(curve, -1, width + 1, s, seed)
                              - mountain_point(curve, -1, width - 1, s, seed))
                    along = (mountain_point(curve, -1, width, s + 1, seed)
                             - mountain_point(curve, -1, width, s - 1, seed))
                    normal = across.cross(along)
                    x, y = -normal.x / normal.z, -normal.y / normal.z
                    angle = math.radians(tree.getH())
                    set_root_slope(tree, (x * math.cos(angle) + y * math.sin(angle),
                                          -x * math.sin(angle) + y * math.cos(angle)))
                    yield 'local-coastal-forest-ridge'
        if self.environment is not None:
            if not isinstance(curve, CareerCourse):
                start = index*200
                enabled = bool(expressway_route.city_weight(start, seed) or
                               expressway_route.city_weight(start+200, seed))
                # 局部UV每600米回绕；共用段根保持合批，横向范围由地表自己的UV判定。
                root.setShaderInput('city_lawn_phase',
                                    (start % 8000-start % 600+seed % 5*160, float(enabled)))
            yield from self.surface_weights(root, index, curve)

    def surface_weights(self, root, index, curve):
        import numpy as np

        trees = [node for node in root.findAllMatches('**/+LODNode')
                 if node.getName().startswith('kcd-oak-')]
        origin = Vec3(*expressway_route.anchor(curve, index))
        centers = np.array([tuple(node.getPos(root) + origin)[:2] for node in trees], dtype=np.float32).reshape(-1, 2)
        radii = np.array([node.getSx(root) * float(node.getTag('source-crown-radius')) for node in trees], dtype=np.float32)
        yield 'local-woodland-coverage'
        # 仅取实际采样林冠覆盖的地表紧包围盒，避免把 650m 海面与 480m 远山算进覆盖纹理。
        low_x = low_y = math.inf
        high_x = high_y = -math.inf
        for name in ('course-landscape', 'route-landscape', 'kcd-stream-grass'):
            for node in root.findAllMatches('**/' + name):
                tight = node.getTightBounds(root)
                if tight is None:
                    continue
                n_low, n_high = tight
                low_x = min(low_x, n_low.x + origin.x)
                low_y = min(low_y, n_low.y + origin.y)
                high_x = max(high_x, n_high.x + origin.x)
                high_y = max(high_y, n_high.y + origin.y)
        if low_x > high_x:
            volume = root.getBounds()
            low, high = volume.getMin(), volume.getMax()
            bounds = (low.x + origin.x, low.y + origin.y, high.x + origin.x, high.y + origin.y)
        else:
            bounds = (low_x, low_y, high_x, high_y)
        yield 'local-woodland-coverage'
        if len(centers):
            pad = radii * 4.0
            canopy_box = (
                float(np.min(centers[:, 0] - pad)),
                float(np.min(centers[:, 1] - pad)),
                float(np.max(centers[:, 0] + pad)),
                float(np.max(centers[:, 1] + pad)),
            )
        else:
            canopy_box = bounds
        dirty = [canopy_box]
        for previous, (path, _box, prev_canopy, _centers, _radii) in tuple(self.forest_canopies.items()):
            if path.isEmpty():
                dirty.append(prev_canopy)
                del self.forest_canopies[previous]
        self.forest_canopies[index] = root, bounds, canopy_box, centers, radii
        all_centers = np.concatenate([item[3] for item in self.forest_canopies.values()])
        all_radii = np.concatenate([item[4] for item in self.forest_canopies.values()])
        # 新段准备时同步刷新相交旧段，所有覆盖场都计入同一组周围实际树冠。
        pending = []
        for path, box, _cbox, _centers, _radii in tuple(self.forest_canopies.values()):
            if path is not root and not any(
                box[0] <= region[2] and box[2] >= region[0] and box[1] <= region[3] and box[3] >= region[1]
                for region in dirty
            ):
                continue
            revision = object()
            path.setPythonTag('woodland-revision', revision)
            pending.append((path, box, revision))
        for path, box, revision in pending:
            texture, coordinates = yield from woodland_texture(all_centers, all_radii, box)
            # 转向会令分帧构建交错；旧计算不能覆盖后来已经登记的新树冠。
            if not path.isEmpty() and path.getPythonTag('woodland-revision') is revision:
                apply_woodland_inputs(path, texture, coordinates)
            yield 'local-woodland-coverage'
        smooth_normals = None
        if isinstance(curve, CareerCourse) and not coast_candidate(curve.course_id):
            from career_terrain import terrain

            # 有限赛道预载窗口之外是原条带网格，不能按笛卡尔地形的8米格读取法线。
            if index in terrain(curve.course_id):
                if curve.course_id not in self.surface_normals:
                    self.surface_normals[curve.course_id] = yield from course_normal_steps(curve.course_id)
                smooth_normals = self.surface_normals[curve.course_id]
        for node in root.findAllMatches('**/+GeomNode'):
            if node.getName() not in ('course-landscape', 'route-landscape') or node.hasTag('kcd-ground'):
                continue
            for number in range(node.node().getNumGeoms()):
                if smooth_normals is None:
                    continue
                data = node.node().modifyGeom(number).modifyVertexData()
                positions = GeomVertexReader(data, 'vertex')
                normal_writer = GeomVertexWriter(data, 'normal')
                for row in range(data.getNumRows()):
                    point = positions.getData3f()
                    key = round((point.x + origin.x) / 8), round((point.y + origin.y) / 8)
                    normal_writer.setData3f(*smooth_normals[key])
                    if row % 120 == 119:
                        yield 'local-kcd-ground-normals'
                del positions, normal_writer
            node.setTag('kcd-ground', '1')

    def segment(self, root, index, seed, kit, stabilize_rail, curve=None):
        origin = Vec3(*expressway_route.anchor(curve, index))
        for phase in self.original_segment(root, index, seed, kit, stabilize_rail, curve):
            if phase == 'trees':
                for node in root.findAllMatches('**/local-collision-tree-*'):
                    if node.hasTag('root-grounded'):
                        continue
                    p = node.getPos(root) + origin
                    s, d = curve.project(tuple(p)) if curve else (p.y, p.x)
                    floor = floor_point(curve, d, s, seed)
                    if floor is None:
                        node.hide()
                    else:
                        node.setZ(floor.z - origin.z + .05 * node.getSz())
                        root_slope(node, curve, d, s, seed)
                    node.setTag('root-grounded', '1')
            yield phase
        yield from city_static_batch_steps(root, kit['lamp'].getName())
        for group in root.findAllMatches('**/mainland-city'):
            # 城市低灌木不投 4K 太阳阴影，中庭与绿带灌木补齐与庭院一致的 190m 距离裁剪，并按缩放补偿自身 LOD。
            loose_shrubs = []
            for child in tuple(group.getChildren()):
                if child.hasTag('city-courtyard-shrub') or child.hasTag('city-greenbelt-shrub'):
                    child.hide(SHADOW_MASK)
                    set_world_lod_range(child, 125.)
                    loose_shrubs.append(child)
                elif child.hasTag('city-tree') or child.hasTag('city-courtyard-tree'):
                    child.hide(SHADOW_MASK)
                elif child.getName() == 'city-garden':
                    for sub in child.getChildren():
                        if sub.hasTag('city-garden-tree') or sub.getName() == 'garden-plants-distance':
                            sub.hide(SHADOW_MASK)
                            if sub.getName() == 'garden-plants-distance':
                                for shrub in sub.findAllMatches('**/kcd-hawthorn-*'):
                                    if isinstance(shrub.node(), LODNode):
                                        set_world_lod_range(shrub, 125.)
            if loose_shrubs:
                buckets = {}
                for shrub in loose_shrubs:
                    key = int(shrub.getPos(group).y // 50)
                    buckets.setdefault(key, []).append(shrub)
                for key, items in sorted(buckets.items()):
                    center = sum((item.getPos(group) for item in items), Vec3(0)) / len(items)
                    radius = max((item.getPos(group) - center).length() for item in items)
                    lod = FadeLODNode(f'city-shrubs-distance-{key}')
                    lod.setCenter(center)
                    lod.addSwitch(190.0 + radius, 0.0)
                    lod.setFadeTime(.35)
                    holder = group.attachNewNode(lod)
                    for item in items:
                        item.wrtReparentTo(holder)
            yield 'city-foliage-optimize'
        yield from tree_batch_steps(root, kit)

    def vegetation(self, root, index, seed, curve, kit, detail_parent):
        origin = Vec3(*expressway_route.anchor(curve, index))
        start = index * 200
        coastal = isinstance(curve, CareerCourse) and coast_candidate(curve.course_id)
        rng = random.Random(seed * 971 + index * 23399)
        fern_sites = []
        rock_bounds = [node.getTightBounds(root) for node in root.findAllMatches('**/+LODNode')
                       if node.getName().startswith(('local-coastal-bank-', 'kcd-sandstone-'))]

        def root_clear(point, gap):
            local = point - origin
            return all(local.x < low.x - gap or local.x > high.x + gap
                       or local.y < low.y - gap or local.y > high.y + gap for low, high in rock_bounds)

        def urban_roadside(d, s):
            # 城镇路侧由街区绿化接管；原物理树仍在segment()的固定位置显示。
            return d > 0 and not isinstance(curve, CareerCourse) and expressway_route.city_weight(s, seed) >= .95

        is_endless = not isinstance(curve, CareerCourse)
        # 无限高速左侧前排树按树冠半径加偏心枝余量外退至护栏外净空区，防止不对称长枝伸入行车道。
        foreground = (((-19.5, 44, 0, 14.), (-20.0, 88, 0, 13.5), (-20.0, 120, 1, 15.),
                       (-19.2, 178, 0, 12.5), (25, 155, 0, 13.5), (33, 164, 1, 14.))
                      if is_endless else
                      ((-13, 44, 0, 14.), (-14, 88, 0, 13.5), (-13, 120, 1, 15.),
                       (-15, 178, 0, 12.5), (25, 155, 0, 13.5), (33, 164, 1, 14.)))
        for d, local, variant, height in foreground:
            s = start + local
            if urban_roadside(d, s):
                continue
            p = floor_point(curve, d, s, seed)
            if p is None or p.z < -2 or not valid_verge(curve, p, s, 12) or not root_clear(p, 1.5):
                continue
            tree = kit['local-kcd-trees'][variant].copyTo(detail_parent(s))
            tree.setPos(p - origin)
            tree.setScale(height / float(tree.getTag('source-height')))
            if variant == 1:
                # 岩坡前采用有净空树干的原树，略展宽树冠，让岩体能从枝下读出来。
                crown_cap = 7.4 if is_endless else 8.0
                horizontal = crown_cap / float(tree.getTag('source-crown-radius'))
                tree.setScale(horizontal, horizontal, height / float(tree.getTag('source-height')))
            tree.setH(rng.uniform(0, 360))
            root_slope(tree, curve, d, s, seed)
            yield 'local-driving-view-tree'
            for number, (across, along) in enumerate(((d+math.copysign(2.4, d), s-3.),
                                                     (d+math.copysign(3.8, d), s+1.5), (d, s+4.))):
                fern_sites.append((across, along, number, 1.15 if number == 2 else 1.8,
                                   (index*47+number*113+s) % 360))
            # 主树后侧由较低的完整D/E树冠承接，不再让每棵前排树独立站在草坪中。
            companions = ((d - 10, s - 7, 4, 10.5), (d - 18, s + 12, 3, 11.5)) if d < 0 else (
                ((d + 18, s + 13, 4, 11.),) if variant == 0 else ())
            for companion_d, companion_s, family, companion_height in companions:
                behind = floor_point(curve, companion_d, companion_s, seed)
                if (behind is None or behind.z < -2 or not root_clear(behind, 1.5)
                        or not valid_verge(curve, behind, companion_s, 16)):
                    continue
                companion = kit['local-kcd-trees'][family].copyTo(detail_parent(companion_s))
                companion.setPos(behind - origin)
                companion.setH(rng.uniform(0, 360))
                companion.setScale(companion_height / float(companion.getTag('source-height')))
                root_slope(companion, curve, companion_d, companion_s, seed)
                yield 'local-driving-companion'
            for offset in (-6, 6):
                young_d = d + (-5 if d < 0 else 5)
                under = floor_point(curve, young_d, s + offset, seed)
                if under is None or not valid_verge(curve, under, s + offset, 14) or not root_clear(under, .7):
                    continue
                young = kit['local-kcd-young-oaks'][rng.randrange(3)].copyTo(detail_parent(s + offset))
                young.setPos(under - origin - Vec3(0, 0, .15))
                young.setH(rng.uniform(0, 360))
                young.setScale(rng.uniform(3, 4.8) / float(young.getTag('source-height')))
                set_world_lod_range(young, 160.)
                root_slope(young, curve, young_d, s + offset, seed)
                yield 'local-driving-understory'
        # 林缘与岩脚的真实低灌丛承担中层，右侧只在局部形成簇群，保留看海开口。
        for center, side in ((start + 28, -1), (start + 96, -1), (start + 164, -1),
                             (start + 90, 1)):
            for n in range(7 if side < 0 else 4):
                s = center + rng.uniform(-16, 16)
                d = side * (14 + rng.uniform(0, 17))
                p = floor_point(curve, d, s, seed)
                if p is None or p.z < -2 or not valid_verge(curve, p, s, 12) or not root_clear(p, .7):
                    continue
                node = kit['local-kcd-shrubs'][n % 3].copyTo(detail_parent(s))
                node.setPos(p - origin - Vec3(0, 0, .12))
                node.setH(rng.uniform(0, 360))
                node.setScale(rng.uniform(1.2, 2.2) / float(node.getTag('source-height')))
                set_world_lod_range(node, 125.)
                root_slope(node, curve, d, s, seed)
                yield 'local-kcd-understory'
        # 主岩群以矮木接到林缘，保留可读石面；不把两块大石孤立摆在草坪上。
        for center in (start + 50, start + 172):
            back = floor_point(curve, -42, center + 24, seed)
            if (back is not None and back.z >= -2 and valid_verge(curve, back, center + 24, 18)
                    and root_clear(back, 1.5)):
                tree = kit['local-kcd-trees'][0].copyTo(detail_parent(center + 24))
                tree.setPos(back - origin)
                tree.setScale(12 / float(tree.getTag('source-height')))
                tree.setH((index * 47 + center) % 360)
                root_slope(tree, curve, -42, center + 24, seed)
                yield 'local-outcrop-canopy'
            edge = ((-17, -12, 1.5, False), (-29, -14, 1.8, False), (-39, 1, 3.5, True),
                    (-33, 15, 3.8, True), (-20, 16, 3.2, True), (-16, 3, 1.4, False), (-39, -9, 1.7, False))
            for number, (d, offset, height, young) in enumerate(edge):
                s = center + offset
                p = floor_point(curve, d, s, seed)
                if p is None or p.z < -2 or not valid_verge(curve, p, s, 14) or not root_clear(p, .7):
                    continue
                plants = kit['local-kcd-young-oaks' if young else 'local-kcd-shrubs']
                node = plants[number % len(plants)].copyTo(detail_parent(s))
                node.setPos(p - origin - Vec3(0, 0, .12))
                node.setH((index * 47 + number * 83) % 360)
                node.setScale(height / float(node.getTag('source-height')))
                set_world_lod_range(node, 160. if young else 125.)
                root_slope(node, curve, d, s, seed)
                yield 'local-outcrop-understory'
        # 后排按完整地块组织；保留前排辨识树与主石面向道路的开口。
        for number, (d, s, variant, height, heading, detail_seed, edge) in enumerate(grove_positions(index, seed)):
            # 不适合种植的候选也消耗查询时间，不能等到成功放下一株才交还帧预算。
            if number % 16 == 0:
                yield 'local-grove-site-checks'
            if urban_roadside(d, s):
                continue
            if d > 0 and is_endless and s % 320 < 240:
                continue
            if -42 < d < 0 and any(start+local-35 < s < start+local+5 for local in (50, 172)):
                continue
            template = kit['local-kcd-trees'][variant]
            if is_endless:
                crown_r = height / float(template.getTag('source-height')) * float(template.getTag('source-crown-radius'))
                if abs(d) - crown_r < 10.5:
                    continue
            p = floor_point(curve, d, s, seed)
            if p is None or p.z < -2 or not valid_verge(curve, p, s, 18) or not root_clear(p, 1.5):
                continue
            if coastal and abs(d) > 36:
                from environment.career_coast import _shoreline

                # 海侧补充林群留成片开口，原碰撞树继续由原segment显示。
                if p.x > _shoreline(p.y)-30 and (s+seed*11) % 192 > 64:
                    continue
            tree = template.copyTo(detail_parent(s))
            tree.setPos(p-origin)
            tree.setScale(height/float(tree.getTag('source-height')))
            tree.setH(heading)
            root_slope(tree, curve, d, s, seed)
            yield 'local-grove-canopy'
            plants_rng = random.Random(detail_seed)
            if abs(d) > 90:
                continue
            if detail_seed % 4 == 0:
                under_d, under_s = d+plants_rng.uniform(-4, 4), s+plants_rng.uniform(-4, 4)
                under = floor_point(curve, under_d, under_s, seed)
                if (under is not None and valid_verge(curve, under, under_s, 18)
                        and root_clear(under, .7)):
                    young = edge > .55
                    plants = kit['local-kcd-young-oaks' if young else 'local-kcd-shrubs']
                    shrub = plants[plants_rng.randrange(3)].copyTo(detail_parent(under_s))
                    shrub.setPos(under-origin-Vec3(0, 0, .12))
                    shrub.setH(plants_rng.uniform(0, 360))
                    shrub.setScale(plants_rng.uniform(3, 4.8) / float(shrub.getTag('source-height'))
                                   if young else plants_rng.uniform(1.1, 1.9) / float(shrub.getTag('source-height')))
                    set_world_lod_range(shrub, 160. if young else 125.)
                    root_slope(shrub, curve, under_d, under_s, seed)
                    yield 'local-grove-understory'
            if abs(d) > 78 or detail_seed % 3:
                continue
            for across, along in ((d+2.5, s+1.5), (d-1.5, s-2.5)):
                fern_sites.append((across, along, plants_rng.randrange(3), plants_rng.uniform(1.1, 1.6),
                                   plants_rng.uniform(0, 360)))
        # 林缘沿同一地块外廓退进；以低矮成片灌丛连接树脚，避免逐树摆一个盆栽状灌木。
        for side, tier, center_d, center_s, radius_d, radius_s, skew, group_seed in grove_regions(index, seed):
            if tier:
                continue
            if urban_roadside(center_d, center_s):
                continue
            edge_rng = random.Random(group_seed+7321)
            for v in (-.68, -.22, .32, .73):
                edge_s = center_s+radius_s*v
                edge_d = center_d-side*radius_d*math.sqrt(1-v*v)+skew*radius_s*v
                for offset in (-3.8, -.9, 2.4):
                    s = edge_s+offset+edge_rng.uniform(-.5, .5)
                    d = edge_d+edge_rng.uniform(-1.7, 1.7)
                    if not start <= s < start+200:
                        continue
                    if is_endless and abs(d) < 11.5:
                        continue
                    p = floor_point(curve, d, s, seed)
                    if (p is None or p.z < -2 or not valid_verge(curve, p, s, 15)
                            or not root_clear(p, .7)):
                        continue
                    shrub = kit['local-kcd-shrubs'][edge_rng.randrange(3)].copyTo(detail_parent(s))
                    height = edge_rng.uniform(.7, 1.45)
                    scale = height/float(shrub.getTag('source-height'))
                    width = scale*edge_rng.uniform(1.2, 1.6)
                    shrub.setScale(width, width, scale)
                    set_world_lod_range(shrub, 125.)
                    shrub.setPos(p-origin-Vec3(0, 0, .10))
                    shrub.setH(edge_rng.uniform(0, 360))
                    root_slope(shrub, curve, d, s, seed)
                    yield 'local-grove-edge'
        for d, s, variant, scale, heading in fern_sites:
            point = floor_point(curve, d, s, seed)
            if point is None or not valid_verge(curve, point, s, 11.5) or not root_clear(point, .2):
                continue
            fern = kit['local-kcd-ferns'][variant].copyTo(detail_parent(s))
            fern.setPos(point-origin-Vec3(0, 0, .035))
            fern.setScale(scale)
            fern.setH(heading)
            root_slope(fern, curve, d, s, seed)
            yield 'local-grove-ferns'
        grass_floor_cache = {}

        def cached_grass_floor(d_val, s_val):
            key = (d_val, s_val)
            if key not in grass_floor_cache:
                grass_floor_cache[key] = floor_point(curve, d_val, s_val, seed)
            return grass_floor_cache[key]

        for cell_start in range(start, start + 200, 20):
            center_s = cell_start + 10
            center = expressway_route.sample(curve, center_s)
            heading = math.radians(curve.sample(center_s).heading) if curve else 0
            co, si = math.cos(heading), math.sin(heading)
            bands = ((-39, -35, -31, -27, -23, -19, -15, -11, 11, 15, 19, 23, 27, 31, 35, 39),
                     (-71, -67, -63, -59, -55, -51, -47, -43, 43, 47, 51, 55, 59, 63, 67, 71),
                     (-103, -99, -95, -91, -87, -83, -79, -75, 75, 79, 83, 87, 91, 95, 99, 103))
            for band, columns in enumerate(bands):
                controls = {name: PTALVecBase3f.emptyArray(80) for name in ('00', '10', '01', '11')}
                count = 0
                for s in range(cell_start + 2, cell_start + 20, 4):
                    for column, d in enumerate(columns):
                        if column % 16 == 0:
                            yield 'local-grass-site-checks'
                        if urban_roadside(d, s) and d >= 59+expressway_route._city_shift(s, seed):
                            continue
                        p = cached_grass_floor(d, s)
                        if p is None or p.z < -2 or not valid_verge(curve, p, s, 10):
                            continue
                        floors = [cached_grass_floor(d + dx, s + dy)
                                  for dx, dy in ((-2, -2), (2, -2), (-2, 2), (2, 2))]
                        if any(point is None for point in floors) or (coastal and any(point.z < -2 for point in floors)):
                            continue
                        for name, floor in zip(('00', '10', '01', '11'), floors, strict=True):
                            delta = floor - center
                            controls[name][count] = Vec3(delta.x * co + delta.y * si,
                                                        -delta.x * si + delta.y * co, delta.z)
                        count += 1
                        yield 'local-kcd-grass-controls'
                if count:
                    lod = LODNode('local-kcd-grass-distance')
                    lod.addSwitch(220, 0)
                    patch = detail_parent(center_s).attachNewNode(lod)
                    patch.setPos(center - origin)
                    patch.setH(math.degrees(heading))
                    batch = kit['local-kcd-grass-mid' if band else 'local-kcd-grass'].copyTo(patch)
                    batch.setInstanceCount(count)
                    # 共享斑块固定鲜/干草与株位；距离只渐隐覆盖率，不改变草高。
                    radius = max(values[number].length() for values in controls.values() for number in range(count)) + 3
                    batch.node().setBounds(BoundingSphere(Vec3(0, 0, 0), radius))
                    batch.node().setFinal(True)
                    for name, values in controls.items():
                        batch.setShaderInput('grass_floor' + name, values)
                    yield 'local-kcd-grass-batch'


def cutout_shadows(scene):
    from kcd_local_environment import CANOPY_SHADOW_SPAN
    from simplepbr._shaderutils import _load_shader_str

    defines = {'USE_330': True}
    # 阴影相机的高优先级状态不继承逐树输入；沿用统一遮罩阈值，可见材质分别使用源阈值。
    vertex = _load_shader_str('shadow.vert', defines.copy())
    fragment = _load_shader_str('shadow.frag', defines.copy()).replace(
        '#ifdef USE_330\n    o_color = base_color;',
        'if (base_color.a < .25) discard;\n#ifdef USE_330\n    o_color = base_color;')
    light = scene.sun_path.node()
    # 中距离树冠和它的后层都保留自阴影；近处微细阴影不是本轮资源预算的重点。
    light.setShadowCaster(True, 4096, 4096)
    light.getLens().setFilmSize(CANOPY_SHADOW_SPAN, CANOPY_SHADOW_SPAN)
    # 29位属于幽灵车和路标，其初始化会从太阳相机中排除该位。
    light.setCameraMask(SHADOW_MASK)
    light.setInitialState(light.getInitialState().setAttrib(
        ShaderAttrib.make(Shader.make(Shader.SLGLSL, vertex, fragment)), 10))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'logs/local-kcd-drive')
    parser.add_argument('--environment', type=Path, default=ROOT / 'logs/local-kcd-original-environment')
    parser.add_argument('--hd2-rocks', action='store_true', help='试用本机HD2岩壁，原安装只读')
    args, game_args = parser.parse_known_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    environment = args.environment.resolve()
    if not (environment / 'original-environment.json').is_file():
        from prepare_kcd_environment import prepare

        prepare(environment)
    if not (DAYLIGHT / 'daylight-manifest.json').is_file():
        from prepare_daylight_environment import prepare

        prepare(ROOT / 'art/expressway/sources/daylight-29', DAYLIGHT,
                azimuth=180, match_sun_elevation=True)
    from bake_kcd_canopy_visibility import prepare as prepare_canopy

    prepare_canopy(CANOPY_VISIBILITY)
    from main import main as run_game

    profile = LocalVegetation(output / 'assets', environment, hd2_rocks=args.hd2_rocks)
    profile.install()
    original_args = sys.argv
    try:
        # 沿用正式入口的驾驶、存档、菜单和工坊链；新增的仅是本地美术来源。
        sys.argv = [str(ROOT / 'src/main.py'), '--driving-mode', 'game', *game_args]
        return run_game()
    finally:
        sys.argv = original_args
        profile.restore()


if __name__ == '__main__':
    import multiprocessing

    multiprocessing.freeze_support()
    try:
        result = main()
    except Exception:
        from paths import user_data

        user_data().joinpath('crash.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise
    raise SystemExit(result)
