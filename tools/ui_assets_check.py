"""复用既有状态夹具，检查资产 UI 的实际字体宽度并保存独立画面。"""

import argparse
import json
import os
from pathlib import Path

import ui_6b08_check as check
from panda3d.core import TextNode


def text_width(text, font, scale):
    probe = TextNode("asset-ui-measure")
    probe.setFont(font)
    return max((probe.calcWidth(line) * scale for line in text.split("\n")), default=0)


def bounds(app):
    buttons = app.main_menu.buttons if not app.main_menu.root.isHidden() else app.buttons
    for button in buttons:
        if button.isHidden():
            continue
        scale = button["text_scale"]
        if isinstance(scale, tuple):
            scale = scale[0]
        width = text_width(button["text"], app.ui_font, scale)
        left, right, _, _ = button["frameSize"]
        if button.component("text0").textNode.getAlign() == TextNode.ALeft:
            if button["text_pos"][0] + width > right - 0.055:
                return False
        elif width > right - left - 0.05:
            return False
    if not app.hud.root.isHidden():
        if text_width(app.status.getText(), app.display_font, app.status.getScale()[0]) > 0.80:
            return False
        if text_width(app.status_notice.getText(), app.ui_font, 0.034) > 0.80:
            return False
    if not app.panel.isHidden():
        if text_width(app.panel_note.getText(), app.ui_font, 0.040) > (0.99 if app.garage else 1.37):
            return False
        detail_scale = app.panel_detail.getScale()[0]
        if text_width(app.panel_detail.getText(), app.ui_font, detail_scale) > 1.75:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", choices=("1280x720", "1920x1080"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    check.OUTPUT = args.output.resolve()
    check.bounds = bounds
    states = check.run_resolution(tuple(map(int, args.size.split("x"))))
    states["01-main-menu"]["title"] = "COASTAL DRIVE"
    report = {"passed": all(s["text_fits"] for s in states.values()), "states": states,
              "kind": "real Panda3D render; fixture result states; human visual gate pending"}
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "states": len(states)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
