"""离屏渲染像素界面页面，用于和 graphic_design 设计图做人工对照。

默认实例化真实的 CoastalDrive（新菜单已接线），只截界面不进入驾驶；
也可以渲染独立页面构件做像素级核对。这不是画面验收，只是对照证据。

用法：
    python tools/ui_preview.py --page menu --size 1672x941 --output logs/ui-preview/menu.png
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, loadPrcFileData

PAGES = ("menu", "parts")


def parse_size(value):
    width, height = value.split("x")
    return int(width), int(height)


def capture_parts(app, canvas, skin):
    """独立渲染界面构件，用于像素级核对配色与按钮状态。"""
    from direct.gui.OnscreenText import OnscreenText
    from panda3d.core import TextNode

    import ui_theme as theme
    from ui_components import PixelButton

    OnscreenText(text="界面构件", font=canvas.font, fg=theme.WHITE,
                 scale=canvas.uy(theme.FONT_TITLE), pos=(canvas.x(60), canvas.y(60)),
                 align=TextNode.ALeft)
    layout = (
        ("主操作", True, "", "wide", theme.FONT_HEADING),
        ("普通按钮", False, "", "wide", theme.FONT_BODY),
        ("菜单按钮", False, "", "menu", theme.FONT_HEADING),
        ("次级按钮", False, "", "mid", theme.FONT_BODY),
        ("小按钮", False, "", "small", theme.FONT_BODY),
    )
    for index, (label, primary, style, size, font_scale) in enumerate(layout):
        button = PixelButton(app.aspect2d, canvas, skin, (60, 140 + index * 84, 420, 62),
                             label, None, primary=primary, font_scale=font_scale, size=size)
        if style:
            button.set_style(style)
    icons = ("clock", "car", "road", "bridge", "wheel", "restart", "home", "volume",
             "exit", "check", "warning", "collision", "checkpoint", "flag", "trophy", "palm")
    for index, name in enumerate(icons):
        row, column = divmod(index, 8)
        skin.picture(f"icon-{name}", app.aspect2d, canvas,
                     640 + column * 84, 160 + row * 84, 56, 56)


def enter_state(app, state):
    """把应用切到指定页面状态，用于逐页离屏核对。"""
    from dataclasses import replace

    from race import GameMode
    from session import Phase

    app.session.menu()
    if state == "pause":
        app.session.phase = Phase.PAUSED
    elif state == "audio":
        app.choose_audio_settings()
    elif state == "highway":
        app.choose_highway()
    elif state == "results-ok":
        app.session.race.snapshot = replace(app.session.race.snapshot, finished=True,
                                            last_lap=123.456, best_lap=123.456)
        app.session.phase = Phase.RESULTS
    elif state == "results-fail":
        app.session.race.snapshot = replace(app.session.race.snapshot, finished=True,
                                            last_lap=98.7, best_lap=95.2,
                                            invalidated=True, invalid_reason="发生碰撞，计时挑战已中止")
        app.session.phase = Phase.RESULTS
    elif state == "free-drive-end":
        app.session.mode = GameMode.FREE_DRIVE
        app.session.finish()
    elif state == "distance-fail":
        app.start_game(mode=GameMode.DISTANCE_CHALLENGE, track="endless")
        app.session.highway.snapshot = replace(
            app.session.highway.snapshot, challenge=True, succeeded=False,
            reason="车辆复位后本次五公里无碰撞挑战结束", distance=3240, elapsed=92.4, collisions=1)
        app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", choices=PAGES, default="menu")
    parser.add_argument("--state", default="menu",
                        choices=("menu", "pause", "audio", "highway", "results-ok",
                                 "results-fail", "free-drive-end", "distance-fail"))
    parser.add_argument("--size", default="1672x941")
    parser.add_argument("--output", type=Path, default=ROOT / "logs/ui-preview/page.png")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    width, height = parse_size(args.size)

    from application import CoastalDrive
    from ui_components import Canvas, UiSkin

    app = CoastalDrive(seed=args.seed, new_ui=True, smoke=True, driver=False,
                       render_size=(width, height))
    # CoastalDrive 按传入尺寸写死了窗口大小，这里再确认一次离屏宽高
    loadPrcFileData("ui-preview", f"win-size {width} {height}\nwindow-type offscreen")
    canvas = Canvas(app)
    skin = UiSkin(app.loader)
    if args.page == "parts":
        capture_parts(app, canvas, skin)
    else:
        enter_state(app, args.state)

    def capture(task):
        # doMethodLater 的任务里 task.time 是延迟到期后的相对时间，
        # 所以等待只能靠延迟本身；这里直接出图。
        args.output.parent.mkdir(parents=True, exist_ok=True)
        app.graphicsEngine.renderFrame()
        app.win.saveScreenshot(Filename.fromOsSpecific(str(args.output)))
        print(f"截图：{args.output} ({width}x{height}, scale={canvas.scale:.3f})")
        app.userExit()
        return task.done

    app.taskMgr.doMethodLater(0.6, capture, "capture-preview")
    app.run()
    app.close_game()


if __name__ == "__main__":
    main()
