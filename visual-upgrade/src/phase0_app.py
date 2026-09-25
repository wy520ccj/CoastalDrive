"""Packaged smoke application used during phase 0 only."""

from pathlib import Path

import gltf
import simplepbr
from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, Filename, NodePath, loadPrcFileData

loadPrcFileData("phase0", "window-title CoastalDrive phase 0")


class Phase0App(ShowBase):
    def __init__(self) -> None:
        super().__init__()
        self.disableMouse()
        simplepbr.init()

        ambient = AmbientLight("phase0-ambient")
        ambient.setColor((0.8, 0.8, 0.8, 1))
        self.render.setLight(self.render.attachNewNode(ambient))

        model_path = Path.cwd() / "assets" / "game" / "player-car.glb"
        model = gltf.load_model(Filename.fromOsSpecific(str(model_path)))
        NodePath(model).reparentTo(self.render)


if __name__ == "__main__":
    Phase0App().run()
