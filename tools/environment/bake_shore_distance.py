"""从视觉岸坡实际海平面交线烘焙水面距离，不凭圆形特效猜接触位置。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import numpy as np
from PIL import Image

from environment.terrain import shoreline_segments


def main():
    size = 768
    minimum = -256.0
    span = 640.0
    axis = minimum + (np.arange(size) + 0.5) * span / size
    x, y = np.meshgrid(axis, axis)
    best = np.full_like(x, 1e9)
    for p, q in shoreline_segments():
        dx, dy = q[0] - p[0], q[1] - p[1]
        t = np.clip(((x - p[0]) * dx + (y - p[1]) * dy) / (dx * dx + dy * dy), 0, 1)
        best = np.minimum(best, (x - p[0] - t * dx) ** 2 + (y - p[1] - t * dy) ** 2)
    mask = np.minimum(1, np.sqrt(best) / 40)
    path = ROOT / "assets/game/environment/materials/shore-distance.png"
    Image.fromarray((mask[::-1] * 255).astype("uint8")).save(path)
    (path.with_suffix(".json")).write_text(
        json.dumps({"minimum": minimum, "span": span, "range_m": 40, "size": size}),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
