"""离线制作主车的小型柔光反射环境；不在游戏循环捕获或过滤立方体贴图。"""

import math
from pathlib import Path

from panda3d.core import Filename, PNMImage, Texture
from simplepbr.envmap import EnvMap

ROOT = Path(__file__).resolve().parents[2]
SIZE = 64
cube = Texture("vehicle-neutral-daylight")
cube.setupCubeMap(SIZE, Texture.TFloat, Texture.FRgb16)
for face in range(6):
    image = PNMImage(SIZE, SIZE, 3)
    for row in range(SIZE):
        for col in range(SIZE):
            u, v = 2 * (col + 0.5) / SIZE - 1, 2 * (row + 0.5) / SIZE - 1
            direction = (
                (1, -u, -v),
                (-1, u, -v),
                (u, 1, -v),
                (-u, -1, -v),
                (u, -v, 1),
                (u, v, -1),
            )[face]
            length = math.sqrt(sum(a * a for a in direction))
            x, y, z = (a / length for a in direction)
            # 低亮度地面、天空和窄亮带分开，避免四面均匀发灰。
            horizon = math.exp(-(((z - 0.035) / 0.06) ** 2))
            sky = max(0, z)
            softbox = math.exp(-(((x - 0.58) / 0.15) ** 2) - ((z - 0.52) / 0.22) ** 2) * 1.1
            side_light = math.exp(-(((y + 0.8) / 0.18) ** 2) - ((z - 0.35) / 0.20) ** 2) * 0.45
            color = (
                0.012 + 0.10 * sky + 0.22 * horizon + softbox + side_light,
                0.016 + 0.14 * sky + 0.24 * horizon + softbox + side_light,
                0.021 + 0.20 * sky + 0.26 * horizon + softbox + side_light,
            )
            image.setXel(col, row, *color)
    assert cube.load(image, face, 0)
cube.generateRamMipmapImages()
environment = EnvMap(cube, prefiltered_size=64, prefiltered_samples=32, blocking_prepare=True)
path = ROOT / "assets/game/vehicles/reflection-probe.env"
environment.write(Filename.fromOsSpecific(str(path)))
print(path)
