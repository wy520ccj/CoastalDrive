"""Shared car-body fitting and wheel placement for the road and garage."""

from functools import lru_cache

import gltf
from panda3d.core import AmbientLight, Filename, LightAttrib, Loader, NodePath
from simplepbr.envmap import EnvMap

from paths import resource_root
from skins import VehicleDefinition
from vehicle_config import WHEEL_HUBS

WHEEL_NAMES = ("wheel-front-left", "wheel-front-right", "wheel-back-left", "wheel-back-right")


def load_vehicle(parent, definition: VehicleDefinition, *, trace=None):
    """按统一车型定义装配显示车；调用方身份不参与资产选择。"""
    path = resource_root() / "assets/game" / definition.visual
    if path.suffix == ".glb":
        return load_gltf_vehicle(parent, definition, path, trace=trace)

    root = parent.attachNewNode(definition.id)
    body = NodePath(Loader.getGlobalPtr().loadSync(Filename.fromOsSpecific(str(path))))
    body.reparentTo(root)
    body.setH(180)
    wheels = []
    for name, hub in zip(WHEEL_NAMES, WHEEL_HUBS):
        wheel = body.find(f"**/{name}")
        mesh = wheel.getChild(0)
        pivot = parent.attachNewNode(name)
        mesh.reparentTo(pivot)
        mesh.setH(180)
        mesh.setScale(1.1)
        low, high = mesh.getTightBounds()
        mesh.setPos(-(low + high) / 2)
        pivot.setPos(hub[0], hub[1], -0.12)
        wheels.append(pivot)
        wheel.removeNode()
    body.setScale(*definition.body_scale)
    body.setZ(-0.48)
    return root, wheels


def load_gltf_vehicle(parent, definition, path, *, trace=None):
    """米制 GLB 共用 Snapshot 的四个世界轮姿。"""
    root = parent.attachNewNode(definition.id)
    body = NodePath(gltf.load_model(Filename.fromOsSpecific(str(path))))
    body.setPythonTag("vehicle-quality", definition.quality)
    if definition.quality == "hero":
        body.setName("classic-coupe-v1")
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
    for name in WHEEL_NAMES:
        wheel = body.find(f"**/{name}")
        if wheel.isEmpty():
            raise ValueError(f"车辆GLB缺少轮根：{definition.id}/{name}")
        wheel.reparentTo(parent)
        if environment is not None:
            set_vehicle_reflection(wheel, environment)
        wheels.append(wheel)
    if definition.quality == "hero":
        balance_vehicle_ambient(parent, root, wheels)
    return root, wheels


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
