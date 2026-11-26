"""在本地试驾中使用KCD2地表全套贴图与原始环境探针；不替代原引擎GI。"""

import json
import math

from panda3d.core import Filename, PTALVecBase3f, Shader, Texture, Vec3
from simplepbr.envmap import EnvMap

CANOPY_SHADOW_SPAN = 320
CANOPY_SHADOW_LEAD = 45
DAYLIGHT_SH_SCALE = 1.2
DAYLIGHT_SUN_SCALE = 1.6

MEADOW_COLOR = '''
uniform sampler2D local_ground_meadow;
uniform sampler2D local_ground_dry;
uniform float local_origin_y;
uniform sampler2D local_forest_coverage;
uniform vec4 local_forest_bounds;
float woodland_cover(vec2 position) {
    vec2 uv = (position+vec2(0.,local_origin_y)-local_forest_bounds.xy)*local_forest_bounds.zw;
    if (any(lessThan(uv,vec2(0.))) || any(greaterThan(uv,vec2(1.)))) return 0.;
    return textureLod(local_forest_coverage,uv,0.).r;
}
float meadow_patch(vec2 p) {
    p.y += local_origin_y;
    vec2 alternate = mat2(.8,-.6,.6,.8)*p*.016+vec2(.73,.19);
    float patch = mix(textureLod(local_ground_dry,p*.025+vec2(.31,.67),6.).g,
                      textureLod(local_ground_dry,alternate,6.).g,.35);
    return smoothstep(.13,.17,patch);
}
float meadow_dry_weight(vec2 p) {
    return mix(.08,.55,meadow_patch(p));
}
float meadow_growth(vec2 p) {
    p.y += local_origin_y;
    vec2 rotated = mat2(.93,-.37,.37,.93)*p*.041+vec2(.19,.83);
    float patch = mix(textureLod(local_ground_meadow,rotated,6.).g,
                      textureLod(local_ground_meadow,p*.019+vec2(.6,.2),6.).g,.25);
    return smoothstep(.059,.071,patch);
}
vec3 meadow_color(vec2 p,vec2 uv,float dry_weight) {
    float patch = textureLod(local_ground_meadow,(p+vec2(0.,local_origin_y))*.012,6.).g;
    float macro = mix(.68,1.14,smoothstep(.05,.085,patch));
    vec2 alternate = mat2(.8,-.6,.6,.8)*uv/1.37+vec2(.32,.57);
    vec3 pasture = mix(texture(local_ground_meadow,uv).rgb,
                       texture(local_ground_meadow,alternate).rgb,.4);
    return mix(pasture,
               texture(local_ground_dry,uv).rgb,dry_weight)*macro*mix(.88,1.08,meadow_growth(p));
}
vec3 meadow_color(vec2 p,vec2 uv) {
    return meadow_color(p,uv,meadow_dry_weight(p));
}
'''

