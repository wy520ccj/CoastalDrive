"""滨海光色和表面材质；其他赛道沿用原配置。"""

from functools import lru_cache
from pathlib import Path

from panda3d.core import (
    Filename,
    Material,
    MaterialAttrib,
    PTALVecBase3f,
    Shader,
    Texture,
    TexturePool,
    Vec3,
)

from paths import resource_root

AMBIENT = (0.30, 0.39, 0.47, 1)
SUN = (2.65, 2.37, 1.86, 1)
HAZE = (0.57, 0.76, 0.84)
FOG_DENSITY = 0.00125
SURFACES = {
    "road": (0.065, 0.079, 0.094, 1),
    "inner-shoulder": (0.60, 0.48, 0.29, 1),
    "outer-shoulder": (0.60, 0.48, 0.29, 1),
    "island": (0.18, 0.29, 0.065, 1),
    "cliff": (0.69, 0.56, 0.38, 1),
    "inner-rail": (0.84, 0.84, 0.72, 1),
    "outer-rail": (0.84, 0.84, 0.72, 1),
}

PROP_COLORS = {
    "woodBarkDark": (0.20, 0.12, 0.06, 1),
    "leafsDark": (0.10, 0.26, 0.09, 1),
    "dirt": (0.48, 0.43, 0.32, 1),
    "grass": (0.22, 0.33, 0.12, 1),
}


def asset_path(relative):
    path = resource_root() / "assets/game/environment" / relative
    if not path.is_file():
        raise FileNotFoundError(f"缺少海岸环境资产：{path}")
    return Filename.fromOsSpecific(str(path))


@lru_cache(maxsize=4)
def texture(name):
    result = TexturePool.loadTexture(asset_path(f"materials/{name}.png"))
    result.setWrapU(Texture.WMRepeat)
    result.setWrapV(Texture.WMRepeat)
    result.setMinfilter(Texture.FTLinearMipmapLinear)
    result.setAnisotropicDegree(8)
    return result


def apply_surface(node, name):
    material = Material(f"coastal-{name}")
    material.setBaseColor((1, 1, 1, 1))
    material.setMetallic(0)
    material.setRoughness(0.94 if name != "road" else 0.87)
    node.setMaterial(material, 1)
    if name == "road":
        from environment.expressway_materials import lab_asphalt_shader, photographed_surface

        # 原顶点色仅适用于平色路面；改为中性白让实拍底色决定路面亮度。
        node.setColor(1, 1, 1, 1)
        node.setTexture(photographed_surface('asphalt_03_diff_2k.jpg', color=True), 1)
        node.setShader(coastal_shadow_shader(lab_asphalt_shader()), 2)
        node.setShaderInput('asphalt_normals', photographed_surface('asphalt_03_nor_gl_2k.jpg'))
        node.setShaderInput('asphalt_roughness', photographed_surface('asphalt_03_rough_2k.jpg'))
    elif name == "island":
        node.setTexture(texture("meadow"), 1)
    elif name == "cliff" or "shoulder" in name:
        node.setTexture(texture("limestone"), 1)


@lru_cache(maxsize=1)
def coastal_ground_shader():
    """同一PBR通道加入米制地表细节，原投影和环境照明保持。"""
    from simplepbr._shaderutils import _load_shader_str

    defines = {'MAX_LIGHTS': 1, 'ENABLE_SHADOWS': True, 'USE_330': True}
    vertex = _load_shader_str('simplepbr.vert', defines.copy())
    fragment = _load_shader_str('simplepbr.frag', defines.copy())
    detail = asset_path('shaders/ground-material.glsl').toOsSpecific()
    fragment = fragment.replace('void main() {', Path(detail).read_text(encoding='utf-8') +
        '\nvoid main() {\nvec3 coastal_detail = texture(coastal_ground_normals, coastal_ground_uv()).rgb*2.-1.;')
    base = ('p3d_Material.baseColor * v_color * p3d_ColorScale * '
            '(texture2D(p3d_TextureBaseColor, v_texcoord) + p3d_TexAlphaOnly)')
    if fragment.count(base) != 1:
        raise RuntimeError('海岸地表需要固定simplepbr底色接口')
    fragment = fragment.replace(base, 'coastal_ground_color() * p3d_ColorScale')
    fragment = fragment.replace('p3d_Material.roughness * metal_rough.g',
        'max(0.75, texture(coastal_ground_roughness, coastal_ground_uv()).r)')
    fragment = fragment.replace('normalize(v_view_tbn * normalmap)',
        'coastal_ground_normal(v_view_tbn[2], v_view_position, coastal_detail)')
    fragment = fragment.replace('normalize(v_world_tbn * normalmap)',
        'coastal_ground_normal(v_world_tbn[2], v_world_position, coastal_detail)')
    return coastal_shadow_shader(Shader.make(Shader.SLGLSL, vertex, fragment))


def style_ground(root):
    """只改变原岛内地表，不给草片/礁石误套草地法线。"""
    from environment.expressway_materials import photographed_surface

    inland = root.find('**/inland/+GeomNode')
    inland.setShader(coastal_ground_shader(), 2)
    inland.setShaderInput('coastal_ground_albedo', photographed_surface('leafy_grass_diff_2k.jpg', color=True))
    inland.setShaderInput('coastal_ground_normals', photographed_surface('leafy_grass_nor_gl_2k.jpg'))
    inland.setShaderInput('coastal_ground_roughness', photographed_surface('leafy_grass_rough_2k.jpg'))


