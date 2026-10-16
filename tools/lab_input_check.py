"""通过Panda窗口输入设备检查编辑链路；实际鼠标/硬件键盘另由可见窗口复核。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from panda3d.core import Filename, KeyboardButton

from lab_application import VehicleLab
from lab_experiment import MANEUVERS


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    app = VehicleLab(output=output/"records")
    app.taskMgr.remove("lab-update")
    device = app.win.getInputDevice(0)
    results = {}

    def pump():
        for _ in range(3):
            app.taskMgr.step()

    def type_keys(entry, value):
        app.blur_entries()
        entry.enterText("")
        # 模拟鼠标获得的真实PGEntry焦点，保留过时的DirectEntry配置值为0。
        entry.guiItem.setFocus(True)
        pump()
        assert entry["focus"] == 0
        for char in value:
            key = KeyboardButton.asciiKey(char)
            device.buttonDown(key)
            device.keystroke(ord(char))
            device.buttonUp(key)
            pump()
        assert entry.get() == value, (value, entry.get())
        return entry.get()

    def capture(name):
        pump()
        app.graphicsEngine.renderFrame()
        path = output/f"{name}.png"
        assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))

    try:
        app.toggle_advanced()
        values = {"duration": "3.5", "steer": "-2.5", "cg": "0.45", "radius": "60",
                  "right_mu": "0.3", "onset": "0.6", "tire_load": "4000",
                  "bump_height": "0.01", "bump_length": "0.9", "bump_distance": "6"}
        calls = []
        app.accept("period", app.hotkey, [lambda: calls.append("step")])
        app.accept("space", app.hotkey, [lambda: calls.append("pause")])
        for key, value in values.items():
            results[key] = type_keys(app.entries[key], value)
        assert calls == []
        switches = []
        # 菜单开启、选择、面板开关后重新走窗口输入设备，检查连续切换后的编辑。
        for _ in range(2):
            for mode, label in MANEUVERS.items():
                app.entries["duration"].guiItem.setFocus(True)
                app.maneuver_menu.showPopupMenu()
                pump()
                assert not app.entries["duration"].guiItem.getFocus()
                app.maneuver_menu.set(label)
                app.maneuver_menu.hidePopupMenu()
                app.toggle_advanced()
                app.toggle_advanced()
                for key, value in values.items():
                    assert type_keys(app.entries[key], value) == value
                app.reset_parameters()
                assert app.read_options() == app.default_options(mode)
                switches.append(mode)
        # 退格与重新输入走同一窗口输入设备，不能只验证enterText赋值。
        entry = app.entries["bump_distance"]
        type_keys(entry, "6")
        device.buttonDown(KeyboardButton.backspace())
        device.buttonUp(KeyboardButton.backspace())
        pump()
        assert entry.get() == ""
        device.keystroke(ord("8"))
        pump()
        assert entry.get() == "8"
        capture("advanced-input")
        app.cycle_entry(1)
        assert app.entries["speed"].guiItem.getFocus()
        app.toggle_advanced()
        assert not any(entry.guiItem.getFocus() for entry in app.entries.values())
        for key, value in (("speed", "18"), ("mu", "1.3")):
            results[key] = type_keys(app.entries[key], value)
        assert calls == []
        app.blur_entries()
        app.messenger.send("period")
        assert calls == ["step"]
        app.manual_panel.show()
        for key, value in (("throttle", "25"), ("brake", "10"), ("gear", "-1"), ("clutch", "100")):
            results[f"manual.{key}"] = type_keys(app.manual_entries[key], value)
        capture("manual-input")
        app.escape()
        assert not any(entry.guiItem.getFocus() for entry in app.manual_entries.values())
        app.import_engineering(ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
        assert app.engineered_config.unsprung_enabled
        capture("engineering-ready")
        report = {"passed": True, "input_path": "GraphicsWindowInputDevice → MouseWatcher → PGEntry",
                  "values": results, "hidden_focus_released": True,
                  "maneuver_switches": switches,
                  "decimal_did_not_trigger_step": True, "human_acceptance": "pending"}
        (output/"summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        return report
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve()), ensure_ascii=False))
