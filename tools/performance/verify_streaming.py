"""固定视点与Scene复用检查；截图不计入性能样本。"""

import argparse
import json
import os
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--original", type=Path)
    parser.add_argument("--pipeline", choices=("single", "draw", "cull-draw"), default="draw")
    args = parser.parse_args()
    args.output = args.output.resolve()
    if args.original:
        args.original = args.original.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    if args.original:
        import environment

        for name in ("environment.expressway_materials", "environment.expressway",
                     "environment.expressway_route", "environment.expressway_mountains", "scene"):
            path = args.original / (name.rsplit(".", 1)[-1] + ".py")
            module = ModuleType(name)
            module.__file__ = str(path)
            sys.modules[name] = module
            if name.startswith("environment."):
                setattr(environment, name.split(".")[1], module)
            source = compile(path.read_text(encoding="utf-8"), str(path), "exec")
            exec(source, module.__dict__)  # noqa: S102
            if name == "environment.expressway_materials":
                def original_shader_path(shader_name):
                    from panda3d.core import Filename

                    return Filename.fromOsSpecific(str(args.original / "shaders" / shader_name))

                module.shader_path = original_shader_path
    from panda3d.core import Filename, SceneGraphAnalyzer, Vec3, loadPrcFileData

    from application import CoastalDrive
    from environment.expressway_route import sample
    from race import GameMode

    pipeline = {"single": "", "draw": "/Draw", "cull-draw": "Cull/Draw"}[args.pipeline]
    loadPrcFileData("verify-pipeline", "threading-model " + pipeline)
    app = CoastalDrive(smoke=True, track="endless", road_shape="hills", seed=23,
                       output=args.output, render_size=(1920, 1080),
                       threading_model=pipeline)
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.aspect2d.hide()
    views = []
    try:
        for shape in ("straight", "curves", "hills"):
            app.start_highway(shape, mode=GameMode.FREE_DRIVE)
            sim = app.session.simulation
            curve = sim.stream.curve
            for distance in (-2300, 170, 830, 8400):
                center = sample(curve, distance)
                sim.origin_y = center.y
                sim.stream.update(distance, sim.origin_y, [])
                app.scene.sync_segments()
                origin = Vec3(0, sim.origin_y, 0)
                camera = center - origin + Vec3(0, 0, 3.4)
                app.camera.setPos(camera)
                app.camera.lookAt(sample(curve, distance + 45) - origin + Vec3(0, 0, 1.9))
                app.scene.sky.setPos(camera)
                app.scene.update_lighting(camera)
                app.taskMgr.step()
                for _ in range(8):
                    app.graphicsEngine.renderFrame()
                app.graphicsEngine.syncFrame()
                name = f"{shape}-{distance}.png"
                assert app.win.saveScreenshot(Filename.fromOsSpecific(str(args.output / name)))
                graph = SceneGraphAnalyzer()
                for node in app.scene.segment_nodes.values():
                    graph.addNode(node.node())
                views.append({"shape": shape, "distance_m": distance, "file": name,
                              "triangles": graph.getNumTris(), "geoms": graph.getNumGeoms()})
            # 已移动到8.4km的Scene重开时必须在加载阶段补齐起点。
            scene = app.scene
            app.start_game(mode=GameMode.FREE_DRIVE, track="endless")
            assert app.scene is scene
            assert set(scene.segment_nodes) == set(app.session.simulation.stream.segments)
            app.back_to_menu()
            assert scene.render.isEmpty()
            assert app.scene is None
            app.start_highway(shape, mode=GameMode.FREE_DRIVE)
        # 绘制线程也经过既有滨海、车库、菜单的资源释放路径。
        app.start_game(mode=GameMode.FREE_DRIVE, track="coastal")
        for _ in range(8):
            app.taskMgr.step()
        app.back_to_menu()
        app.choose_garage()
        for _ in range(8):
            app.taskMgr.step()
        app.close_garage()
    finally:
        app.close_game()
    (args.output / "report.json").write_text(json.dumps({"passed": True,
        "kind": "static views and scene lifecycle; not FPS or human acceptance",
        "pipeline": args.pipeline, "original": str(args.original), "views": views}, indent=2),
        encoding="utf-8")
    print(f"12 views and three-shape restart/menu/garage lifecycle passed: {args.output}")


if __name__ == "__main__":
    main()
