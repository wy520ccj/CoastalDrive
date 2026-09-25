"""沿真实 PGUI 事件路径验证按钮：悬停、按下、释放、点击都要能走通。

直接调 `command()` 会绕过事件处理，之前就是这样漏掉了 `DGG.BUTTON_PRESSED`
这个不存在的常量导致的崩溃。这里改为发送 DirectGui 实际 accept 的事件名
（`事件名 + guiId`），与真实鼠标点击走同一条路径。

用法：python tools/check_buttons.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import loadPrcFileData

PAGES = ("pause", "audio", "highway", "results-ok", "results-fail")
EVENTS = {"enter": "ENTER", "exit": "EXIT", "press": "B1PRESS",
          "release": "B1RELEASE", "click": "B1CLICK"}


def send(app, button, events):
    """按 DirectGui 注册的事件名发送，参数用 None 占位。"""
    from direct.gui import DirectGuiGlobals as DGG

    for event in events:
        app.messenger.send(getattr(DGG, EVENTS[event]) + button.guiId, [None])


def describe(tag, button):
    """输出拾取相关属性，便于和原界面实测可点的按钮对照。"""
    item = button.node()
    has_frame = item.hasFrame() if hasattr(item, "hasFrame") else True
    frame = item.getFrame() if has_frame else None
    shape = ("无 frame" if frame is None
             else f"frame=({frame[0]:.3f},{frame[1]:.3f},{frame[2]:.3f},{frame[3]:.3f})")
    parent = button.node().getParent(0).getName()
    return (f"{tag}: 类={type(item).__name__} active={item.getActive()} {shape} "
            f"父={parent}")


def attempt(failures, label, action):
    """执行一步并收集失败，保证一次跑完所有页面。"""
    try:
        action()
    except Exception as exc:  # noqa: BLE001 - 检查工具要报出任意处理器错误
        failures.append(f"{label}：{type(exc).__name__}: {exc}")


def check_pickable(failures, label, button):
    """鼠标拾取的前提：PGItem 必须有 frame 且处于激活状态。

    这一版 Panda3D 里子类化 DirectGui 控件会让 frame 消失，表现为“点击毫无反应
    也不报错”，所以这里作为硬断言。
    """
    item = button.node()
    if not item.hasFrame():
        failures.append(f"{label}: PGItem 没有 frame，鼠标永远点不到")
    if not item.getActive():
        failures.append(f"{label}: PGItem 未激活，收不到鼠标事件")


def main():
    loadPrcFileData("check", "window-type offscreen\naudio-library-name null\n"
                             "win-size 1280 720")
    from dataclasses import replace

    from application import CoastalDrive
    from race import GameMode
    from session import Phase

    app = CoastalDrive(new_ui=True, smoke=True, driver=False)
    failures = []

    def enter(state):
        app.session.menu()
        app._shown_phase = None
        if state == "pause":
            app.session.phase = Phase.PAUSED
        elif state == "audio":
            app.choose_audio_settings()
        elif state == "highway":
            app.choose_highway()
        elif state in ("results-ok", "results-fail"):
            app.session.race.snapshot = replace(
                app.session.race.snapshot, finished=True, last_lap=101.5,
                best_lap=101.5, invalidated=state == "results-fail",
                invalid_reason="发生碰撞",
            )
            app.session.phase = Phase.RESULTS
        app._shown_phase = None
        app.refresh_panel()

    enter("menu")
    buttons = app.page.buttons
    for index, button in enumerate(buttons):
        check_pickable(failures, f"menu 按钮{index}", button)
        attempt(failures, f"menu 按钮{index}",
                lambda b=button: send(app, b, ("enter", "press", "release", "exit")))
    print(f"menu: {len(buttons)} 个按钮，可拾取性与悬停/按下/释放已走通")
    print("  " + describe("新按钮", buttons[0]))
    print("  " + describe("原按钮(实测可点)", app.buttons[0]))

    def click_second():
        send(app, app.page.buttons[1], ("click",))
        if app.session.mode is not GameMode.FREE_DRIVE:
            failures.append("menu 按钮1 点击后没有进入自由驾驶")
        else:
            print(f"menu 按钮1 点击生效 -> {app.session.mode} / {app.session.phase}")

    attempt(failures, "menu 按钮1 点击", click_second)

    for state in PAGES:
        enter(state)
        for index, button in enumerate(app.page.buttons):
            check_pickable(failures, f"{state} 按钮{index}", button)
            attempt(failures, f"{state} 按钮{index}",
                    lambda b=button: send(app, b, ("enter", "press", "release", "exit")))
        print(f"{state}: {len(app.page.buttons)} 个按钮，可拾取性与悬停/按下/释放已走通")

    if failures:
        print("失败：")
        for line in failures:
            print("  ", line)
        return 1
    print("全部按钮的事件路径通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
