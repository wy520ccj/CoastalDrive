"""离线过滤Poly Haven实拍HDRI；游戏只载入已过滤的车库反射。"""

import argparse
import math
from pathlib import Path

from panda3d.core import Filename, PfmFile, Texture, Vec3
from simplepbr.envmap import EnvMap

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/sources/skylit_garage_2k.hdr'
OUTPUT = ROOT/'assets/game/vehicles/garage-skylit.env'


def equirectangular_cube(image, size, *, longitude_offset=0., radiance_limit=None):
    """经纬图顶行为天顶；PfmFile到Texture会翻转图像行，按原生取样方向展开。"""
    cube = Texture('polyhaven-skylit-garage')
    cube.setupCubeMap(size, Texture.TFloat, Texture.FRgb16)
    for face in range(6):
        pixels = PfmFile()
        pixels.clear(size, size, 3)
        for row in range(size):
            for col in range(size):
                u, v = 2*(col+.5)/size-1, 2*(row+.5)/size-1
                x, y, z = ((1, v, -u), (-1, v, u), (u, 1, -v),
                           (u, -1, v), (u, v, 1), (-u, v, -1))[face]
                length = math.sqrt(x*x+y*y+z*z)
                longitude = (math.atan2(y, x)/(2*math.pi)+.5+longitude_offset) % 1
                latitude = .5-math.asin(z/length)/math.pi
                # 经度环绕、纬度夹边，双线性采样避免反射里出现原图像素跳变。
                sx, sy = longitude*image.getXSize()-.5, latitude*image.getYSize()-.5
                ix, iy = math.floor(sx), math.floor(sy)
                fx, fy = sx-ix, sy-iy
                color = sum((image.getPoint3((ix+dx) % image.getXSize(),
                    max(0, min(image.getYSize()-1, iy+dy)))*weight
                    for dx, dy, weight in ((0, 0, (1-fx)*(1-fy)), (1, 0, fx*(1-fy)),
                                          (0, 1, (1-fx)*fy), (1, 1, fx*fy))),
                    Vec3())
                if radiance_limit is not None and max(color) > radiance_limit:
                    color *= radiance_limit/max(color)
                pixels.setPoint3(col, row, color)
        assert cube.load(pixels, face, 0)
    cube.generateRamMipmapImages()
    return cube


def prepare(output=OUTPUT, size=128):
    image = PfmFile()
    if not image.read(Filename.fromOsSpecific(str(SOURCE))):
        raise OSError(f'无法读取HDRI：{SOURCE}')
    cube = equirectangular_cube(image, size)
    environment = EnvMap(cube, prefiltered_size=size, prefiltered_samples=64, blocking_prepare=True)
    environment.write(Filename.fromOsSpecific(str(output)))
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--size', type=int, default=128)
    args = parser.parse_args()
    prepare(args.output.resolve(), args.size)