def setup_daylight(scene):
    """滨海及沿海生涯共用落日光照，输入只属于当前Scene。"""
    from environment.expressway_materials import daylight_assets, style_sky
    from vehicle_visual import set_vehicle_reflection

    sky, environment, metadata = daylight_assets(resource_root()/'assets/game/environment/coastal-sunset')
    scene.coastal_daylight = metadata
    if scene.base.session.simulation.track == 'coastal':
        scene.render.setShader(coastal_shadow_shader(scene.base.render.getShader()))
    else:
        # 流送地区保留原距离阴影和空气透视，不另加固定滨海接收滤波。
        scene.expressway_kit.update({'sky': sky, 'daylight-environment': environment,
                                    'daylight-metadata': metadata})
        scene.render.setShaderInput('expressway_sky_tint', Vec3(*metadata['sky_tint']))
    scene.base.pipeline.exposure = metadata['exposure_ev']
    style_sky(scene.sky, {'sky': sky, 'daylight-metadata': metadata})
    from environment.expressway_materials import shader_path

    scene.sky.setShader(Shader.load(Shader.SLGLSL, shader_path('sky.vert'),
                                   asset_path('shaders/sunset-sky.frag')), 2)
    scene.sky.setShaderInput('coastal_sky_tint',Vec3(*metadata['sky_tint']))
    coefficients = PTALVecBase3f.emptyArray(9)
    scale = metadata['career_sky_diffuse_scale'] if scene.base.session.simulation.track == 'endless' else metadata['sky_diffuse_scale']
    for index in range(9):
        coefficients[index] = environment.sh_coefficients[index]*scale
    scene.render.setShaderInput('sh_coeffs', coefficients)
    color = tuple(v*metadata['direct_sun_scale'] for v in metadata['direct_sun_color'])+(1.,)
    scene.sun_path.node().setColor(color)
    scene.rail_sun_path.node().setColor(color)
    scene.render.setShaderInput('coastal_sun_direction', Vec3(*metadata['directional_sun']))
    scene.render.setShaderInput('coastal_sun_color', Vec3(*color[:3]))
    set_vehicle_reflection(scene.render, environment)
    for part in (scene.player, *scene.wheels, *scene.traffic, *(wheel for row in scene.traffic_wheels for wheel in row)):
        set_vehicle_reflection(part, environment)
    scene.ambient_path.node().setColor((.04, .055, .075, 1))
    scene.sun_path.node().setShadowCaster(True, 4096, 4096)
    scene.render.setShaderInput('coastal_shadow_texel', (1/4096, 1/4096))
    scene.update_lighting(scene.player.getPos())


@lru_cache(maxsize=4)
def coastal_shadow_shader(source):
    """低角度光照沿用原深度比较，仅对边缘做固定3×3帐篷采样。"""
    fragment = source.getText(Shader.STFragment)
    sample = 'texture(shadowmap,coordinate)' if '#version 330' in fragment else 'shadow2D(shadowmap,coordinate).r'
    start = fragment.index('float shadow_caster_contrib(')
    end = fragment.index('\n}', start)+2
    fragment = fragment[:start]+'''
uniform vec2 coastal_shadow_texel;
float shadow_caster_contrib(sampler2DShadow shadowmap, vec4 shadowpos) {
    vec3 p = shadowpos.xyz/shadowpos.w;
    if (any(lessThan(p,vec3(0.))) || any(greaterThan(p,vec3(1.)))) return 1.;
    p.z -= global_shadow_bias;
    float filtered = 0.;
    for (int y=-1; y<=1; y++) for (int x=-1; x<=1; x++) {
        float weight = (x==0 ? 2. : 1.)*(y==0 ? 2. : 1.);
        vec3 coordinate = vec3(p.xy+vec2(x,y)*coastal_shadow_texel,p.z);
        filtered += weight*SHADOW_SAMPLE;
    }
    return filtered/16.;
}'''.replace('SHADOW_SAMPLE', sample)+fragment[end:]
    return Shader.make(Shader.SLGLSL, source.getText(Shader.STVertex), fragment)


def update_daylight(scene, position):
    """固定太阳方向，沿投影纹素格跟车；不让移动相机改变天空朝向。"""
    lens, size = scene.sun_path.node().getLens(), scene.sun_path.node().getShadowBufferSize()
    distance = 360.0 if lens.getFar() > 400.0 else 156.25
    offset = Vec3(*scene.coastal_daylight['directional_sun']) * distance
    sun = scene.sun_path
    sun.setPos(offset)
    sun.lookAt(0, 0, 0)
    inverse = sun.getQuat().conjugate()
    origin = Vec3(0, scene.base.session.render_origin(), 0)
    light_position = inverse.xform(position+offset+origin)
    if size.x > 0 and size.y > 0:
        for axis, step in ((0, lens.getFilmSize().x/size.x), (2, lens.getFilmSize().y/size.y)):
            light_position[axis] = round(light_position[axis]/step)*step
    sun.setPos(sun.getQuat().xform(light_position)-origin)


def style_existing_prop(root):
    """统一既有 Kenney 树石的材质，保留碰撞物对应的全部几何与变换。"""
    for path in root.findAllMatches("**/+GeomNode"):
        node = path.node()
        for index in range(node.getNumGeoms()):
            state = node.getGeomState(index)
            original = state.getAttrib(MaterialAttrib).getMaterial()
            material = Material(original)
            material.setBaseColor(PROP_COLORS[original.getName()])
            material.setMetallic(0)
            material.setRoughness(0.95)
            node.setGeomState(index, state.setAttrib(MaterialAttrib.make(material)))
