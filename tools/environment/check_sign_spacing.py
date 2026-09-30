"""以生产标志模型与实际里程布置复现限速/横风牌重叠，保存修订对照。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, Vec4

from application import CoastalDrive
from environment.expressway_route import positions
from scene import make_mesh


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, track="endless", seed=0, road_shape="straight",
                       output=args.output, render_size=(1280, 720))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    app.scene.render.hide()
    app.scene.sun_path.node().setShadowCaster(False)
    group = app.render.attachNewNode("sign-spacing-evidence")
    road = make_mesh("road-context", [(-9, 0, -.01), (9, 0, -.01),
                                      (9, 300, -.01), (-9, 300, -.01)],
                     [(0, 1, 2), (0, 2, 3)], Vec4(.15, .16, .17, 1))
    road.reparentTo(group)
    before = [("speed-limit", 10.3, 1100, 0), ("wind-warning", 10.4, 1100, 0)]
    after = [item for index in (5, 6) for item in positions(index, 0)
             if item[0] in ("speed-limit", "wind-warning")]
    nodes = []
    try:
        for label, placements, camera_y, target_y in (("before-overlap", before, 75, 100),
                                                       ("after-limit", after, 75, 100),
                                                       ("after-warning", after, 220, 250)):
            for node in nodes:
                node.removeNode()
            nodes = []
            for name, x, s, heading in placements:
                node = app.scene.expressway_kit[name].copyTo(group)
                node.setPos(x, s-1000, 0)
                node.setH(heading)
                nodes.append(node)
            app.camera.setPos(10.35, camera_y, 2.3)
            app.camera.lookAt(10.35, target_y, 3.0)
            app.taskMgr.step()
            for _ in range(3):
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            app.win.saveScreenshot(Filename.fromOsSpecific(str(args.output / f"{label}.png")))
        interval = after[1][2] - after[0][2]
        report = {"passed": interval >= 50, "seed": 0, "before": before,
                  "after": after, "separation_m": interval,
                  "kind": "production sign models and placements; isolated rendered comparison"}
        (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
        return 0 if report["passed"] else 1
    finally:
        group.removeNode()
        app.close_game()


if __name__ == "__main__":
    raise SystemExit(main())
