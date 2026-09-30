"""快速路独立的晴空、路堑表面和海湾材质。"""

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


def style_sky(sky, loader):
    image = texture("expressway-sky")
    image.setWrapV(Texture.WMClamp)
    sky.setTexture(image, 2)
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
    return {"ground": texture("grass-albedo"), "rock": texture("strata-albedo"),
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


def road_shadow_shader():
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
        # 固定屏幕覆盖图样不随时间随机抖动，保持不透明深度和原材质照明。
        fade = """
    float coverage = 1.0 - smoothstep(430.0, 560.0,
                                     length(v_world_position - camera_world_position));
    expressway_dither(coverage);
"""
        fragment = fragment.replace("void main() {", "void main() {\n" + fade)
    return Shader.make(Shader.SLGLSL, vertex, fragment)


def route_water_shader():
    vertex = Path(shader_path("route-water.vert").toOsSpecific()).read_text(encoding="utf-8")
    fragment = Path(shader_path("route-water.frag").toOsSpecific()).read_text(encoding="utf-8")
    addition = Path(shader_path("distance-haze.glsl").toOsSpecific()).read_text(encoding="utf-8")
    fragment = fragment.replace("void main() {", addition +
                                "\nvoid main() {\nexpressway_far_clip(v_world_position);")
    return Shader.make(Shader.SLGLSL, vertex, fragment)
