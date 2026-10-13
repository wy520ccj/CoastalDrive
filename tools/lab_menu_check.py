"""真实DirectGUI鼠标命中、持续悬停、选项选择与点击外部关闭检查。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import (
    Filename,
    MouseButton,
    MouseWatcher,
    PGMouseWatcherBackground,
    Point3,
    VirtualMouse,
)

from lab_application import VehicleLab


def check(output, height):
    output.mkdir(parents=True, exist_ok=False)
    width = round(height * 16 / 9)
    app = VehicleLab(offscreen=True, render_size=(width, height))
    mouse = VirtualMouse("lab-menu-pointer")
    mouse.setWindowSize(width, height)
    mouse.setMouseOn(True)
    watcher = app.dataRoot.attachNewNode(mouse).attachNewNode(MouseWatcher("lab-menu-watcher"))
    app.mouseWatcherNode = watcher.node()
    app.aspect2d.node().setMouseWatcher(watcher.node())
    watcher.node().addRegion(PGMouseWatcherBackground())
    results = {}

    def step(count=4):
        for _ in range(count):
            app.taskMgr.step()
            app.graphicsEngine.renderFrame()

    def point(node, x, z):
        pos = app.render2d.getRelativePoint(node, Point3(x, 0, z))
        mouse.setMousePos(round((pos.x + 1) * width / 2), round((1 - pos.z) * height / 2))
        step()

    def click():
        mouse.pressButton(MouseButton.one())
        step()
        mouse.releaseButton(MouseButton.one())
        step()

    try:
        step()
        for name, menu in (("vehicle", app.vehicle_menu), ("maneuver", app.maneuver_menu),
                           ("abs", app.abs_menu), ("plot", app.plot_menu),
                           ("esc", app.esc_menu)):
            if name == "esc":
                app.advanced_panel.show()
                step()
            point(menu, .30, 0)
            click()
            assert not menu.popupMenu.isHidden(), name
            popup_pos = menu.popupMenu.getPos(app.render2d)
            popup_scale = menu.popupMenu.getScale(app.render2d)
            assert popup_pos.z <= .991 and popup_pos.z - menu.maxHeight * len(menu["items"]) * popup_scale.z >= -.991
            assert popup_pos.x >= -.991 and popup_pos.x + menu.maxWidth * popup_scale.x <= .991
            # 每行中心及靠右区域均持续悬停；捕捉命中区缩小导致的进出循环。
            for index in range(len(menu["items"])):
                item = menu.component(f"item{index}")
                bounds, text_scale = tuple(item["frameSize"]), item["text_scale"]
                for fraction in (.5, .95):
                    point(item, bounds[0] + fraction * (bounds[1] - bounds[0]), 0)
                    for _ in range(12):
                        step(1)
                        assert menu.highlightedIndex == index, (name, index)
                        assert tuple(item["frameSize"]) == bounds
                        assert item["text_scale"] == text_scale
            selected = len(menu["items"]) // 2
            point(menu.component(f"item{selected}"), .30, 0)
            for _ in range(120):
                step(1)
                assert menu.highlightedIndex == selected, name
            path = output / f"{name}-hover.png"
            assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
            click()
            assert menu.selectedIndex == selected and menu.get() == menu["items"][selected]
            assert menu.popupMenu.isHidden() and menu.cancelFrame.isHidden()
            point(menu, .30, 0)
            click()
            mouse.setMousePos(width - 2, height - 2)
            step()
            click()
            assert menu.popupMenu.isHidden() and menu.cancelFrame.isHidden()
            results[name] = {"rows": len(menu["items"]), "row_height": menu.maxHeight,
                             "steady_hover_frames": 120, "edge_hover_frames_per_row": 24,
                             "selection": menu.get(), "outside_click_closes": True}
        assert app.run_state is None
        (output / "result.json").write_text(json.dumps(
            {"height": height, "menus": results, "physics_rerun": False},
            ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--height", type=int, choices=(720, 1080), required=True)
    args = parser.parse_args()
    check(args.output.resolve(), args.height)
