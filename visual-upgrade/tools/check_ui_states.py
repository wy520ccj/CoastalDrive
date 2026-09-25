"""检查各状态下界面互斥：像素页面与旧 HUD 不能同时出现。

真实故障：从暂停恢复驾驶后，暂停页没有被销毁，旧 HUD 又打开了，
两套界面叠在一起。这里遍历所有状态并断言互斥，避免再退化。

用法：python tools/check_ui_states.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import loadPrcFileData

# 状态名 -> (阶段, 期望的像素页)
STATES = (
    ("菜单", "menu", "menu"),
    ("驾驶", "driving", None),
    ("暂停", "paused", "pause"),
    ("声音设置", "audio", "audio"),
    ("高速设置", "highway", "highway"),
    ("结算", "results", "results"),
    ("车库(旧面板)", "garage", None),
    ("返回菜单", "menu", "menu"),
)


def main():
    loadPrcFileData("check", "window-type offscreen\naudio-library-name null\n"
                             "win-size 1280 720")
    from dataclasses import replace

    from application import CoastalDrive
    from session import Phase

    app = CoastalDrive(new_ui=True, smoke=True, driver=False)
    hud = ("speed_frame", "telemetry_frame", "status_frame", "help_frame", "panel",
           "result_card")
    failures = []

    for label, state, expected in STATES:
        # 每个状态从干净起点开始，避免上一个子页的标志残留
        app.audio_settings_page = False
        app.highway_menu = False
        if app.garage is not None:
            app.cancel_garage()
        if state == "menu":
            app.session.menu()
        elif state == "driving":
            app.session.start(countdown=False)
            app.session.phase = Phase.DRIVING
        elif state == "paused":
            app.session.phase = Phase.PAUSED
        elif state == "audio":
            app.session.menu()
            app._shown_phase = None
            app.choose_audio_settings()
        elif state == "highway":
            app.session.menu()
            app._shown_phase = None
            app.choose_highway()
        elif state == "results":
            app.session.start(countdown=False)
            app.session.race.snapshot = replace(app.session.race.snapshot, finished=True,
                                                last_lap=100.0, best_lap=100.0)
            app.session.phase = Phase.RESULTS
        elif state == "garage":
            app.session.menu()
            app._shown_phase = None
            app.choose_garage()
        app._shown_phase = None
        app.refresh_panel()

        page_alive = app.page is not None
        shown = [name for name in hud if not getattr(app, name).isHidden()]
        if expected is None:
            if page_alive:
                failures.append(f"{label}：该状态不应留下像素页面（page_name={app.page_name}）")
            if not shown:
                failures.append(f"{label}：该状态应由旧界面承担，但没有任何旧面板可见")
        else:
            if not page_alive or app.page_name != expected:
                failures.append(f"{label}：期望像素页 {expected}，实际 {app.page_name}")
            if shown:
                failures.append(f"{label}：像素页与旧 HUD 叠加，仍可见 {shown}")
        print(f"{label}: 像素页={app.page_name} 旧HUD可见={shown or '无'}")

    if failures:
        print("失败：")
        for line in failures:
            print("  ", line)
        return 1
    print("全部状态界面互斥通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
