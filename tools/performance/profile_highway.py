"""固定高速场景的CPU剖析与场景图统计；剖析帧率不用于验收。"""

import argparse
import cProfile
import json
import os
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from endurance_check import EnduranceDriver
from panda3d.core import SceneGraphAnalyzer

from application import CoastalDrive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(args.output.resolve() / "user-data")
    app = CoastalDrive(smoke=True, onscreen=True, track="endless", road_shape="hills",
                       seed=23, output=args.output, render_size=(1920, 1080))
    app.taskMgr.remove("finish-smoke")
    app.session.set_controller(EnduranceDriver(app.session.simulation, 724))
    rows = []
    for parent in (app.scene.render, *app.scene.segment_nodes.values()):
        for node in parent.getChildren():
            graph = SceneGraphAnalyzer()
            graph.addNode(node.node())
            rows.append({"parent": parent.getName(), "name": node.getName(),
                         "geoms": graph.getNumGeoms(), "tris": graph.getNumTris()})
    (args.output / "graph.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    profiler = cProfile.Profile()

    def stop(task):
        if task.time > 15:
            app.userExit()
            return task.done
        return task.cont

    app.taskMgr.add(stop, "profile-stop", sort=55)
    try:
        profiler.enable()
        app.run()
        profiler.disable()
    finally:
        app.close_game()
    profiler.dump_stats(str(args.output / "cpu.prof"))
    with (args.output / "cpu.txt").open("w", encoding="utf-8") as stream:
        pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats("cumulative").print_stats(65)


if __name__ == "__main__":
    main()
