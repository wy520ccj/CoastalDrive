"""离线过滤Poly Haven实拍HDRI；游戏只载入已过滤的车库反射。"""

import math
from pathlib import Path

from panda3d.core import Filename, PfmFile, Texture
from simplepbr.envmap import EnvMap

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'art/vehicles/sources/skylit_garage_2k.hdr'
OUTPUT = ROOT/'assets/game/vehicles/garage-skylit.env'


def prepare():
    image = PfmFile()
    if not image.read(Filename.fromOsSpecific(str(SOURCE))):
        raise OSError(f'无法读取HDRI：{SOURCE}')
    size = 128
    cube = Texture('polyhaven-skylit-garage')
    cube.setupCubeMap(size, Texture.TFloat, Texture.FRgb16)
    for face in range(6):
        pixels = PfmFile()
        pixels.clear(size, size, 3)
        for row in range(size):
            for col in range(size):
                u, v = 2*(col+.5)/size-1, 2*(row+.5)/size-1
                x, y, z = ((1, -u, -v), (-1, u, -v), (u, 1, -v),
                           (-u, -1, -v), (u, -v, 1), (u, v, -1))[face]
                length = math.sqrt(x*x+y*y+z*z)
                longitude = (math.atan2(y, x)/(2*math.pi)+.5) % 1
                latitude = math.asin(z/length)/math.pi+.5
                color = image.getPoint3(int(longitude*(image.getXSize()-1)),
                                       int(latitude*(image.getYSize()-1)))
                pixels.setPoint3(col, row, color)
        assert cube.load(pixels, face, 0)
    cube.generateRamMipmapImages()
    environment = EnvMap(cube, prefiltered_size=128, prefiltered_samples=64, blocking_prepare=True)
    environment.write(Filename.fromOsSpecific(str(OUTPUT)))
    print(OUTPUT)


if __name__ == '__main__':
    prepare()
