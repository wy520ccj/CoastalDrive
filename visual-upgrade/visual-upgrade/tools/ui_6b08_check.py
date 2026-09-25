"""6B-08 的真实离屏界面留证与文本边界检查。"""

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from panda3d.core import Filename

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from application import CoastalDrive
from controls import ConstantController
from race import GameMode
from session import Phase
from simulation import Control

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "logs/6B-08/ui"


def capture(app, name, folder):
    app._shown_phase = None
    app.update(SimpleNamespace(cont=None))
    app.taskMgr.step()
    app.graphicsEngine.renderFrame()
    app.graphicsEngine.renderFrame()
    path = folder / f"{name}.png"
    assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
    return path


def bounds(app):
    checks = []
    for widget, width, scale in (
        (app.status, 0.98, 0.040),
        (app.status_notice, 0.98, 0.037),
        (app.panel_note, 0.92 if app.garage is not None else 1.80 if app.session.phase == Phase.RESULTS else 1.37, 0.040),
        (app.panel_detail, 1.50, 0.055),
    ):
        for line in widget.getText().split("\n"):
            measured = app.fit_lines(line, width, scale)
            checks.append(measured == line)
    return all(checks)


def run_resolution(size):
    folder = OUTPUT / f"{size[0]}x{size[1]}"
    folder.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=folder, render_size=size)
    app.taskMgr.remove("finish-smoke")
    records = {}

    def shot(name):
        path = capture(app, name, folder)
        records[name] = {
            "screenshot": str(path.relative_to(ROOT)),
            "title": app.panel_title.getText() if not app.panel.isHidden() else "",
            "text_fits": bounds(app),
        }

    try:
        app.session.menu()
        shot("01-main-menu")
        app.start_game(mode=GameMode.TIME_TRIAL)
        app.session.countdown_ticks = 0
        app.session.phase = Phase.DRIVING
        app.session.race.snapshot = replace(
            app.session.race.snapshot, elapsed=123.456, checkpoints=3, next_checkpoint=4,
            invalidated=True, invalid_reason="错过检查点后驶离赛道，本圈成绩无效",
        )
        shot("02-time-trial-hud")
        app.session.pause()
        shot("06-paused")
        app.session.resume()
        app.session.race.snapshot = replace(
            app.session.race.snapshot, finished=True, invalidated=False,
            last_lap=123.456, best_lap=123.456,
        )
        app.session.phase = Phase.RESULTS
        shot("07-challenge-success")
        app.session.race.snapshot = replace(
            app.session.race.snapshot, invalidated=True,
            invalid_reason="错过检查点后驶离赛道，本圈成绩无效",
        )
        shot("08-challenge-failure")
        app.start_game(mode=GameMode.FREE_DRIVE)
        app.session.phase = Phase.DRIVING
        shot("03-coastal-free-hud")
        app.session.finish()
        shot("09-free-drive-results")
        app.session.road_shape = "hills"
        app.start_game(mode=GameMode.FREE_DRIVE, track="endless")
        app.session.phase = Phase.DRIVING
        app.session.highway.snapshot = replace(
            app.session.highway.snapshot, distance=2345.6, elapsed=98.7, collisions=2,
        )
        shot("04-endless-free-hud")
        app.start_game(mode=GameMode.DISTANCE_CHALLENGE, track="endless")
        app.session.phase = Phase.DRIVING
        app.session.highway.snapshot = replace(
            app.session.highway.snapshot, distance=4321.0, elapsed=152.3,
        )
        shot("05-distance-challenge-hud")
        app.session.highway.snapshot = replace(
            app.session.highway.snapshot, finished=True, succeeded=False,
            reason="车辆复位后本次五公里无碰撞挑战结束，请返回菜单重新开始",
            collisions=1,
        )
        app.session.phase = Phase.RESULTS
        shot("12-distance-challenge-failure-long")
        app.session.highway.snapshot = replace(
            app.session.highway.snapshot, succeeded=True,
            reason="完成 5 公里无碰撞挑战", distance=5000, collisions=0,
        )
        shot("13-distance-challenge-success")
        app.start_game(mode=GameMode.FREE_DRIVE, track="endless")
        app.session.highway.snapshot = replace(
            app.session.highway.snapshot, finished=True, distance=8731.0,
            elapsed=372.38, collisions=4,
        )
        app.session.phase = Phase.RESULTS
        shot("14-endless-free-results")
        app.session.menu()
        app.choose_garage()
        app.appearance.notice = "车辆外观设置保存失败，请检查当前目录的写入权限后重试。"
        shot("10-garage")
        app.cancel_garage()
        app.choose_audio_settings()
        app.audio_settings.notice = "声音设置保存失败，请检查当前目录的写入权限后重试。"
        shot("11-audio-settings")
    finally:
        app.close_game()
    return records


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == "video":
        record_flow()
        return
    width, height = map(int, sys.argv[1].split("x"))
    states = run_resolution((width, height))
    passed = all(item["text_fits"] for item in states.values())
    (OUTPUT / f"report-{width}x{height}.json").write_text(
        json.dumps({"passed": passed, "states": states}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"passed": passed, "folder": str(OUTPUT)}, ensure_ascii=False))


def record_flow():
    folder = OUTPUT / "flow-720-frames"
    folder.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=OUTPUT / "flow-data")
    app.taskMgr.remove("finish-smoke")
    frames = 0

    def add_frames(count, driving=False):
        nonlocal frames
        for _ in range(count):
            if driving:
                for _ in range(8):
                    app.session.tick()
            app.update(SimpleNamespace(cont=None))
            app.taskMgr.step()
            app.graphicsEngine.renderFrame()
            path = folder / f"frame-{frames:04d}.png"
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
            frames += 1

    try:
        app.session.menu()
        add_frames(12)
        app.key_down("enter")
        app.key_up("enter")
        app.session.phase = Phase.DRIVING
        app.session.begin_driving()
        app.session.set_controller(ConstantController(Control(throttle=1)))
        add_frames(33, driving=True)
        app.key_down("escape")
        app.key_up("escape")
        add_frames(15)
        app.key_down("enter")
        app.key_up("enter")
        add_frames(30, driving=True)
        app.session.finish()
        add_frames(18)
        app.session.menu()
        add_frames(12)
    finally:
        app.close_game()
    video = OUTPUT / "flow-menu-drive-pause-resume-results-menu-720.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "15",
        "-i", str(folder / "frame-%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(video),
    ], check=True)
    print(json.dumps({"video": str(video), "frames": frames}, ensure_ascii=False))


if __name__ == "__main__":
    main()
