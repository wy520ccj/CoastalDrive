"""固定光照与微移相机下检查路牌面；输出真实像素，不作为驾驶性能测试。"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from panda3d.core import Filename, PNMImage, Point2, Vec3

from application import CoastalDrive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    app = CoastalDrive(smoke=True, track="endless", seed=23, output=args.output,
                       render_size=(1920, 1080))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    app.scene.render.hide()
    app.scene.sun_path.node().setShadowCaster(False)
    records, tiles = [], []
    try:
        # 底色区的像素突变区分深度竞争与正常文字缩小；保持牌子及光照不动。
        for name, center, width, height in (("gantry", (0, 0, 7.1), 14.0, 2.4),
                                           ("route-direction", (0, 0, 3.3), 4.4, 1.5)):
            node = app.scene.expressway_kit[name].copyTo(app.render)
            for distance in (80, 200, 350, 480):
                coverage, pixels = [], []
                for frame in range(24):
                    app.camera.setPos(center[0] + frame * .007, -distance + frame * .043, center[2])
                    app.camera.lookAt(Vec3(*center))
                    app.taskMgr.step()
                    for _ in range(2):
                        app.graphicsEngine.renderFrame()
                    app.graphicsEngine.syncFrame()
                    path = args.output / f"{name}-{distance}-{frame:02d}.png"
                    assert app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
                    corners = []
                    for x, z in ((-width/2, -height/2), (width/2, height/2)):
                        screen = Point2()
                        assert app.camLens.project(app.cam.getRelativePoint(app.render,
                            Vec3(center[0]+x, -.8 if name == "gantry" else -.25, center[2]+z)), screen)
                        corners.append(((screen.x+1)*960, (1-screen.y)*540))
                    rect = (int(corners[0][0])+2, int(corners[1][1])+2,
                            int(corners[1][0])-2, int(corners[0][1])-2)
                    source = PNMImage()
                    source.read(Filename.fromOsSpecific(str(path)))
                    crop = PNMImage(rect[2]-rect[0], rect[3]-rect[1])
                    crop.copySubImage(source, 0, 0, rect[0], rect[1], crop.getXSize(), crop.getYSize())
                    white = sum(min(crop.getXel(x,y)) > 105/255
                                and max(crop.getXel(x,y))-min(crop.getXel(x,y)) < 45/255
                                for y in range(crop.getYSize()) for x in range(crop.getXSize()))
                    coverage.append(white / (crop.getXSize() * crop.getYSize()))
                    tile = PNMImage(320, 96)
                    tile.quickFilterFrom(crop)
                    pixels.append(tile)
                records.append({"model": name, "distance": distance,
                                "white_coverage_range": [min(coverage), max(coverage)],
                                "white_coverage_swing": max(coverage)-min(coverage)})
                tiles.extend(pixels[i] for i in (0, 5, 11, 17, 23))
            node.removeNode()
        sheet = PNMImage(1600, 8*96)
        for i, tile in enumerate(tiles):
            sheet.copySubImage(tile, (i % 5)*320, (i // 5)*96)
        sheet.write(Filename.fromOsSpecific(str(args.output / "faces.png")))
        (args.output / "report.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(json.dumps(records, indent=2))
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
