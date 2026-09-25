"""把候选像素字体排在同一张图上对照，便于选定界面字体。

用法：python tools/preview_fonts.py [--size 24] [--output logs/ui-preview/fonts.png]
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, loadPrcFileData

FONT_DIR = ROOT / "assets/game/ui/fonts"
SAMPLE = "海岸驾驶 计时挑战 无限高速 已暂停 挑战成功 0123456789 km/h"
LABEL = "COASTAL DRIVE 0.8.3"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=32)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "logs/ui-preview/fonts.png")
    args = parser.parse_args()

    loadPrcFileData("fonts", "window-type offscreen\naudio-library-name null\n"
                             "win-size 1600 600\nsync-video 0")
    from direct.gui.OnscreenText import OnscreenText
    from direct.showbase.ShowBase import ShowBase

    app = ShowBase()
    app.setBackgroundColor(0.96, 0.94, 0.89, 1)
    fonts = sorted(FONT_DIR.glob("*.ttf"))
    for index, path in enumerate(fonts):
        font = app.loader.loadFont(Filename.fromOsSpecific(str(path)).getFullpath())
        font.setPixelsPerUnit(32)
        y = 0.62 - index * 0.34
        OnscreenText(text=f"{path.name}", font=font, fg=(0.4, 0.45, 0.5, 1),
                     scale=12 / 300, pos=(-1.5, y + 0.14), align=0)
        OnscreenText(text=SAMPLE, font=font, fg=(0.06, 0.17, 0.23, 1),
                     scale=args.size / 300, pos=(-1.5, y), align=0)
        OnscreenText(text=LABEL, font=font, fg=(0.96, 0.49, 0.14, 1),
                     scale=args.size / 300, pos=(-1.5, y - 0.16), align=0)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    app.graphicsEngine.renderFrame()
    app.graphicsEngine.renderFrame()
    app.win.saveScreenshot(Filename.fromOsSpecific(str(args.output)))
    print(f"字体对照：{args.output}（{len(fonts)} 种，字号 {args.size}）")
    app.destroy()


if __name__ == "__main__":
    sys.exit(main())
