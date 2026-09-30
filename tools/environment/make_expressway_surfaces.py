"""离线制作快速路专用晴空与表面；照片只参考配色，不采样/复制像素。"""

import hashlib
import json
import math
from pathlib import Path

from panda3d.core import Filename, PNMImage

OUT = Path(__file__).resolve().parents[2] / "assets/game/expressway"


def noise(x, y, period=256):
    """周期平滑值噪声，用于可重建的多尺度材质。"""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)

    def value(a, b):
        n = ((a % period) * 374761393 + (b % period) * 668265263 + 437) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return (n ^ (n >> 16)) / 0xFFFFFFFF

    a = value(ix, iy) * (1 - fx) + value(ix + 1, iy) * fx
    b = value(ix, iy + 1) * (1 - fx) + value(ix + 1, iy + 1) * fx
    return a * (1 - fy) + b * fy


def smooth(a, b, value):
    t = max(0, min(1, (value - a) / (b - a)))
    return t * t * (3 - 2 * t)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    sky = PNMImage(2048, 1024, 3)
    for y in range(1024):
        elevation = max(0, 1 - y / 511.5)
        blend = min(1, elevation * 2.7) ** 0.6
        horizon, zenith = (0.73, 0.83, 0.87), (0.20, 0.48, 0.73)
        base = [a * (1 - blend) + b * blend for a, b in zip(horizon, zenith)]
        for x in range(2048):
            u, v = x / 2048, y / 1024
            broad = noise(u * 32, v * 16, 32)
            detail = (noise(u * 128, v * 64, 128) * 0.55
                      + noise(u * 256, v * 128, 256) * 0.30
                      + noise(u * 512, v * 256, 512) * 0.15)
            shape = broad * 0.66 + detail * 0.34
            # 小团积云与蓝天留白，较高频轮廓防止低仰角下变成模糊白带。
            band = smooth(0.015, 0.055, elevation) * (1 - smooth(0.32, 0.54, elevation))
            cloud = smooth(0.575, 0.68, shape) * band * .7
            shade = 0.79 + 0.17 * smooth(0.3, 0.7, detail)
            sky.setXel(x, y, *(c * (1 - cloud) + shade * cloud for c in base))
    sky.write(Filename.fromOsSpecific(str(OUT / "expressway-sky.png")))
    for name in ("aggregate",):
        image = PNMImage(256, 256, 3)
        for y in range(256):
            for x in range(256):
                coarse = noise(x / 32, y / 32, 8)
                fine = noise(x / 4, y / 4, 64)
                grain = noise(x, y, 256)
                value = 0.79 + 0.055 * coarse + 0.12 * grain + 0.035 * fine
                color = (value, value, value)
                image.setXel(x, y, *color)
        image.write(Filename.fromOsSpecific(str(OUT / f"{name}.png")))
    files = ["expressway-sky.png", "aggregate.png", "grass-albedo.png", "strata-albedo.png"]
    manifest = {
        "source": "Original deterministic expressway surface and daylight artwork",
        "editable_source": "tools/environment/make_expressway_surfaces.py",
        "rights": "Original procedural sky and aggregate; grass/strata albedos generated with OpenAI imagegen; photographs are reference only",
        "reference": "https://www.w-nexco.co.jp/drive_porter/photo_contest/contest23/",
        "reference_use": "Daylight sky, airy ridge layers and coastal motorway earthworks; no copied pixels",
        "files": {name: hashlib.sha256((OUT / name).read_bytes()).hexdigest() for name in files},
    }
    (OUT / "surface-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Expressway surface artwork rebuilt")


if __name__ == "__main__":
    build()
