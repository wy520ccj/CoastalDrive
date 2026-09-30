"""高速路肩阴影连续帧诊断；诊断开关仅在本工具，不进入游戏配置。"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, PNMImage, Point2, Vec3

from application import CoastalDrive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", choices=("normal", "fixed-sun", "no-shadow", "inward-rails", "hard-shadow"), default="normal")
    parser.add_argument("--camera", choices=("static", "moving"), default="moving")
    parser.add_argument("--step", type=float, default=.08)
    parser.add_argument("--start", type=float, default=130)
    parser.add_argument("--road-view", action="store_true")
    parser.add_argument("--shape", choices=("straight", "curves", "hills"), default="straight")
    parser.add_argument("--frames", type=int, default=48)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--distance", type=int, choices=(11, 16), default=11)
    parser.add_argument("--shadow-source", type=Path, help="仅诊断：替换路面阴影函数源文件")
    parser.add_argument("--shoulder-lateral", type=float, default=-7.4)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    if args.shadow_source:
        from environment import expressway_materials

        original_path = expressway_materials.shader_path
        expressway_materials.shader_path = lambda name: (
            Filename.fromOsSpecific(str(args.shadow_source.resolve()))
            if name == "road-shadow.frag" else original_path(name)
        )
    if args.diagnostic == "hard-shadow":
        from panda3d.core import Shader
        from simplepbr._shaderutils import _load_shader_str

        from environment import expressway_materials

        def original_shadow_shader():
            defines = {"MAX_LIGHTS": 8, "ENABLE_SHADOWS": True, "USE_330": True}
            return Shader.make(Shader.SLGLSL, _load_shader_str("simplepbr.vert", defines.copy()),
                               _load_shader_str("simplepbr.frag", defines.copy()))

        expressway_materials.road_shadow_shader = original_shadow_shader
    if args.diagnostic == "inward-rails":
        # 仅诊断：把修复后的显示副本翻回旧朝向，便于同版本连续帧A/B。
        import scene

        make_mesh = scene.make_mesh

        def old_rail(name, vertices, triangles, color):
            if args.shape != "straight" and name.startswith("expressway-rail"):
                triangles = [(a,c,b) for a,b,c in triangles]
            return make_mesh(name,vertices,triangles,color)

        scene.make_mesh = old_rail
    app = CoastalDrive(smoke=True, track="endless", road_shape=args.shape, seed=23, output=args.output,
                       render_size=(args.width, args.width * 9 // 16))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    records = []
    try:
        app.scene.apply(app.session.current)
        if args.diagnostic == "no-shadow":
            app.scene.sun_path.node().setShadowCaster(False)
        from environment.expressway_route import sample

        curve = app.session.simulation.road.curve
        for frame in range(args.frames):
            travel = frame * args.step
            camera_travel = travel if args.camera == "moving" else 0
            eye = sample(curve, args.start - args.distance + camera_travel, -3.5) + Vec3(0,0,3.8)
            target = sample(curve,args.start+23+camera_travel,-7.5)+Vec3(0,0,.35)
            if args.road_view:
                eye = sample(curve,args.start+camera_travel)+Vec3(0,0,3.4)
                target = sample(curve,args.start+camera_travel+45)+Vec3(0,0,1.9)
            app.camera.setPos(eye)
            app.camera.lookAt(target)
            app.scene.sky.setPos(eye)
            light_target = sample(curve,args.start+(0 if args.diagnostic == "fixed-sun" else travel),-3.5)+Vec3(0,0,.5)
            if args.road_view:
                light_target = sample(curve,args.start+(0 if args.diagnostic == "fixed-sun" else travel))+Vec3(0,0,3.4)
            app.scene.update_lighting(light_target)
            app.taskMgr.step()
            for _ in range(2):
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            screenshot = PNMImage()
            assert app.win.getScreenshot(screenshot)
            filename = f"frame-{frame:03d}.png"
            screenshot.write(Filename.fromOsSpecific(str(args.output / filename)))
            shoulder = []
            for ahead in range(5, 101):
                point = sample(curve, args.start + camera_travel + ahead, args.shoulder_lateral) + Vec3(0,0,.012)
                screen, shadow = Point2(), Point2()
                visible = app.camLens.project(app.cam.getRelativePoint(app.render, point), screen)
                covered = app.scene.sun_path.node().getLens().project(
                    app.scene.sun_path.getRelativePoint(app.render, point), shadow)
                shoulder.append({"ahead": ahead, "visible": visible, "covered": covered,
                                 "pixel": [(screen.x + 1) * args.width / 2,
                                           (1-screen.y) * (args.width * 9 // 16) / 2],
                                 "shadow_uv": [(shadow.x+1)/2, (shadow.y+1)/2]})
            records.append({"frame": frame, "eye": list(eye), "light_target": list(light_target),
                            "shoulder": shoulder,
                            "light_position": list(app.scene.sun_path.getPos()), "file": filename})
        report = {"diagnostic": args.diagnostic, "camera": args.camera,
                  "shape": args.shape, "step_m": args.step, "start_m": args.start, "road_view": args.road_view, "resolution": [args.width, args.width * 9 // 16], "camera_distance": args.distance,
                  "shoulder_lateral": args.shoulder_lateral,
                  "note": "rendered frames; frozen physics; camera/light probe, not gameplay FPS",
                  "frames": records}
        (args.output / "frames.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    finally:
        app.close_game()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i",
                    str(args.output / "frame-%03d.png"), "-c:v", "libx264", "-crf", "18",
                    "-pix_fmt", "yuv420p", str(args.output / "motion.mp4")], check=True)


if __name__ == "__main__":
    main()
