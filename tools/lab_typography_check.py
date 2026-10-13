"""读取既有记录验证实验室字体；不重新运行物理。"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename

from lab_application import VehicleLab
from lab_records import load_record


def check(record_folder, output, height):
    output.mkdir(parents=True, exist_ok=False)
    app = VehicleLab(offscreen=True, render_size=(round(height * 16 / 9), height))
    screenshots = []

    def capture(name):
        app.taskMgr.step()
        app.graphicsEngine.renderFrame()
        app.graphicsEngine.renderFrame()
        path = output / f"{name}.png"
        if not app.win.saveScreenshot(Filename.fromOsSpecific(str(path))):
            raise RuntimeError(f"字体截图未保存：{path}")
        screenshots.append(path.name)

    try:
        app.import_record(record_folder)
        if app.record is None:
            raise RuntimeError(app.notice.getText())
        baseline = record_folder / "baseline-A"
        if baseline.is_dir():
            app.baseline = load_record(baseline)
        app.present_summary(app.record.metadata["summary"])
        app.refresh_plots()
        app.show_sample(len(app.record.samples) - 1)
        capture("01-workbench")
        app.toggle_advanced()
        capture("02-advanced")
        app.toggle_advanced()
        app.toggle_details()
        capture("03-signals")
        app.toggle_details()
        # 仅展开控件做排版检查，不创建手动试验物理世界。
        app.manual_panel.show()
        capture("04-manual")
        app.manual_panel.hide()
        app.toggle_record_menu()
        capture("05-records")
        assert app.run_state is None
        result = {"height": height, "record": str(record_folder),
                  "screenshots": screenshots, "physics_rerun": False}
        (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--height", type=int, choices=(720, 1080), required=True)
    args = parser.parse_args()
    check(args.record.resolve(), args.output.resolve(), args.height)
