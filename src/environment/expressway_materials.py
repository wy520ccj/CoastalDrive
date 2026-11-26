"""快速路独立的晴空、路堑表面和海湾材质。"""

import json
from functools import lru_cache
from pathlib import Path

from panda3d.core import Filename, Shader, Texture, TexturePool

from paths import resource_root


def shader_path(name):
    path = resource_root() / "assets/game/expressway/shaders" / name
    if not path.is_file():
        raise FileNotFoundError(f"缺少高速材质：{path}")
    return Filename.fromOsSpecific(str(path))


def texture(name):
    path = resource_root() / "assets/game/expressway" / f"{name}.png"
    result = TexturePool.loadTexture(Filename.fromOsSpecific(str(path)))
    if result is None:
        raise FileNotFoundError(f"缺少高速表面：{path}")
    result.setWrapU(Texture.WMRepeat)
    result.setWrapV(Texture.WMRepeat)
    result.setMinfilter(Texture.FTLinearMipmapLinear)
    result.setAnisotropicDegree(8)
    return result


def photographed_surface(name, *, color=False):
    """有来源的实拍材质；底色用sRGB，法线/粗糙度保持线性数据。"""
    path = resource_root() / 'assets/game/materials' / name
    result = Texture(path.stem)
    if not result.read(Filename.fromOsSpecific(str(path))):
        raise OSError(f'无法读取道路实拍材质：{path}')
    if color:
        result.setFormat(Texture.FSrgb)
    result.setWrapU(Texture.WMRepeat)
    result.setWrapV(Texture.WMRepeat)
    result.setMinfilter(Texture.FTLinearMipmapLinear)
    result.setAnisotropicDegree(8)
    return result


@lru_cache(maxsize=1)
def lab_asphalt_shader():
    """实验地面沿用道路的米制实拍法线/粗糙度，不引入道路护栏或远景输入。"""
    from simplepbr._shaderutils import _load_shader_str

    defines = {'MAX_LIGHTS': 1, 'ENABLE_SHADOWS': True, 'USE_330': True}
    vertex = _load_shader_str('simplepbr.vert', defines.copy())
    fragment = _load_shader_str('simplepbr.frag', defines.copy())
    detail = Path(shader_path('asphalt-material.glsl').toOsSpecific()).read_text(encoding='utf-8')
    fragment = fragment.replace('void main() {', detail+'\nvoid main() {')
    fragment = fragment.replace('(texture2D(p3d_TextureBaseColor, v_texcoord) + p3d_TexAlphaOnly)',
                                'asphalt_color()')
    fragment = fragment.replace('p3d_Material.roughness * metal_rough.g',
                                'asphalt_roughness_value()')
    fragment = fragment.replace('normalize(v_view_tbn * normalmap)',
                                'asphalt_normal(v_view_tbn[2], v_view_position)')
    fragment = fragment.replace('normalize(v_world_tbn * normalmap)',
                                'asphalt_normal(v_world_tbn[2], v_world_position)')
    return Shader.make(Shader.SLGLSL, vertex, fragment)


@lru_cache(maxsize=1)
def city_asphalt_shader():
    """街区柏油路面使用同源实拍沥青并接入高速远景雾化与 1050m 裁剪。"""
    from simplepbr._shaderutils import _load_shader_str

    defines = {'MAX_LIGHTS': 1, 'ENABLE_SHADOWS': True, 'USE_330': True}
    vertex = _load_shader_str('simplepbr.vert', defines.copy())
    fragment = _load_shader_str('simplepbr.frag', defines.copy())
    detail = Path(shader_path('asphalt-material.glsl').toOsSpecific()).read_text(encoding='utf-8')
    fragment = fragment.replace('void main() {', detail+'\nvoid main() {')
    fragment = fragment.replace('(texture2D(p3d_TextureBaseColor, v_texcoord) + p3d_TexAlphaOnly)',
                                'asphalt_color()')
    fragment = fragment.replace('p3d_Material.roughness * metal_rough.g',
                                'asphalt_roughness_value()')
    fragment = fragment.replace('normalize(v_view_tbn * normalmap)',
                                'asphalt_normal(v_view_tbn[2], v_view_position)')
    fragment = fragment.replace('normalize(v_world_tbn * normalmap)',
                                'asphalt_normal(v_world_tbn[2], v_world_position)')
    return Shader.make(Shader.SLGLSL, vertex, add_distance_haze(add_shadow_transition(fragment)))


