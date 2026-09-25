"""Inspect imported wheel geometry and contact placement at several wheel rotations."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panda3d.core import Filename, Quat, Vec3

from application import CoastalDrive
from simulation import Control


def main():
    output = Path(__file__).resolve().parents[1] / "logs/h2-review/wheels-after"
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    sim = app.session.simulation
    try:
        for _ in range(240):
            sim.step(Control())
        state = sim.snapshot()
        app.scene.apply(state)
        app.panel.hide()
        app.status.hide()
        app.help.hide()
        app.camera.setPos(Vec3(*state.player.position) + Vec3(5, -7, 2))
        app.camera.lookAt(Vec3(*state.player.position) + Vec3(0, 0, 0.3))
        report = []
        assert all(w.getRaycastInfo().isInContact() for w in sim._vehicle.getWheels())
        body = app.scene.player.getChild(0)
        arch_points = ((0.3, -0.66, 0.3), (-0.3, -0.66, 0.3), (0.3, 0.66, 0.3), (-0.3, 0.66, 0.3))
        for arch, wheel in zip(arch_points, state.player.wheels):
            position = app.render.getRelativePoint(body, Vec3(*arch))
            assert abs(position.y - wheel.position[1]) < 0.03
            assert abs(position.z - wheel.position[2]) < 0.03
        for angle in (0, 45, 90, 135):
            spin = Quat()
            spin.setFromAxisAngle(angle, Vec3(1, 0, 0))
            for node, wheel in zip(app.scene.wheels, state.player.wheels):
                node.setQuat(spin * Quat(*wheel.orientation))
                low, high = node.getTightBounds(app.render)
                assert ((low + high) / 2 - Vec3(*wheel.position)).length() < 0.001
                assert -0.02 < low.z < 0.03
            for side in (-1, 1):
                app.camera.setPos(Vec3(*state.player.position) + Vec3(side * 5, -7, 2))
                app.camera.lookAt(Vec3(*state.player.position) + Vec3(0, 0, 0.3))
                for _ in range(4):
                    app.taskMgr.step()
                assert app.win.saveScreenshot(
                    Filename.fromOsSpecific(str(output / f"spin-{angle}-side-{side}.png"))
                )
            report.append(
                {
                    "spin_deg": angle,
                    "bounds": [
                        [tuple(v) for v in n.getTightBounds(app.render)] for n in app.scene.wheels
                    ],
                }
            )
        (output / "report.json").write_text(
            json.dumps({"passed": True, "samples": report}, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
