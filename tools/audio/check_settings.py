"""声音设置最长电台名称、七行按钮及实际双分辨率截图。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, TextNode

from application import CoastalDrive


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", choices=("1280x720", "1920x1080"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    size = tuple(map(int, args.size.split("x")))
    args.output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, output=args.output, render_size=size)
    app.taskMgr.remove("finish-smoke")
    try:
        app.back_to_menu()
        app.audio_settings.radio_station = 2
        app.choose_audio_settings()
        widths, bottoms = [], []
        node = TextNode("settings-width")
        node.setFont(app.ui_font)
        for button in app.buttons[:app.panel_option_count]:
            widths.append(node.calcWidth(button["text"]) * button["text_scale"][0])
            bottoms.append(button.getZ() + button["frameSize"][2])
        app.taskMgr.step()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        app.win.saveScreenshot(Filename.fromOsSpecific(str(args.output / "settings.png")))
        report = {"passed": app.panel_option_count == 7 and max(widths) <= .941
                  and min(bottoms) >= -.78,
                  "resolution": size, "text_widths": widths, "button_bottoms": bottoms,
                  "station": app.audio_settings.radio_station}
        (args.output / "report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
        return 0 if report["passed"] else 1
    finally:
        app.close_game()


if __name__ == "__main__":
    raise SystemExit(main())