@lru_cache(maxsize=1)
def city_plaster_shader():
    """住宅灰泥与石墙共用原PBR照明，分别绑定米制尺度与表面强度。"""
    from simplepbr._shaderutils import _load_shader_str

    defines = {'MAX_LIGHTS': 1, 'ENABLE_SHADOWS': True, 'USE_330': True}
    vertex = _load_shader_str('simplepbr.vert', defines.copy())
    fragment = add_shadow_transition(_load_shader_str('simplepbr.frag', defines.copy()))
    detail = Path(shader_path('city-plaster.glsl').toOsSpecific()).read_text(encoding='utf-8')
    fragment = fragment.replace('void main() {', detail+'\nvoid main() {')
    fragment = fragment.replace('(texture2D(p3d_TextureBaseColor, v_texcoord) + p3d_TexAlphaOnly)',
                                'city_plaster_color()')
    fragment = fragment.replace('p3d_Material.roughness * metal_rough.g',
                                'max(0.7, texture2D(city_roughness, v_texcoord*city_tex_scale).r)')
    fragment = fragment.replace('normalize(v_view_tbn * normalmap)',
                                'city_surface_normal(v_view_tbn[2], v_view_position)')
    fragment = fragment.replace('normalize(v_world_tbn * normalmap)',
                                'city_surface_normal(v_world_tbn[2], v_world_position)')
    return Shader.make(Shader.SLGLSL, vertex, fragment)


@lru_cache(maxsize=2)
def daylight_assets(folder=None):
    """天空、空气透视和照明共用同一实拍；源图是线性HDR，不能再按sRGB解码。"""
    folder = resource_root()/'assets/game/expressway' if folder is None else folder
    environment, metadata = daylight_environment(folder)
    sky_name = metadata.get('sky_file', 'daylight-sky.hdr')
    for name in (sky_name, 'daylight.env', 'daylight-manifest.json'):
        if not (folder/name).is_file():
            raise FileNotFoundError(f'缺少晴天环境资源：{folder/name}')
    sky = Texture('coastal-daylight-sky')
    if not sky.read(Filename.fromOsSpecific(str(folder/sky_name))):
        raise OSError('无法读取晴天HDR天空')
    sky.setFormat(Texture.FRgb16)
    sky.setWrapU(Texture.WMRepeat)
    sky.setWrapV(Texture.WMClamp)
    sky.setMinfilter(Texture.FTLinearMipmapLinear)
    sky.setAnisotropicDegree(4)
    return sky, environment, metadata


@lru_cache(maxsize=2)
def daylight_environment(folder):
    """共用离线过滤环境；仅需照明的视窗不重复读取整张HDR天空。"""
    from simplepbr.envmap import EnvMap

    for name in ('daylight.env', 'daylight-manifest.json'):
        if not (folder/name).is_file():
            raise FileNotFoundError(f'缺少晴天照明资源：{folder/name}')
    environment = EnvMap.from_file_path(Filename.fromOsSpecific(str(folder/'daylight.env')))
    metadata = json.loads((folder/'daylight-manifest.json').read_text(encoding='utf-8'))
    return environment, metadata


def style_sky(sky, kit):
    sky.setTexture(kit['sky'], 2)
    sky.setH(kit['daylight-metadata']['sky_heading_degrees'])
    sky.setShader(Shader.load(Shader.SLGLSL, shader_path("sky.vert"),
                             shader_path("sky.frag")), 2)


