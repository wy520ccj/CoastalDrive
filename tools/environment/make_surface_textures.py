"""离线生成克制的平铺笔触纹理；颜色由环境材质提供。"""

import math
import random
from pathlib import Path

from panda3d.core import Filename, PNMImage

ROOT = Path(__file__).resolve().parents[2]


def main():
    output = ROOT / "assets/game/environment/materials"
    output.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(("asphalt", "meadow", "limestone")):
        rng = random.Random(431 + index)
        image = PNMImage(256, 256, 3)
        for y in range(256):
            for x in range(256):
                sx, sy = x * math.tau / 256, y * math.tau / 256
                noise = rng.uniform(-0.06, 0.06)
                if name == "asphalt":
                    shade = 0.86 + noise
                elif name == "meadow":
                    shade = 0.84 + 0.018 * math.sin(sx * 3 + math.sin(sy * 2)) + noise
                else:
                    shade = 0.84 + 0.055 * math.sin(sy * 8 + math.sin(sx * 3)) + noise
                image.setXel(x, y, shade, shade, shade)
        assert image.write(Filename.fromOsSpecific(str(output / f"{name}.png")))


if __name__ == "__main__":
    main()
