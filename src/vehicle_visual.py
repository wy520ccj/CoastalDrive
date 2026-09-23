"""Shared car-body fitting and wheel placement for the road and garage."""

from panda3d.core import Filename, Loader, NodePath

from paths import resource_root
from skins import MODELS
from vehicle_config import WHEEL_HUBS

WHEEL_NAMES = ("wheel-front-left", "wheel-front-right", "wheel-back-left", "wheel-back-right")


def load_vehicle(parent, model_id):
    definition = next(model for model in MODELS if model.id == model_id)
    path = resource_root() / "assets/game" / definition.filename
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
