"""从同一实拍晴空离线生成天空和环境照明，运行时不执行过滤。"""

import argparse
import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

from panda3d.core import Filename, PfmFile, Vec3
from simplepbr.envmap import EnvMap

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/vehicles'))
from prepare_garage_environment import equirectangular_cube


def prepare(source_folder, folder, *, azimuth=None, match_sun_elevation=False, sky_tint=None):
    original = json.loads((source_folder/'source.json').read_text(encoding='utf-8'))
    source = source_folder/original['file']
    image = PfmFile()
    if not image.read(Filename.fromOsSpecific(str(source))):
        raise OSError(f'无法读取晴空HDRI：{source}')
    width, height = image.getXSize(), image.getYSize()
    # 仅绕竖轴配准太阳方位，保持实拍天空地平线水平。
    if 'sun_pixel' in original:
        sx, sy = original['sun_pixel']
    else:
        light = max((sum(image.getPoint3(x, y)), x, y)
                    for y in range(0, height//2, 4) for x in range(0, width, 4))
        _, sx, sy = light
    target_heading = math.degrees(math.atan2(-75, -55)) if azimuth is None else azimuth
    heading = (target_heading-sx/width*360+180)%360-180
    elevation = 90-sy/height*180
    direction = Vec3(-55, -75, 125).normalized()
    if match_sun_elevation:
        angle, altitude = math.radians(target_heading), math.radians(elevation)
        direction = Vec3(math.cos(altitude)*math.cos(angle), math.cos(altitude)*math.sin(angle), math.sin(altitude))
    # 太阳直射由现有DirectionalLight负责，避免低分辨率环境图把太阳热点重复算入漫反射。
    cube = equirectangular_cube(image, 128, longitude_offset=-.5-heading/360, radiance_limit=4.)
    if sky_tint is not None:
        # 区域天空的艺术色平衡必须同步进入反射/漫反射，不能只改背景。
        for face in range(6):
            pixels = PfmFile()
            assert cube.store(pixels,face,0)
            for y in range(128):
                for x in range(128):
                    color = pixels.getPoint3(x,y)
                    pixels.setPoint3(x,y,tuple(color[i]*sky_tint[i] for i in range(3)))
            assert cube.load(pixels,face,0)
        cube.generateRamMipmapImages()
    environment = EnvMap(cube, prefiltered_size=128, prefiltered_samples=64, blocking_prepare=True)
    folder.mkdir(parents=True, exist_ok=True)
    environment.write(Filename.fromOsSpecific(str(folder/'daylight.env')))
    sky_name = 'daylight-sky'+source.suffix
    shutil.copyfile(source, folder/sky_name)
    report = {'source': original, 'sky_heading_degrees': heading,
              'source_sun_elevation_degrees': elevation,
              'directional_sun': list(direction),
              'cube_size': 128, 'prefiltered_samples': 64, 'indirect_radiance_limit': 4.,
              'sky_file': sky_name,
              'sky_sha256': hashlib.sha256((folder/sky_name).read_bytes()).hexdigest(),
              'environment_sha256': hashlib.sha256((folder/'daylight.env').read_bytes()).hexdigest()}
    if sky_tint is not None:
        report['sky_tint'] = list(sky_tint)
    (folder/'daylight-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'art/expressway/sources/daylight')
    parser.add_argument('--output', type=Path, default=ROOT/'assets/game/expressway')
    parser.add_argument('--azimuth', type=float)
    parser.add_argument('--match-sun-elevation', action='store_true')
    args = parser.parse_args()
    prepare(args.source.resolve(), args.output.resolve(), azimuth=args.azimuth,
            match_sun_elevation=args.match_sun_elevation)