MATERIAL = MEADOW_COLOR + '''
const float ground_grass_albedo_scale=.6;
uniform vec2 city_lawn_phase;
float city_lawn_weight() {
    if (city_lawn_phase.y < .5) return 0.;
    float phase = mod(v_texcoord.y+city_lawn_phase.x,8000.);
    float town = smoothstep(3200.,3440.,phase)*(1.-smoothstep(6160.,6400.,phase));
    float zone = floor(phase/1600.);
    float shift = -24.;
    // 桥位距离先减去整段相位，避免在约6000米的浮点数上再相减。
    float bridge_local = v_texcoord.y+(mod(city_lawn_phase.x,1600.)-820.);
    if (bridge_local > 800.) bridge_local -= 1600.;
    if (bridge_local < -800.) bridge_local += 1600.;
    if (zone == 1. || zone == 3.) shift *= smoothstep(18.,75.,abs(bridge_local));
    float across = v_texcoord.x-shift;
    // 横向过渡位于地方车道之下，原35米内地面不参与。
    return town*smoothstep(61.5,68.5,across)*(1.-smoothstep(151.5,158.5,across));
}
float ground_dry_weight() {
    return meadow_dry_weight(v_world_position.xy)*(1.-city_lawn_weight());
}
uniform sampler2D expressway_rock;
uniform sampler2D pasture_normal;
uniform sampler2D pasture_gloss;
uniform sampler2D pasture_height;
uniform sampler2D forest_albedo;
uniform sampler2D forest_normal;
uniform sampler2D forest_gloss;
uniform sampler2D forest_height;
uniform sampler2D dry_normal;
uniform sampler2D dry_gloss;
uniform sampler2D dry_height;
float forest_weight() { return woodland_cover(v_world_position.xy)*.85; }
vec2 kcd_uv() {
    vec3 n = normalize(v_world_tbn[2]);
    vec3 dx = dFdx(v_world_position), dy = dFdy(v_world_position);
    vec2 ux = dFdx(v_texcoord), uy = dFdy(v_texcoord);
    vec3 t = normalize(cross(dy,n)*ux.x + cross(n,dx)*uy.x);
    vec3 b = normalize(cross(dy,n)*ux.y + cross(n,dx)*uy.y);
    vec3 eye = normalize(camera_world_position-v_world_position);
    float w = forest_weight();
    float height = mix(mix(texture(pasture_height,v_texcoord*.25).r,
                          texture(dry_height,v_texcoord*.25).r,ground_dry_weight()),
                       texture(forest_height,v_texcoord*.25).r,w)-.5;
    return v_texcoord - vec2(dot(eye,t),dot(eye,b)) / max(dot(eye,n),.38)
                           * height * mix(.030,.024,w)*mix(1.,.25,city_lawn_weight());
}
vec4 expressway_albedo() {
    vec2 p = kcd_uv();
    float w = forest_weight();
    vec3 pasture = meadow_color(v_world_position.xy,p*.5,ground_dry_weight());
    vec3 forest = texture(forest_albedo,p*.25).rgb*.53327644;
    vec3 base = mix(pasture*ground_grass_albedo_scale,forest,w);
    vec3 rock = texture(expressway_rock,vec2(p.y/5.,(v_world_position.z+p.x*.08)/3.)).rgb;
    return vec4(mix(base,rock*vec3(.69,.66,.60),v_color.a),1.0);
}
float kcd_roughness() {
    vec2 p = kcd_uv();
    float mip_footprint = length(fwidth(v_texcoord));
    float filter_amount = smoothstep(.08, .70, mip_footprint);
    float gloss = mix(mix(texture(pasture_gloss,p*.25).r,
                         texture(dry_gloss,p*.25).r,ground_dry_weight()),
                      texture(forest_gloss,p*.25).r,forest_weight());
    float roughness = clamp(1.0-gloss,.08,1.0);
    return mix(roughness, max(roughness, .92), filter_amount);
}
vec3 kcd_normal(vec3 geometric_normal,vec3 position) {
    vec3 n = normalize(geometric_normal);
    vec3 dx = dFdx(position),dy = dFdy(position);
    vec2 ux = dFdx(v_texcoord),uy = dFdy(v_texcoord);
    vec3 t = cross(dy,n)*ux.x + cross(n,dx)*uy.x;
    vec3 b = cross(dy,n)*ux.y + cross(n,dx)*uy.y;
    float magnitude = max(dot(t,t),dot(b,b));
    if (magnitude < 1e-16) return n;
    float mip_footprint = length(fwidth(v_texcoord));
    float detail_filter = 1.0 - smoothstep(.08, .70, mip_footprint);
    vec2 p = kcd_uv()*.25;
    float w = forest_weight();
    vec3 detail = mix(mix(texture(pasture_normal,p).rgb,
                         texture(dry_normal,p).rgb,ground_dry_weight()),
                      texture(forest_normal,p).rgb,w)*2.-1.;
    detail.xy *= mix(1.15,0.98,w)*mix(1.,.3,city_lawn_weight())*detail_filter;
    detail.z = max(detail.z, .01)*sqrt(magnitude);
    return normalize(mat3(t,b,n)*detail);
}
'''

