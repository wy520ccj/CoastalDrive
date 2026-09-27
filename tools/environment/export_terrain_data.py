"""输出地貌与局部草丛数据给 Blender；不把生产数据加载进游戏。"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from coastal_map import offset_point, point_at
from environment.terrain import ground_height, landscape_meshes


def ground_cover():
    rng = random.Random(401)
    vertices = []
    faces = []
    colors = []
    for cs, cd in (
        (20, 9),
        (44, 10),
        (84, 10),
        (103, 10),
        (128, 11),
        (148, 11),
        (290, 9),
        (319, 10),
    ):
        for _ in range(45):
            s, d = cs + rng.uniform(-8, 8), cd + rng.uniform(-1.4, 3.0)
            x, y, _ = offset_point(point_at(s), -d)
            z = ground_height(x, y) - 0.04
            for _ in range(5):
                a = rng.uniform(0, math.tau)
                h = rng.uniform(0.18, 0.45)
                w = 0.035
                dx, dy = math.cos(a), math.sin(a)
                i = len(vertices)
                vertices.extend(
                    (
                        (x - dy * w, y + dx * w, z),
                        (x + dy * w, y - dx * w, z),
                        (x + dx * h * 0.25, y + dy * h * 0.25, z + h),
                    )
                )
                faces.append((i, i + 1, i + 2))
                colors.extend(
                    ((0.15, 0.22, 0.025, 1), (0.17, 0.24, 0.03, 1), (0.36, 0.41, 0.10, 1))
                )
    return {"name": "ground-cover", "vertices": vertices, "faces": faces, "colors": colors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data = landscape_meshes() + [ground_cover()]
    args.output.write_text(json.dumps(data), encoding="utf-8")
    print("Terrain triangles:", sum(len(m["faces"]) for m in data))


if __name__ == "__main__":
    main()
