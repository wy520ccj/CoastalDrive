"""Capture a real offscreen render of the current coastal scene."""

import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from panda3d.core import Filename

    from application import CoastalDrive

    output = root / "logs" / "visual-scene"
    output.mkdir(parents=True, exist_ok=True)
    track = sys.argv[1] if len(sys.argv) > 1 else "coastal"
    app = CoastalDrive(smoke=True, output=output, track=track)
    app.taskMgr.remove("finish-smoke")
    try:
        for _ in range(3):
            app.taskMgr.step()
            app.update(type("Task", (), {"cont": None})())
            app.graphicsEngine.renderFrame()
        path = output / f"{track}.png"
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        print(f"saved {path}; renderer={app.win.getGsg().getDriverRenderer()}")
        app.camera.setPos(125, -38, 12)
        app.camera.lookAt(86, 65, 4)
        for _ in range(2):
            app.graphicsEngine.renderFrame()
        if track == "coastal":
            app.win.saveScreenshot(Filename.fromOsSpecific(str(output / "coastal-overlook.png")))
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