FOLIAGE_DETAIL = '''
uniform sampler2D local_normal;
uniform sampler2D local_gloss;
uniform sampler2D local_transmission;
uniform vec3 local_transmittance_color;
uniform float local_back_diffuse;
uniform float local_normal_view_dependency;
uniform vec3 local_specular_color;
uniform float local_canopy_occlusion;
uniform float local_sky_transmission;
vec3 local_opposite_sky(vec3 normal,vec3 front) {
    return max(front-.977206*(sh_coeffs[1]*normal.x+sh_coeffs[2]*normal.z+sh_coeffs[3]*normal.y),0.);
}
vec3 local_view_normal(vec3 n,vec3 eye) {
    vec3 facing = eye * (dot(n,eye) < 0. ? -1. : 1.);
    return normalize(mix(n,facing,local_normal_view_dependency*texture(local_transmission,v_texcoord).r));
}
vec3 local_leaf_normal(vec3 geometric_normal, vec3 position) {
    vec3 n = normalize(geometric_normal) * (gl_FrontFacing ? 1. : -1.);
    float detail_weight = 1.-smoothstep(12.,38.,length(v_world_position-camera_world_position));
    if (detail_weight <= 0.) return n;
    vec3 dx = dFdx(position), dy = dFdy(position);
    vec2 ux = dFdx(v_texcoord), uy = dFdy(v_texcoord);
    vec3 t = cross(dy,n)*ux.x + cross(n,dx)*uy.x;
    vec3 b = cross(dy,n)*ux.y + cross(n,dx)*uy.y;
    float magnitude = max(dot(t,t),dot(b,b));
    if (magnitude < 1e-16) return n;
    vec3 detail = texture(local_normal,v_texcoord).rgb*2.-1.;
    detail.z *= sqrt(magnitude);
    return normalize(mix(n,normalize(mat3(t,b,n)*detail),detail_weight*0.65));
}
'''


def vegetation_material(shader):
    """叶片与树皮用原件法线/光滑度/透光，而非整树共用白色默认材质。"""
    fragment = shader.getText(Shader.STFragment)
    fragment = fragment.replace('void main() {', FOLIAGE_DETAIL + '\nvoid main() {')
    # 灰度顶点RGB只作天空可见率，alpha保持1，避免遮蔽数据误伤阴影遮罩。
    fragment = fragment.replace('p3d_Material.baseColor * v_color * p3d_ColorScale *',
                                'p3d_Material.baseColor * p3d_ColorScale *')
    fragment = fragment.replace('float ambient_occlusion = 1.0;',
                                'float ambient_occlusion = mix(1.,v_color.r,local_canopy_occlusion);')
    fragment = fragment.replace('p3d_Material.roughness * metal_rough.g',
                                'max(.65,1.-texture(local_gloss,v_texcoord).r)')
    fragment = fragment.replace('vec3 spec_color = mix(F0, base_color.rgb, metallic);',
                                'vec3 spec_color = mix(local_specular_color, base_color.rgb, metallic);')
    fragment = fragment.replace('if (base_color.a < foliage_alpha_cutoff) discard;', '''
float lod_alpha = p3d_ColorScale.a;
base_color.a /= max(lod_alpha,.0001);
float opacity_width = max(fwidth(base_color.a),.001);
float foliage_visibility = 1.;
if (base_color.a < foliage_alpha_cutoff) discard;
base_color.a = clamp((base_color.a-foliage_alpha_cutoff)/opacity_width+.5,0.,1.)*foliage_visibility*lod_alpha;
''')
    # 当前环境探针下限制粗糙叶片的掠射填光；这与原件视向法线参数分别处理。
    fragment = fragment.replace('vec3 ibl_f = fresnelSchlickRoughness(n_dot_v, spec_color, perceptual_roughness);',
                                'vec3 ibl_f = mix(spec_color, '
                                'fresnelSchlickRoughness(n_dot_v, spec_color, perceptual_roughness), .1);')
    fragment = fragment.replace('ibl_f * env_brdf.x + env_brdf.y',
                                'ibl_f * env_brdf.x + env_brdf.y*.1')
    fragment = fragment.replace('normalize(v_view_tbn * normalmap)',
                                'local_view_normal(local_leaf_normal(v_view_tbn[2],v_view_position), normalize(-v_view_position))')
    fragment = fragment.replace('normalize(v_world_tbn * normalmap)',
                                'local_view_normal(local_leaf_normal(v_world_tbn[2],v_world_position), '
                                'normalize(camera_world_position-v_world_position))')
    fragment = fragment.replace(
        'func_params.n_dot_l = max(nl, 0.0) + max(-nl, 0.0)*0.35;',
        'float transmission = texture(local_transmission,v_texcoord).r;\n'
        '        func_params.n_dot_l = max(nl,0.);')
    # 透光颜色是叶色的色调，背面光照同样受底色调制，不能直接当作发光颜色相加。
    direct = 'color.rgb += func_params.n_dot_l * lightcol * (diffuse_contrib + spec_contrib) * shadow;'
    fragment = fragment.replace(direct, direct + '''
        float back_wrap = clamp(.4-.6*nl,0.,1.);
        color.rgb += lightcol * local_transmittance_color * local_back_diffuse * transmission
                   * base_color.rgb * back_wrap * diffuse_function() * shadow;
''')
    # 二阶SH反转方向时仅一阶项变号，复用未截断的正面结果，避免再计算整套SH。
    fragment = fragment.replace(
        'vec3 ibl_diff = base_color.rgb * max(irradiance_from_sh(world_normal), 0.0) * diffuse_function();',
        'vec3 local_sky_irradiance = irradiance_from_sh(world_normal);\n'
        'vec3 ibl_diff = base_color.rgb * max(local_sky_irradiance,0.) * diffuse_function();')
    # 薄叶背面仍可接收天空；沿用原透光遮罩，树干不会被统一加亮。
    indirect = 'color.rgb += (ibl_kd * ibl_diff  + ibl_spec) * ambient_occlusion;'
    fragment = fragment.replace(indirect, indirect + '''
    if (local_sky_transmission > 0.) {
        vec3 opposite_sky = local_opposite_sky(world_normal,local_sky_irradiance);
        color.rgb += opposite_sky*base_color.rgb*local_transmittance_color
                   *texture(local_transmission,v_texcoord).r*local_back_diffuse
                   *diffuse_function()*ambient_occlusion*local_sky_transmission;
    }
''')
    return Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex), fragment)


