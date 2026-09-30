"""只在独立节点上比较Panda原生合批策略，不修改游戏运行实现。"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from panda3d.core import NodePath, SceneGraphAnalyzer
from test_expressway import AssetLoader

from environment.expressway import KIT_NAMES, LANDSCAPE_NAMES, SIGN_NAMES, load_kit
from highway_curve import HighwayCurve
from scene import Scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    parent = NodePath("probe-templates")
    scene = Scene.__new__(Scene)
    trees = [scene.load_model(f"nature/tree_pineTall{x}.glb") for x in ("A", "B")]
    kit = load_kit(AssetLoader(), parent, trees)
    started = time.perf_counter()
    for name in KIT_NAMES + SIGN_NAMES + LANDSCAPE_NAMES + ("tree-0", "tree-1"):
        kit[name].clearModelNodes()
        kit[name].flattenStrong()
    template_ms = (time.perf_counter() - started) * 1000
    source = (ROOT / "src/environment/expressway_route.py").read_text(encoding="utf-8")
    if "    root.clearModelNodes()\n    root.flattenStrong()" not in source:
        raise RuntimeError("此历史探针只适用暂停前同步源码；当前版本用benchmark_runtime.py测量")
    replacements = {
        "full": "    root.clearModelNodes()\n    root.flattenStrong()",
        "spatial": '''    road_batch = root.attachNewNode("road-batch")
    for child in root.getChildren():
        if child != road_batch and not isinstance(child.node(), LODNode):
            child.reparentTo(road_batch)
    road_batch.clearModelNodes()
    road_batch.flattenStrong()
    buckets = {}
    for child in list(details.getChildren()):
        number = math.floor(child.getY() / 20)
        if number not in buckets:
            buckets[number] = NodePath("detail-cell")
        child.reparentTo(buckets[number])
    for batch in buckets.values():
        started = time.perf_counter()
        batch.clearModelNodes()
        batch.flattenStrong()
        batch.reparentTo(details)
        batch_ms.append((time.perf_counter() - started) * 1000)''',
    }
    results = {"template_ms": template_ms, "kind": "CPU microprobe; not FPS"}
    for label, replacement in replacements.items():
        local_source = source.replace(replacements["full"], replacement)
        space = {"__name__": "environment.batching_probe", "time": time,
                 "NodePath": NodePath, "batch_ms": []}
        exec(compile(local_source, label, "exec"), space)  # noqa: S102
        curve = HighwayCurve(23, hills=True)
        rows = []
        for index in (7, 8, 9, 10, 11):
            root = NodePath("probe")
            started = time.perf_counter()
            space["build_segment"](root, index, 23, kit, lambda n: None, curve)
            elapsed = (time.perf_counter() - started) * 1000
            graph = SceneGraphAnalyzer()
            graph.addNode(root.node())
            rows.append({"index": index, "ms": elapsed, "geoms": graph.getNumGeoms(),
                         "triangles": graph.getNumTris()})
            root.removeNode()
        results[label] = {"rows": rows, "batch_ms": space["batch_ms"]}
    parent.removeNode()
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
