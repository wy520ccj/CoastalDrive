"""固定镜头移动阴影覆盖，采样真实树影强度与相邻帧变化；不作为FPS测试。"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    if args.baseline:
        from environment import expressway_materials

        expressway_materials.add_shadow_transition = lambda fragment: fragment
    from panda3d.core import Filename, PNMImage, Point2, Vec3

    from application import CoastalDrive
    from environment.expressway_route import terrain_point
    from environment.expressway_vegetation import ground_point

    app = CoastalDrive(smoke=True, track="endless", seed=23, output=args.output,
                       render_size=(1280, 720), threading_model="/Draw")
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    curve = app.session.simulation.stream.curve
    samples = []
    try:
        tree = app.scene.expressway_kit["broadleaf-a"].copyTo(app.scene.render)
        tree.setPos(ground_point(curve, 17.5, 75, 23))
        tree.setScale(2)
        app.camera.setPos(27, 54, 20)
        app.camera.lookAt(20, 78, 0)
        app.scene.sky.setPos(app.camera.getPos())
        points = []
        for row in range(16):
            for col in range(16):
                world = terrain_point(curve, 18+col*.4, 76+row*.4, 23)
                screen = Point2()
                assert app.camLens.project(app.cam.getRelativePoint(app.render, world), screen)
                points.append({"world": tuple(world),
                               "pixel": (round((screen.x+1)*640), round((1-screen.y)*360))})
        for frame in range(201):
            center = frame*.5
            app.scene.update_lighting(Vec3(0, center, 3.4))
            app.taskMgr.step()
            for _ in range(3):
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            image = PNMImage()
            assert app.win.getScreenshot(image)
            values = [sum(image.getXel(*point["pixel"]))/3*255 for point in points]
            samples.append({"center_m": center, "values": values})
            if frame % 20 == 0:
                assert image.write(Filename.fromOsSpecific(str(args.output / f"frame-{frame:03d}.png")))
    finally:
        app.close_game()
    report = {"kind": "frozen camera and tree, real rendered shadow coverage; not FPS",
              "baseline": args.baseline, "step_m": .5, "points": points, "frames": samples}
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"{len(samples)} frames and {len(points)} ground points: {args.output}")


if __name__ == "__main__":
    main()
