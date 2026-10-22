"""方向编码的经纬图经原生立方体采样后，世界方向与接缝必须保持。"""

import math

import pytest
from panda3d.core import LColor, PfmFile, Vec3
from vehicles.prepare_garage_environment import equirectangular_cube


def test_environment_roundtrip_keeps_world_directions_across_all_faces():
    image = PfmFile()
    image.clear(256, 128, 3)
    for row in range(128):
        latitude = (.5-(row+.5)/128)*math.pi
        for col in range(256):
            longitude = ((col+.5)/256-.5)*2*math.pi
            direction = Vec3(math.cos(latitude)*math.cos(longitude),
                             math.cos(latitude)*math.sin(longitude), math.sin(latitude))
            image.setPoint3(col, row, (direction+Vec3(1, 1, 1))*.5)
    cube = equirectangular_cube(image, 64)
    peeker = cube.peek()
    # 由Panda原生TexturePeeker按世界向量选面；不复制转换工具的面向公式作判定。
    for axis in range(3):
        for sign in (-1, 1):
            for a, b in ((0., 0.), (.65, -.25), (-.35, .75), (.999, -.6)):
                direction = Vec3()
                direction[axis] = sign
                direction[(axis+1) % 3], direction[(axis+2) % 3] = a, b
                direction.normalize()
                color = LColor()
                peeker.lookup(color, *direction)
                assert tuple(color.xyz) == pytest.approx(tuple((direction+Vec3(1, 1, 1))*.5), abs=.015)
