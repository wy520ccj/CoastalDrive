"""用真实最佳圈记录检查幽灵显示/开关/阴影；静态预览不冒充人工驾驶。"""

import argparse
import json
import os
import shutil
import sys
from dataclasses import replace
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

import numpy as np
from direct.gui.DirectGui import OnscreenText
from panda3d.core import Filename, Point2, Vec3

from application import CoastalDrive
from ghost_visual import GHOST_MASK
from race import BestTimes, GameMode
from session import Phase
from ui import theme
from vehicle_config import CAR
from vehicle_workspace import WorkspaceVehicle


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check(output, source, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    scores = BestTimes(source)
    shutil.copy2(source, output/"test-best-times.json")
    (output/"ghosts").mkdir()
    for digest in scores.times.get("_ghosts_v1", {}).values():
        shutil.copy2(source.parent/"ghosts"/(digest+".cdg"), output/"ghosts"/(digest+".cdg"))
    app = CoastalDrive(smoke=True, output=output, render_size=size,
                       workspace_vehicle=WorkspaceVehicle("game-tuned", CAR))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")

    def capture(name):
        for _ in range(3):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        texture = app.win.getScreenshot()
        require(texture.write(Filename.fromOsSpecific(str(output/f"{name}.png"))), "截图失败")
        return np.frombuffer(texture.getRamImageAs("RGBA"), dtype=np.uint8).reshape(size[1], size[0], 4)[::-1].copy()

    try:
        app.session.start(mode=GameMode.TIME_TRIAL, countdown=False)
        app.sync_scene()
        lap = app.session.reference_ghost
        require(lap is not None, app.session.race.snapshot.ghost_notice)
        seconds = lap.seconds*.33
        pose = lap.pose_at(seconds)
        # 参考显示稍后0.6秒的真实姿态，主车显示较早的真实姿态；世界始终停在初态。
        shown = replace(app.session.current, tick=0, time=seconds+.6,
                        player=replace(app.session.current.player, position=pose.position,
                            heading=pose.hpr[0], pitch=pose.hpr[1], roll=pose.hpr[2], wheels=pose.wheels))
        app.session.phase = Phase.DRIVING
        app.session.race.snapshot = replace(app.session.race.snapshot, elapsed=seconds+.6, start_time=0.)
        app._shown_phase = None
        app.refresh_panel()
        app.hud.resize(app.getAspectRatio())
        app.refresh_ghost_button()
        app.ghost_button.setX(app.getAspectRatio()-.44)
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.hud.update(shown, app.session.race.snapshot, app.session.highway.snapshot,
                       track="coastal", countdown="", notice="真实最佳圈静态回放预览")
        label = OnscreenText(parent=app.aspect2d, font=app.ui_font,
                             text="真实记录预览 / 主车较参考早0.6秒 / 物理未推进", fg=theme.INK,
                             scale=.028, pos=(0., -.81))
        app.apply_scene(shown, 0.)
        ghost = app.scene.ghost
        require(ghost is not None and not ghost.root.isHidden(GHOST_MASK), "幽灵没有显示")
        bodies = app.session.simulation._world.getNumRigidBodies()
        frozen = app.session.simulation.snapshot()
        for _ in range(6):
            app.taskMgr.step()
        on = capture("01-ghost-on")
        on_repeat = capture("01b-unchanged-on")
        low, high = ghost.root.getTightBounds(app.render)
        projected = []
        for x, y, z in product((low.x, high.x), (low.y, high.y), (low.z, high.z)):
            point = Point2()
            require(app.camLens.project(app.cam.getRelativePoint(app.render, Vec3(x, y, z)), point), "幽灵不在镜头内")
            projected.append(((point.x+1)*size[0]/2, (1-point.y)*size[1]/2))
        bounds = (max(0, int(min(p[0] for p in projected))-6),
                  min(size[0], int(max(p[0] for p in projected))+7),
                  max(0, int(min(p[1] for p in projected))-6),
                  min(size[1], int(max(p[1] for p in projected))+7))
        app.scene.apply_ghost(shown, app.session.race.snapshot, False)
        off = capture("02-ghost-hidden-control")
        off_repeat = capture("02b-unchanged-off")
        changed = np.any(on != off, axis=2)
        total = int(changed.sum())
        left, right, top, bottom = bounds
        changed[top:bottom, left:right] = False
        outside = int(changed.sum())
        diagnostic = {"total": total, "outside": outside, "bounds": bounds,
                      "unchanged_on_pixels": int(np.any(on != on_repeat, axis=2).sum()),
                      "unchanged_off_pixels": int(np.any(off != off_repeat, axis=2).sum())}
        stable_on, stable_off = (np.any(a != b, axis=2) for a, b in ((on, on_repeat), (off, off_repeat)))
        stable_on[top:bottom, left:right] = False
        stable_off[top:bottom, left:right] = False
        diagnostic.update(unchanged_on_outside=int(stable_on.sum()), unchanged_off_outside=int(stable_off.sum()))
        (output/"pixel-diagnostic.json").write_text(json.dumps(diagnostic), encoding="utf-8")
        require(diagnostic["unchanged_on_outside"] == 0 and diagnostic["unchanged_off_outside"] == 0,
                "静态渲染尚未稳定，不能据此判断幽灵区域")
        require(total > 25 and outside == 0, f"可见性/阴影像素检查失败：{total=}, {outside=}")
        require(not (app.scene.sun_path.node().getCameraMask() & GHOST_MASK), "幽灵仍进入阴影相机")
        app.key_down("g")
        app.key_up("g")
        app.apply_scene(shown, 0.)
        require(not app.ghost_enabled and ghost.root.isHidden(GHOST_MASK), "G键未隐藏")
        capture("03-g-toggle-off")
        app.ghost_button["command"]()
        app.apply_scene(shown, 0.)
        require(app.ghost_enabled and not ghost.root.isHidden(GHOST_MASK), "按钮未恢复")
        overlap = replace(shown, player=replace(shown.player, position=lap.pose_at(shown.time).position))
        app.scene.apply_ghost(overlap, app.session.race.snapshot, True)
        require(ghost.root.isHidden(GHOST_MASK), "贴近主车未隐藏")
        capture("04-overlap-fade")
        require(app.session.simulation._world.getNumRigidBodies() == bodies
                and app.session.simulation.snapshot() == frozen, "回放改变了物理")
        label.destroy()
        summary = {"passed": True, "source_scores": str(source), "frames": lap.frames,
                   "seconds": lap.seconds, "context": lap.context, "size": size,
                   "pose_source": "real_completed_steps", "presentation": "static_two_times_preview",
                   "changed_pixels": total, "changed_outside_ghost_bounds": outside,
                   "projected_bounds": bounds, "rigid_bodies_unchanged": bodies,
                   "static_control": diagnostic,
                   "human_driving": "not_run"}
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    result = check(args.output.resolve(), args.scores.resolve(), tuple(args.size))
    print(json.dumps({key: result[key] for key in ("passed", "frames", "seconds", "size", "changed_pixels",
                                                  "changed_outside_ghost_bounds")}, ensure_ascii=False))
