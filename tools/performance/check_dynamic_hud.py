"""真实窗口录制动态HUD及轻微移动的交通车；读回不阻塞引擎，也不计入FPS。"""

import argparse
import ctypes
import math
import os
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pipeline", choices=("draw", "cull-draw"), default="draw")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    capture = Path(tempfile.mkdtemp(prefix="CoastalDrive-dynamic-HUD-"))
    (args.output / "capture-path.txt").write_text(str(capture), encoding="utf-8")
    from panda3d.core import Vec3

    from application import CoastalDrive
    from highway_run import HighwayResult

    pipeline = {"draw": "/Draw", "cull-draw": "Cull/Draw"}[args.pipeline]
    app = CoastalDrive(smoke=True, onscreen=True, track="endless", road_shape="hills",
                       seed=23, output=args.output, render_size=(1920, 1080),
                       threading_model=pipeline)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    state = app.session.current
    position = Vec3(*state.player.position)
    app.camera.setPos(position + Vec3(0, -11, 4))
    app.camera.lookAt(position + Vec3(0, 20, 1))
    app.scene.sky.setPos(position)
    app.scene.update_lighting(position)
    app.refresh_panel()
    handle = app.win.getWindowHandle().getIntHandle()
    ctypes.windll.user32.ShowWindow(handle, 9)
    ctypes.windll.user32.SetForegroundWindow(handle)
    recording, log = None, None
    frames = 0

    def observe(task):
        nonlocal frames, recording, log
        frames += 1
        # 只改变诊断显示副本，物理冻结；同一车身范围内不断更新姿态以检查渲染稳定性。
        traffic = tuple(replace(car, position=(car.position[0] + .15*math.sin(task.time*3),
                        car.position[1], car.position[2]),
                        heading=car.heading + 2*math.sin(task.time*3)) for car in state.traffic)
        current = replace(state, traffic=traffic,
                          player=replace(state.player, speed=frames % 40, rpm=1500+frames % 3000))
        app.scene.apply(current)
        app.hud.update(current, app.session.race.snapshot,
                       HighwayResult(running=True, elapsed=task.time), track="endless",
                       countdown="", notice="")
        if task.time >= 3 and recording is None:
            log = (capture / "ffmpeg.log").open("w", encoding="utf-8")
            recording = subprocess.Popen([
                "ffmpeg", "-y", "-loglevel", "error", "-f", "gdigrab", "-framerate", "30",
                "-i", "title=CoastalDrive 0.8.3 Impact Audio", "-t", "8", "-c:v", "libx264",
                "-preset", "ultrafast", "-crf", "15", str(capture / "window.mp4"),
            ], stdout=log, stderr=log)
        if task.time >= 13:
            app.userExit()
            return task.done
        return task.cont

    app.taskMgr.add(observe, "dynamic-render-check", sort=45)
    try:
        app.run()
    finally:
        if recording is not None:
            code = recording.wait(timeout=15)
            log.close()
        app.close_game()
    if recording is not None and code:
        raise RuntimeError(f"窗口录制失败：{capture / 'ffmpeg.log'}")
    print(capture / "window.mp4")


if __name__ == "__main__":
    main()
