"""生产HUD/结算的规则轨迹夹具；实际物理圈由H3回归另行验证。"""

import argparse
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from direct.gui.DirectGui import OnscreenText
from panda3d.core import Filename, TextNode

from application import CoastalDrive
from coastal_map import map_length, point_at
from race import BestTimes, GameMode, RaceTracker
from session import Phase
from ui import theme


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.apply_scene(app.session.current, 0.)
    label = OnscreenText(parent=app.aspect2d, font=app.ui_font, text="自动规则夹具 / 非实际圈速",
                         fg=theme.INK, scale=.028, pos=(-size[0]/size[1]+.07, -.82), align=TextNode.ALeft)
    images = []

    def capture(name):
        for _ in range(3):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        path = output/f"{name}.png"
        require(app.win.getScreenshot().write(Filename.fromOsSpecific(str(path))), "截图失败")
        images.append(path.name)

    def update_hud(race):
        app.session.phase = Phase.DRIVING
        app.session.mode = race.mode
        app.session.race.snapshot = race
        app._shown_phase = None
        app.refresh_panel()
        app.hud.update(app.session.current, race, app.session.highway.snapshot,
                       track="coastal", countdown="", notice="")

    def render_result(race, name):
        app.session.phase = Phase.RESULTS
        app.session.mode = race.mode
        app.session.race.snapshot = race
        app._shown_phase = None
        app.refresh_panel()
        capture(name)
        for column in app.result_sectors:
            lower, upper = column.getTightBounds(app.panel)
            require(lower.z > app.buttons[0].getZ()+.085, "分段与按钮重叠")
            require(upper.z < app.panel_detail.getTightBounds(app.panel)[0].z-.01, "分段与整圈文字重叠")
            require(lower.x > -.94 and upper.x < .94, "表格超出底板")

    def rule_lap(race, intervals, *, capture_middle=False):
        race.begin()
        for index in range(1, 1002):
            point = point_at(map_length()*index/1000)
            state = SimpleNamespace(player=SimpleNamespace(position=(point.x, point.y, point.z+.42), speed=100.))
            race.update(state, intervals[min(4, (index-1)//200)])
            if capture_middle and index == 410:
                update_hud(race.snapshot)
                capture("02-split-and-total-delta")
        return race.snapshot

    try:
        tracker = RaceTracker(GameMode.TIME_TRIAL, BestTimes(output/"fixture-scores.json"))
        first = rule_lap(tracker, (.1,)*5)
        require(first.finished and not first.invalidated and len(first.splits) == 5, "规则圈未完成")
        tracker.start()
        update_hud(tracker.snapshot)
        capture("01-awaiting-checkpoint")
        candidate = rule_lap(tracker, (.105, .09, .095, .1, .095), capture_middle=True)
        require(candidate.new_best and candidate.reference_splits == first.splits, "参考整圈变化")
        render_result(candidate, "03-new-best-sectors")
        warning = replace(candidate, save_error="成绩暂未保存，请检查存储空间或目录权限")
        render_result(warning, "04-save-warning-layout")
        invalid = replace(candidate, invalidated=True, invalid_reason="车辆复位", new_best=False)
        render_result(invalid, "05-invalid-no-deltas")
        require(all(value == "—" for value in app.result_sectors[2].getText().splitlines()[1:]), "无效圈显示比较")
        update_hud(replace(candidate, mode=GameMode.FREE_DRIVE))
        require(app.hud.split.isHidden(), "自由驾驶残留分段")
        capture("06-free-drive")
        summary = {"passed": True, "size": size, "source": "explicit_rule_trajectory_fixture",
                   "human_driving": "not_run", "physics_lap": "separate_test_h3_review",
                   "reference": asdict(first), "candidate": asdict(candidate), "images": images}
        for name in ("reference", "candidate"):
            summary[name]["mode"] = summary[name]["mode"].value
        (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    finally:
        label.destroy()
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", nargs=2, type=int, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), tuple(args.size)), ensure_ascii=False))
