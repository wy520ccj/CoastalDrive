"""渲染加载边界和草木渐隐；固定画面回读单独记账，不作FPS样本。"""

import argparse
import json
import os
import sys
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output / "user-data")
    from panda3d.core import Filename, PNMImage, Vec3

    from application import CoastalDrive
    from environment.expressway_route import sample

    app = CoastalDrive(smoke=True, track="endless", road_shape="hills", seed=23,
                       output=args.output, render_size=(1920, 1080))
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()

    def capture(name):
        app.taskMgr.step()
        for _ in range(5):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        texture = app.win.getScreenshot()
        image = PNMImage()
        assert texture.store(image)
        assert texture.write(Filename.fromOsSpecific(str(args.output / f"{name}.png")))
        return image

    def changed_pixels(a, b, region):
        x0, y0, x1, y1 = region
        return sum(max(abs(a.getXel(x,y)[i]-b.getXel(x,y)[i]) for i in range(3)) > .02
                   for y in range(y0,y1) for x in range(x0,x1))

    report = {"kind": "rendered transitions; not performance or human acceptance"}
    try:
        sim = app.session.simulation
        curve = sim.stream.curve
        distance = 208
        center = sample(curve, distance)
        sim.origin_y = center.y
        sim.stream.update(distance, sim.origin_y, [])
        app.scene.sync_segments()
        camera = center - Vec3(0,sim.origin_y,0) + Vec3(0,0,3.4)
        app.camera.setPos(camera)
        app.camera.lookAt(sample(curve,distance+45)-Vec3(0,sim.origin_y,0)+Vec3(0,0,1.9))
        app.scene.sky.setPos(camera)
        app.scene.update_lighting(camera)
        # 模拟新远端段挂入，保持镜头、灯光和所有其他节点完全一致。
        index = max(sim.stream.segments)
        node = app.scene.segment_nodes[index]
        node.hide()
        before = capture("far-before-attach")
        node.show()
        after = capture("far-after-attach")
        pop = changed_pixels(before,after,(0,0,1920,550))
        report["horizon_attach_changed_pixels_over_2_percent"] = pop
        report["near_field_changed_pixels"] = changed_pixels(before,after,(0,550,1920,1080))
        assert pop == 0, f"远端分段挂入改变了地平线区域{pop}个像素"
        for child in app.scene.render.getChildren():
            if child != app.scene.sky:
                child.hide()
        marker = app.scene.expressway_kit["broadleaf-a"].copyTo(app.scene.render)
        marker.setScale(3)
        marker.setPos(0,300,0)
        rows = []
        region = (700,280,1220,800)
        for distance in (400,430,470,500,530,560,590):
            camera = Vec3(0,300-distance,9)
            app.camera.setPos(camera)
            app.camera.lookAt(0,300,9)
            app.scene.sky.setPos(camera)
            app.scene.update_lighting(camera)
            marker.hide()
            background = capture(f"detail-{distance}-background")
            marker.show()
            marker.setShader(app.scene.expressway_kit["distance-shader"], 1)
            opaque = capture(f"detail-{distance}-opaque")
            marker.setShader(app.scene.expressway_kit["detail-shader"], 1)
            faded = capture(f"detail-{distance}-fade")
            total = changed_pixels(opaque,background,region)
            visible = changed_pixels(faded,background,region)
            assert total > 0
            rows.append({"distance_m": distance, "opaque_pixels": total,
                         "visible_pixels": visible, "coverage": visible/total})
        assert rows[0]["coverage"] >= .95
        assert rows[-1]["visible_pixels"] == 0
        assert all(b["coverage"] <= a["coverage"] + .04 for a,b in pairwise(rows))
        report.update(passed=True, details=rows)
    finally:
        app.close_game()
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