def landscape_lighting(scene, scale=.65):
    """晴空间接光不再与常量环境灯重复相加；保留原天空与同一太阳。"""
    source = scene.expressway_kit['daylight-environment'].sh_coefficients
    coefficients = PTALVecBase3f.emptyArray(9)
    for i in range(9):
        coefficients[i] = source[i] * scale
    scene.render.setShaderInput('sh_coeffs', coefficients)
    scene.ambient_path.node().setColor((.015, .02, .025, 1))


def source_texture(path, *, color=False):
    texture = Texture(path.stem)
    if not texture.read(Filename.fromOsSpecific(str(path))):
        raise OSError('无法读取KCD本地材质：' + str(path))
    if color:
        texture.setFormat(Texture.FSrgb)
    texture.setMinfilter(Texture.FTLinearMipmapLinear)
    texture.setAnisotropicDegree(8)
    return texture


def load_environment(kit, parent, folder):
    from zipfile import ZipFile

    from kcd_local_assets import INSTALL
    from prepare_kcd_environment import prepare_surface

    parameters = json.loads((folder / 'original-environment.json').read_text(encoding='utf-8'))
    if not (folder / 'driving-meadow-source.json').is_file():
        with ZipFile(INSTALL / 'IPL_Textures-part1.pak') as package:
            sources = [prepare_surface(package, folder, 'meadow-b',
                                      'Textures/terrain/grass/grass_pasture_b_2x2',1024,'.5','.4'),
                       prepare_surface(package, folder, 'dry',
                                      'Textures/terrain/grass/grass_dry_trampled_2x2',1024,'.5','.4')]
        (folder / 'driving-meadow-source.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    kit['ground'] = source_texture(folder / 'pasture-albedo.png', color=True)
    parent.setShaderInput('local_ground_meadow', kit['ground'])
    parent.setShaderInput('local_ground_dry', source_texture(folder / 'dry-albedo.png', color=True))
    parent.setShaderInput('local_origin_y', 0.)
    parent.setShaderInput('city_lawn_phase', (0., 0.))
    for layer in ('pasture', 'forest'):
        for channel in ('normal', 'gloss', 'height', 'albedo'):
            if layer == 'pasture' and channel == 'albedo':
                continue
            texture = source_texture(folder / (layer + '-' + channel + '.png'), color=channel == 'albedo')
            parent.setShaderInput(layer + '_' + channel, texture)
    for channel in ('normal', 'gloss', 'height'):
        parent.setShaderInput('dry_' + channel, source_texture(folder / ('dry-' + channel + '.png')))
    original = kit['route-terrain-shader']
    fragment = original.getText(Shader.STFragment)
    start = fragment.index('uniform sampler2D expressway_rock;')
    end = fragment.index('\n}\n', start) + 3
    fragment = fragment[:start] + MATERIAL + fragment[end:]
    fragment = fragment.replace('p3d_Material.roughness * metal_rough.g', 'kcd_roughness()')
    # 土壤与短草是粗糙漫反射表面，默认掠射环境高光会把整个中距离草坡漂白。
    fragment = fragment.replace('vec3 ibl_f = fresnelSchlickRoughness(n_dot_v, spec_color, perceptual_roughness);',
                                'vec3 ibl_f = mix(spec_color, '
                                'fresnelSchlickRoughness(n_dot_v, spec_color, perceptual_roughness), .1);')
    fragment = fragment.replace('ibl_f * env_brdf.x + env_brdf.y',
                                'ibl_f * env_brdf.x + env_brdf.y*.1')
    fragment = fragment.replace('normalize(v_view_tbn * normalmap)', 'kcd_normal(v_view_tbn[2],v_view_position)')
    fragment = fragment.replace('normalize(v_world_tbn * normalmap)', 'kcd_normal(v_world_tbn[2],v_world_position)')
    kit['route-terrain-shader'] = Shader.make(Shader.SLGLSL, original.getText(Shader.STVertex), fragment)
    # 环境探针包含原关卡的地面，供照明与反射使用；可见天空继续使用已认可的晴空。
    kit['daylight-environment'] = EnvMap.from_file_path(folder / 'original-pasture-pbr.env')
    return parameters


def load_daylight(kit, folder):
    """新晴空与反射/天空漫反射用同一实拍，原件植被和地表材质继续保留。"""
    metadata = json.loads((folder / 'daylight-manifest.json').read_text(encoding='utf-8'))
    sky = source_texture(folder / 'daylight-sky.hdr')
    sky.setFormat(Texture.FRgb16)
    sky.setWrapU(Texture.WMRepeat)
    sky.setWrapV(Texture.WMClamp)
    kit['sky'] = sky
    kit['daylight-metadata'] = metadata
    kit['daylight-environment'] = EnvMap.from_file_path(folder / 'daylight.env')


def sun_color(parameters):
    # CryEngine先adjust_luminance；其BRDF外除PI，simplepbr已在Lambert项内除PI。
    rgb = tuple(float(v) for v in parameters['sun_color'].split(','))
    luminance = sum(v * w for v, w in zip(rgb, (.2126, .7152, .0722), strict=True))
    scale = float(parameters['sun_lux']) / (10000 * luminance)
    return tuple(v * scale for v in rgb) + (1.,)


def source_sun(scene, position, parameters, *, intensity=.8):
    direction = Vec3(*(float(v) for v in parameters['lighting']['SunVector'].split(',')))
    offset = -direction * 360.0
    sun = scene.sun_path
    sun.setPos(offset)
    sun.lookAt(0, 0, 0)
    inverse = sun.getQuat().conjugate()
    origin = float(scene.base.session.render_origin())
    current_origin = scene.render.getShaderInput('local_origin_y')
    if current_origin.getValueType() == current_origin.MInvalid or current_origin.getVector().x != origin:
        scene.render.setShaderInput('local_origin_y', origin)
    # 跟车相机就绪后使用已平滑的相机朝向，避免未插值物理朝向跳动令前置阴影中心剧烈摆动。
    chase = scene.base.chase_camera
    heading = math.radians(chase.heading if chase.position is not None else scene.base.session.current.player.heading)
    center = position + Vec3(-math.sin(heading), math.cos(heading), 0) * CANOPY_SHADOW_LEAD
    light_position = inverse.xform(center + offset + Vec3(0, origin, 0))
    lens, resolution = sun.node().getLens(), sun.node().getShadowBufferSize()
    # 仅光平面 XY 按阴影纹素对齐，深度轴保持连续，消除 0.5m 阶跃跳变导致的阴影呼吸闪烁。
    for axis, step in ((0, lens.getFilmSize().x / resolution.x),
                       (2, lens.getFilmSize().y / resolution.y)):
        light_position[axis] = round(light_position[axis] / step) * step
    sun.setPos(sun.getQuat().xform(light_position) - Vec3(0, origin, 0))
    # 原探针与本项目晴空/相机的曝光口径不同；按正常驾驶的中性地表平衡直射光。
    original_color = sun_color(parameters)
    color = tuple(v * intensity for v in original_color[:3]) + (1.,)
    sun.node().setColor(color)
    scene.rail_sun_path.node().setColor(color)
    scene.rail_sun_path.setTransform(sun.getTransform())


def source_rail_shadow(curve, distance, lateral, parameters, height=0):
    vector = tuple(float(v) for v in parameters['lighting']['SunVector'].split(','))
    x, y = vector[0] / -vector[2], vector[1] / -vector[2]
    pose = curve.sample(distance) if curve else None
    heading, grade = (math.radians(pose.heading), math.radians(pose.grade)) if pose else (0., 0.)
    forward = -x * math.sin(heading) + y * math.cos(heading)
    cross = x * math.cos(heading) + y * math.sin(heading)
    return lateral, max(0, .8 - height) * cross / (1 + math.tan(grade) * forward)
