"""高速路肩阴影连续帧诊断；诊断开关仅在本工具，不进入游戏配置。"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, PNMImage, Vec3

from application import CoastalDrive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", choices=("normal", "fixed-sun", "no-shadow"), default="normal")
    parser.add_argument("--camera", choices=("static", "moving"), default="moving")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--distance", type=int, choices=(11, 16), default=11)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    app = CoastalDrive(smoke=True, track="endless", seed=23, output=args.output,
                       render_size=(args.width, args.width * 9 // 16))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    records = []
    try:
        app.scene.apply(app.session.current)
        if args.diagnostic == "no-shadow":
            app.scene.sun_path.node().setShadowCaster(False)
        for frame in range(48):
            travel = frame * 0.08
            camera_travel = travel if args.camera == "moving" else 0
            eye = Vec3(-3.5, 130 - args.distance + camera_travel, 3.8)
            target = Vec3(-7.5, 153 + camera_travel, 0.35)
            app.camera.setPos(eye)
            app.camera.lookAt(target)
            app.scene.sky.setPos(eye)
            light_target = Vec3(-3.5, 130 + (0 if args.diagnostic == "fixed-sun" else travel), 0.5)
            app.scene.update_lighting(light_target)
            app.taskMgr.step()
            for _ in range(2):
                app.graphicsEngine.renderFrame()
            screenshot = PNMImage()
            assert app.win.getScreenshot(screenshot)
            filename = f"frame-{frame:03d}.png"
            screenshot.write(Filename.fromOsSpecific(str(args.output / filename)))
            records.append({"frame": frame, "eye": list(eye), "light_target": list(light_target),
                            "light_position": list(app.scene.sun_path.getPos()), "file": filename})
        report = {"diagnostic": args.diagnostic, "camera": args.camera,
                  "resolution": [args.width, args.width * 9 // 16], "camera_distance": args.distance,
                  "note": "48 rendered frames; frozen physics; camera/light probe, not gameplay FPS",
                  "frames": records}
        (args.output / "frames.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    finally:
        app.close_game()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i",
                    str(args.output / "frame-%03d.png"), "-c:v", "libx264", "-crf", "18",
                    "-pix_fmt", "yuv420p", str(args.output / "motion.mp4")], check=True)


if __name__ == "__main__":
    main()
