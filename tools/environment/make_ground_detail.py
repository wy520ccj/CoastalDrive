"""生成地表细节调制纹理，离线制作，不在游戏循环生成像素。"""

import random
from pathlib import Path

from panda3d.core import Filename, PNMImage

root = Path(__file__).resolve().parents[2]
rng = random.Random(622)
n = 512
image = PNMImage(n, n, 3)
grids = {
    count: [[rng.random() for _ in range(count)] for _ in range(count)] for count in (4, 16, 64)
}


def noise(x, y, count):
    u, v = x * count / n, y * count / n
    ix, iy = int(u), int(v)
    u -= ix
    v -= iy
    u = u * u * (3 - 2 * u)
    v = v * v * (3 - 2 * v)
    g = grids[count]
    return (g[iy % count][ix % count] * (1 - u) + g[iy % count][(ix + 1) % count] * u) * (1 - v) + (
        g[(iy + 1) % count][ix % count] * (1 - u) + g[(iy + 1) % count][(ix + 1) % count] * u
    ) * v


for y in range(n):
    for x in range(n):
        shade = (
            0.55
            + 0.16 * noise(x, y, 4)
            + 0.20 * noise(x, y, 16)
            + 0.12 * noise(x, y, 64)
            + rng.uniform(-0.035, 0.035)
        )
        image.setXel(x, y, shade, shade, shade)
# 细短草叶与颗粒只有几厘米，留出大块底色避免棋盘感。
for _ in range(4500):
    x, y = rng.randrange(n), rng.randrange(n)
    length = rng.randrange(2, 9)
    value = rng.uniform(0.46, 0.98)
    for k in range(length):
        px, py = (x + k // 3) % n, (y + k) % n
        image.setXel(px, py, value, value, value)
image.write(
    Filename.fromOsSpecific(str(root / "assets/game/environment/materials/ground-detail.png"))
)
