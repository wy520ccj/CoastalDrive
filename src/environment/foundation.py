"""滨海光色和表面材质；其他赛道沿用原配置。"""

from functools import lru_cache

from panda3d.core import Filename, Material, MaterialAttrib, Texture, TexturePool

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
        node.setTexture(texture("asphalt"), 1)
    elif name == "island":
        node.setTexture(texture("meadow"), 1)
    elif name == "cliff" or "shoulder" in name:
        node.setTexture(texture("limestone"), 1)


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
