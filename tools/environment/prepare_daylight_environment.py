"""从同一实拍晴空离线生成天空和环境照明，运行时不执行过滤。"""

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


def main():
    original = json.loads((ROOT/'art/expressway/sources/daylight/source.json').read_text())
    source = ROOT/'art/expressway/sources/daylight'/original['file']
    image = PfmFile()
    if not image.read(Filename.fromOsSpecific(str(source))):
        raise OSError(f'无法读取晴空HDRI：{source}')
    width, height = image.getXSize(), image.getYSize()
    # 仅绕竖轴配准太阳方位，保持实拍天空地平线水平。
    light = max((sum(image.getPoint3(x, y)), x, y)
                 for y in range(0, height//2, 4) for x in range(0, width, 4))
    _, sx, sy = light
    target_heading = math.degrees(math.atan2(-75, -55))
    heading = (target_heading-sx/width*360+180)%360-180
    # 太阳直射由现有DirectionalLight负责，避免低分辨率环境图把太阳热点重复算入漫反射。
    cube = equirectangular_cube(image, 128, longitude_offset=-.5-heading/360, radiance_limit=4.)
    environment = EnvMap(cube, prefiltered_size=128, prefiltered_samples=64, blocking_prepare=True)
    folder = ROOT/'assets/game/expressway'
    environment.write(Filename.fromOsSpecific(str(folder/'daylight.env')))
    shutil.copyfile(source, folder/'daylight-sky.hdr')
    report = {'source': original, 'sky_heading_degrees': heading,
              'source_sun_elevation_degrees': 90-sy/height*180,
              'directional_sun': list(Vec3(-55, -75, 125).normalized()),
              'cube_size': 128, 'prefiltered_samples': 64, 'indirect_radiance_limit': 4.,
              'sky_sha256': hashlib.sha256((folder/'daylight-sky.hdr').read_bytes()).hexdigest(),
              'environment_sha256': hashlib.sha256((folder/'daylight.env').read_bytes()).hexdigest()}
    (folder/'daylight-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
