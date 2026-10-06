"""道路与车库共用的车身外廓、轮宽轮径及轮位装配。"""

from functools import lru_cache

import gltf
from panda3d.core import AmbientLight, Filename, LightAttrib, Loader, NodePath, Vec3
from simplepbr.envmap import EnvMap

from paths import resource_root
from skins import VehicleDefinition
from vehicle_config import body_center, wheel_hubs
from vehicle_designs import vehicle_design

WHEEL_NAMES = ("wheel-front-left", "wheel-front-right", "wheel-back-left", "wheel-back-right")


def load_vehicle(parent, definition: VehicleDefinition, *, trace=None, config=None):
    """按统一车型定义装配显示车；调用方身份不参与资产选择。"""
    if config is None:
        config = vehicle_design(definition.physics_id).config
    path = resource_root() / "assets/game" / definition.visual
    if path.suffix == ".glb":
        return load_gltf_vehicle(parent, definition, path, trace=trace, config=config)

    root = parent.attachNewNode(definition.id)
    body = NodePath(Loader.getGlobalPtr().loadSync(Filename.fromOsSpecific(str(path))))
    body.reparentTo(root)
    body.setH(180)
    wheels = []
    for name, hub in zip(WHEEL_NAMES, wheel_hubs(config)):
        wheel = body.find(f"**/{name}")
        mesh = wheel.getChild(0)
        mesh.setH(180)
        pivot = fit_wheel(parent, mesh, name, hub, config)
        wheels.append(pivot)
        wheel.removeNode()
    body.setScale(*definition.body_scale)
    body.setZ(-0.48)
    fit_body(body, root, config)
    return root, wheels


def load_gltf_vehicle(parent, definition, path, *, trace=None, config):
    """米制 GLB 共用 Snapshot 的四个世界轮姿。"""
    root = parent.attachNewNode(definition.id)
    body = NodePath(gltf.load_model(Filename.fromOsSpecific(str(path))))
    body.setPythonTag("vehicle-quality", definition.quality)
    if definition.quality == "hero":
        body.setName(path.stem.replace("_", "-"))
        if trace is not None:
            trace.mark("hero_mesh_loaded")
    body.reparentTo(root)
    environment = None
    if definition.quality == "hero":
        environment = vehicle_reflection()
        if trace is not None:
            trace.mark("reflection_resource_loaded")
        set_vehicle_reflection(root, environment)
    wheels = []
    for name, hub in zip(WHEEL_NAMES, wheel_hubs(config)):
        wheel = body.find(f"**/{name}")
        if wheel.isEmpty():
            raise ValueError(f"车辆GLB缺少轮根：{definition.id}/{name}")
        pivot = fit_wheel(parent, wheel, name, hub, config)
        if environment is not None:
            set_vehicle_reflection(wheel, environment)
        wheels.append(pivot)
    fit_body(body, root, config)
    if definition.quality == "hero":
        balance_vehicle_ambient(parent, root, wheels)
    return root, wheels


def fit_wheel(parent, mesh, name, hub, config):
    """轮姿由Snapshot写到无缩放枢轴，宽径缩放留在它的网格子节点。"""
    pivot = parent.attachNewNode(name)
    mesh.reparentTo(pivot)
    low, high = mesh.getTightBounds(pivot)
    size = high-low
    scale = Vec3(config.wheel_width/size.x, 2*config.wheel_radius/size.y, 2*config.wheel_radius/size.z)
    mesh.setScale(*(mesh.getScale()[a]*scale[a] for a in range(3)))
    low, high = mesh.getTightBounds(pivot)
    mesh.setPos(mesh.getPos()-(low+high)/2)
    # 静态预览为设计地面坐标；驾驶中由唯一物理世界四轮姿态替换。
    pivot.setPos(hub[0], hub[1], config.wheel_radius-config.center_of_mass_height)
    return pivot


def fit_body(body, root, config):
    """车身网格外廓与声明碰撞盒同步，不从显示节点反写物理参数。"""
    low, high = body.getTightBounds(root)
    size = high-low
    half = Vec3(config.collision_half_width, config.collision_half_length, config.collision_half_height)
    body.setScale(*(body.getScale()[a]*2*half[a]/size[a] for a in range(3)))
    low, high = body.getTightBounds(root)
    body.setPos(body.getPos()+Vec3(*body_center(config))-(low+high)/2)


@lru_cache(maxsize=1)
def vehicle_reflection():
    """已离线过滤的中性日光反射，仅供主车材质使用。"""
    path = resource_root() / "assets/game/vehicles/reflection-probe.env"
    return EnvMap.from_file_path(Filename.fromOsSpecific(str(path)))


def set_vehicle_reflection(node, environment):
    texture = environment.filtered_env_map
    node.setShaderInput("filtered_env_map", texture)
    node.setShaderInput("max_reflection_lod", texture.num_loadable_ram_mipmap_images)


def balance_vehicle_ambient(parent, body, wheels):
    """主车压低均匀环境填光，保留原太阳/车库主灯及其阴影。"""
    lights = parent.getNetState().getAttrib(LightAttrib)
    if lights is None:
        return  # 无灯的资产检查节点无需创建表现灯光。
    for index in range(lights.getNumOnLights()):
        source = lights.getOnLight(index)
        if isinstance(source.node(), AmbientLight):
            fill = AmbientLight("vehicle-ambient-fill")
            fill.setColor(source.node().getColor() * 0.28)
            fill_path = body.attachNewNode(fill)
            for node in (body, *wheels):
                node.setLightOff(source)
                node.setLight(fill_path)