def style_water(water):
    water.setShader(Shader.load(Shader.SLGLSL, shader_path("water.vert"),
                               shader_path("bay.frag")), 2)
    path = resource_root() / "assets/game/expressway/shore-profile.png"
    profile = TexturePool.loadTexture(Filename.fromOsSpecific(str(path)))
    if profile is None:
        raise FileNotFoundError(f"缺少高速岸线：{path}")
    profile.setWrapU(Texture.WMClamp)
    profile.setWrapV(Texture.WMClamp)
    water.setShaderInput("shore_profile", profile)
    water.setShaderInput("sea_time", 0.0)
    water.setShaderInput("origin_y", 0.0)


def surface_textures():
    return {"ground": photographed_surface('leafy_grass_diff_2k.jpg', color=True), "rock": texture("strata-albedo"),
            "asphalt": texture("aggregate")}


def terrain_shader(name="terrain-material.frag"):
    """仅扩展固定版本PBR的底色取样，继续使用原有灯光、阴影与后处理。"""
    from simplepbr._shaderutils import _load_shader_str

    # 高速每个表面只接收一个太阳光，环境光不占PBR直射光槽。
    defines = {"MAX_LIGHTS": 1, "ENABLE_SHADOWS": True, "USE_330": True}
    vertex = _load_shader_str("simplepbr.vert", defines.copy())
    fragment = _load_shader_str("simplepbr.frag", defines.copy())
    original = ("p3d_Material.baseColor * v_color * p3d_ColorScale * "
                "(texture2D(p3d_TextureBaseColor, v_texcoord) + p3d_TexAlphaOnly)")
    if fragment.count(original) != 1:
        raise RuntimeError("高速地表材质需要已锁定的simplepbr 0.13.1底色接口")
    addition = Path(shader_path(name).toOsSpecific()).read_text(encoding="utf-8")
    fragment = fragment.replace("void main() {", addition + "\nvoid main() {")
    fragment = fragment.replace(original, "expressway_albedo() * p3d_ColorScale")
    return Shader.make(Shader.SLGLSL, vertex, add_distance_haze(add_shadow_transition(fragment)))


def road_shadow_shader(*, asphalt=False):
    """固定护栏遮蔽跨越实时阴影范围，车辆与设施仍使用原有PCF投影。"""
    from simplepbr._shaderutils import _load_shader_str

    defines = {"MAX_LIGHTS": 1, "ENABLE_SHADOWS": True, "USE_330": True}
    vertex = _load_shader_str("simplepbr.vert", defines.copy())
    vertex = vertex.replace("void main() {", "in vec2 rail_shadow_coord;\n"
                            "out vec2 v_rail_shadow_coord;\nvoid main() {\n"
                            "v_rail_shadow_coord = rail_shadow_coord;")
    fragment = _load_shader_str("simplepbr.frag", defines.copy())
    start = fragment.index("float shadow_caster_contrib(")
    end = fragment.index("\n}\n", start) + 3
    addition = Path(shader_path("road-shadow.frag").toOsSpecific()).read_text(encoding="utf-8")
    fragment = fragment[:start] + addition + fragment[end:]
    fragment = fragment.replace("float shadow = shadowSpot * shadow_caster * attenuation_factor;",
                                "float shadow = shadowSpot * min(shadow_caster, "
                                "expressway_rail_shadow()) * attenuation_factor;")
    if asphalt:
        detail = Path(shader_path('asphalt-material.glsl').toOsSpecific()).read_text(encoding='utf-8')
        fragment = fragment.replace('void main() {', detail+'\nvoid main() {')
        fragment = fragment.replace('(texture2D(p3d_TextureBaseColor, v_texcoord) + p3d_TexAlphaOnly)',
                                    'asphalt_color()')
        fragment = fragment.replace('p3d_Material.roughness * metal_rough.g',
            'asphalt_roughness_value()')
        fragment = fragment.replace('normalize(v_view_tbn * normalmap)',
            'asphalt_normal(v_view_tbn[2], v_view_position)')
        fragment = fragment.replace('normalize(v_world_tbn * normalmap)',
            'asphalt_normal(v_world_tbn[2], v_world_position)')
    return Shader.make(Shader.SLGLSL, vertex, add_distance_haze(fragment))


