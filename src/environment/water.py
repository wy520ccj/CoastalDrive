"""低成本海面表现，时间只来自快照，不增加物理水体。"""

from panda3d.core import Shader, Texture, TexturePool

from environment.foundation import asset_path


def style_water(node):
    shader = Shader.load(
        Shader.SLGLSL, asset_path("shaders/water.vert"), asset_path("shaders/water.frag")
    )
    if shader is None:
        raise RuntimeError("海面 shader 加载失败")
    node.setShader(shader, 2)
    node.setShaderInput("sea_time", 0.0)
    distance = TexturePool.loadTexture(asset_path("materials/shore-distance.png"))
    distance.setWrapU(Texture.WMClamp)
    distance.setWrapV(Texture.WMClamp)
    node.setShaderInput("shore_distance", distance)
