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


def terrain_shader():
    """仅扩展固定版本PBR的底色取样，继续使用原有灯光、阴影与后处理。"""
    from simplepbr._shaderutils import _load_shader_str

    defines = {"MAX_LIGHTS": 8, "ENABLE_SHADOWS": True, "USE_330": True}
    vertex = _load_shader_str("simplepbr.vert", defines.copy())
    fragment = _load_shader_str("simplepbr.frag", defines.copy())
    original = ("p3d_Material.baseColor * v_color * p3d_ColorScale * "
                "(texture2D(p3d_TextureBaseColor, v_texcoord) + p3d_TexAlphaOnly)")
    if fragment.count(original) != 1:
        raise RuntimeError("高速地表材质需要已锁定的simplepbr 0.13.1底色接口")
    addition = Path(shader_path("terrain-material.frag").toOsSpecific()).read_text(encoding="utf-8")
    fragment = fragment.replace("void main() {", addition + "\nvoid main() {")
    fragment = fragment.replace(original, "expressway_albedo() * p3d_ColorScale")
    return Shader.make(Shader.SLGLSL, vertex, fragment)