def add_distance_haze(fragment):
    """同一天空辐亮度覆盖所有高速表面，近350m不改变颜色。"""
    addition = Path(shader_path("distance-haze.glsl").toOsSpecific()).read_text(encoding="utf-8")
    fragment = fragment.replace("void main() {", addition +
                                "\nvoid main() {\nexpressway_far_clip(v_world_position);")
    return fragment.replace("o_color = color;",
                            "o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);")


def add_shadow_transition(fragment):
    """原生阴影采样仅在覆盖边缘混合，不改中心区强度或固定护栏遮蔽。"""
    start = fragment.index("float shadow_caster_contrib(")
    end = fragment.index("\n}\n", start) + 3
    addition = Path(shader_path("shadow-transition.glsl").toOsSpecific()).read_text(encoding="utf-8")
    return fragment[:start] + addition + fragment[end:]


def distance_shader(*, details=False):
    from simplepbr._shaderutils import _load_shader_str

    defines = {"MAX_LIGHTS": 1, "ENABLE_SHADOWS": True, "USE_330": True}
    vertex = _load_shader_str("simplepbr.vert", defines.copy())
    fragment = add_distance_haze(add_shadow_transition(_load_shader_str("simplepbr.frag", defines.copy())))
    if details:
        # 780m 分组裁剪前在 560-680m 平滑并入同一天空辐亮度，绝不打棋盘孔洞。
        target = "o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);"
        replacement = (
            "vec3 expressway_detail_dir = v_world_position - camera_world_position;\n"
            "    float expressway_detail_fade = smoothstep(560.0, 680.0, length(expressway_detail_dir));\n"
            "    vec3 expressway_detail_color = expressway_haze(color.rgb, v_world_position);\n"
            "    if (expressway_detail_fade > 0.0) {\n"
            "        expressway_detail_color = mix(expressway_detail_color, "
            "expressway_sky_radiance(expressway_detail_dir), expressway_detail_fade);\n"
            "    }\n"
            "    o_color = vec4(expressway_detail_color, color.a);"
        )
        assert target in fragment
        fragment = fragment.replace(target, replacement)
    return Shader.make(Shader.SLGLSL, vertex, fragment)


def foliage_shader():
    """薄叶使用源遮罩和双面透光近似，仍接受同一太阳/阴影/空气透视。"""
    from simplepbr._shaderutils import _load_shader_str

    defines = {'MAX_LIGHTS': 1, 'ENABLE_SHADOWS': True, 'USE_330': True}
    vertex = _load_shader_str('simplepbr.vert', defines.copy())
    fragment = add_distance_haze(add_shadow_transition(_load_shader_str('simplepbr.frag', defines.copy())))
    fragment = fragment.replace('void main() {', 'uniform float foliage_alpha_cutoff;\nvoid main() {')
    fragment = fragment.replace('vec3 diffuse_color =',
        'if (base_color.a < foliage_alpha_cutoff) discard;\n    vec3 diffuse_color =')
    fragment = fragment.replace('func_params.n_dot_l = clamp(dot(n, l), 0.0, 1.0);',
        'float nl = dot(n, l);\n        func_params.n_dot_l = max(nl, 0.0) + max(-nl, 0.0)*0.35;')
    return Shader.make(Shader.SLGLSL, vertex, fragment)


def route_water_shader():
    vertex = Path(shader_path("route-water.vert").toOsSpecific()).read_text(encoding="utf-8")
    fragment = Path(shader_path("route-water.frag").toOsSpecific()).read_text(encoding="utf-8")
    addition = Path(shader_path("distance-haze.glsl").toOsSpecific()).read_text(encoding="utf-8")
    fragment = fragment.replace("void main() {", addition +
                                "\nvoid main() {\nexpressway_far_clip(v_world_position);")
    return Shader.make(Shader.SLGLSL, vertex, fragment)
