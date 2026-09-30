"""真实窗口固定背景检查提示底板；同时覆盖稳定提示与动态高度更新。"""

import argparse
import ctypes
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from direct.gui.DirectGui import DirectFrame
from panda3d.core import Vec3, WindowProperties

from application import CoastalDrive


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--background-sweep", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    app = CoastalDrive(smoke=True, onscreen=True, output=args.output)
    properties = WindowProperties()
    properties.setTitle("CoastalDrive Notice Render Check")
    app.win.requestProperties(properties)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    state = app.session.current
    position = Vec3(*state.player.position)
    app.camera.setPos(position + Vec3(0, -11, 4))
    app.camera.lookAt(position + Vec3(0, 20, 1))
    app.scene.sky.setPos(position)
    app.scene.apply(state)
    app.scene.update_lighting(position)
    app.refresh_panel()
    app.hud.select_radio(2)
    backdrop = (DirectFrame(parent=app.aspect2d, frameColor=(1, 1, 1, 1),
                            frameSize=(-2, 2, -1, 1), sortOrder=-100)
                if args.background_sweep else None)
    handle = app.win.getWindowHandle().getIntHandle()
    ctypes.windll.user32.ShowWindow(handle, 9)
    ctypes.windll.user32.SetForegroundWindow(handle)
    recording = None
    frames = 0
    window_states = []
    log = (args.output / "ffmpeg.log").open("w", encoding="utf-8")

    def observe(task):
        nonlocal recording, frames
        frames += 1
        if backdrop is not None:
            brightness = .05 if int(task.time * 2) % 2 else 1
            backdrop.setColorScale(brightness, brightness, brightness, 1)
        # 先稳定两秒，再每帧改变文字；最后交替长短提示，真实布局仍走HUD.update。
        notice = "" if task.time < 5 else f"请返回赛道 {frames % 10}"
        if task.time >= 8 and frames % 2:
            notice = "请返回赛道，车辆已经离开有效计时区域；请检查路线并继续驶向下一个检查点"
        app.hud.update(state, app.session.race.snapshot, app.session.highway.snapshot,
                       track="coastal", countdown="", notice=notice)
        window = app.win.getProperties()
        window_states.append({"time": task.time, "foreground": window.getForeground(),
                              "minimized": window.getMinimized()})
        if task.time >= 3 and recording is None:
            recording = subprocess.Popen([
                "ffmpeg", "-y", "-loglevel", "error", "-f", "gdigrab", "-framerate", "30",
                "-i", "title=CoastalDrive Notice Render Check", "-t", "8", "-c:v", "libx264",
                "-preset", "ultrafast", "-crf", "15", str(args.output / "window.mp4")
            ], stdout=log, stderr=log)
        if task.time >= 13:
            app.userExit()
            return task.done
        return task.cont

    app.taskMgr.add(observe, "notice-render-check", sort=45)
    try:
        app.run()
    finally:
        if recording is not None:
            code = recording.wait(timeout=15)
        log.close()
        app.close_game()
    if code:
        raise RuntimeError(f"窗口录制失败：{args.output / 'ffmpeg.log'}")
    # gdigrab按窗口外框录制：1280x720客户区外通常有8px边框和标题栏。
    probe = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=width,height", "-of", "json", str(args.output / "window.mp4")
    ])
    dimensions = json.loads(probe)["streams"][0]
    border = (dimensions["width"] - 1280) // 2
    top = dimensions["height"] - 720 - border
    # 左侧内边距，无文字，所有高度共用的底板区域；背景和相机完全固定。
    crop = f"crop=6:18:{border+30}:{top+185}"
    raw = subprocess.check_output([
        "ffmpeg", "-loglevel", "error", "-i", str(args.output / "window.mp4"),
        "-vf", crop, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"
    ])
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 18, 6, 3)
    colors = pixels.astype(float).mean(axis=(1, 2))
    distances = np.max(np.abs(colors - np.median(colors, axis=0)), axis=1)
    capture_states = [s for s in window_states if 3 <= s["time"] <= 11.5]
    visible = all(s["foreground"] and not s["minimized"] for s in capture_states)
    report = {"frames": len(colors), "outlier_frames": int(np.sum(distances > 15)),
              "max_rgb_change": float(np.max(np.abs(np.diff(colors, axis=0)))),
              "rgb_min": colors.min(axis=0).tolist(), "rgb_max": colors.max(axis=0).tolist(),
              "foreground_frames": sum(s["foreground"] for s in window_states),
              "observed_frames": len(window_states),
              "minimized_frames": sum(s["minimized"] for s in window_states),
              "background_sweep": args.background_sweep,
              "capture_visible": visible,
              "passed": bool(np.max(distances) < 15) and visible, "roi": crop,
              "kind": "real window; frozen scenery; steady text, dynamic text and alternating height"}
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-i", str(args.output / "window.mp4"),
        "-frames:v", "1", str(args.output / "frame.png")
    ], check=True)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
