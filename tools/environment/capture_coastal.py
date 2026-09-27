"""固定镜头记录海岸环境；仅移动相机，不修改物理世界。"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, Vec3

from application import CoastalDrive
from coastal_map import offset_point, point_at


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--width", type=int, default=1920)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    app = CoastalDrive(smoke=True, output=args.output, render_size=(args.width, args.width * 9 // 16))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    records = []
    try:
        app.scene.apply(app.session.current)
        for distance in (0, 65, 140, 225, 315):
            p, q = point_at(distance), point_at(distance + 26)
            eye = Vec3(*offset_point(p, -1.0, 3.8))
            app.camera.setPos(eye)
            app.camera.lookAt(Vec3(*offset_point(q, 0, 2)))
            app.scene.sky.setPos(eye)
            app.scene.update_lighting(eye)
            app.camLens.setFov(68)
            app.taskMgr.step()
            for _ in range(12):
                app.graphicsEngine.renderFrame()
            path = args.output / f"coast-{distance:03d}.png"
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
            samples = []
            for _ in range(45):
                start = time.perf_counter()
                app.graphicsEngine.renderFrame()
                app.graphicsEngine.syncFrame()
                samples.append((time.perf_counter() - start) * 1000)
            records.append({"distance_m": distance, "eye": list(eye), "screenshot": path.name,
                            "render_mean_ms": sum(samples) / len(samples),
                            "render_p95_ms": sorted(samples)[int(len(samples) * 0.95)]})
        report = {"kind": "static camera rendering, not full gameplay performance gate",
                  "renderer": app.win.getGsg().getDriverRenderer(), "views": records}
        (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
