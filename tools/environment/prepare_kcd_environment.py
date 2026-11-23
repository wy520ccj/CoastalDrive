"""从本机KCD2原件准备地表完整贴图、原始HDR探针及太阳参数；输出不进入发行资产。"""

import argparse
import ctypes
import hashlib
import io
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from kcd_local_assets import INSTALL
from panda3d.core import Filename, LColor, PfmFile, Texture
from PIL import Image
from simplepbr._ibl_funcs_cpu import get_sh_coeffs_from_cube_map
from simplepbr.envmap import EnvMap

PROBE = 'Textures/cubemaps/kutnohorsko/krat_pasture_probe_1/13_00_cm.dds'


def decoder(folder):
    from setuptools._distutils._msvccompiler import _get_vc_env

    library = folder / 'bc6h.dll'
    if not library.is_file():
        env = os.environ.copy()
        env.update(_get_vc_env('x86_amd64'))
        compiler = shutil.which('cl.exe', path=env['path'])
        if compiler is None:
            raise FileNotFoundError('转换BC6H需要本机MSVC C编译器')
        source = ROOT / 'tools/environment/decode_bc6h.c'
        subprocess.run([compiler, '/nologo', '/utf-8', '/O2', '/LD', str(source),
                        '/link', '/OUT:' + str(library)], cwd=folder, env=env, check=True,
                       stdout=subprocess.DEVNULL)
    library = ctypes.CDLL(str(library))
    function = library.decode_bc6h_hdr
    function.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    function.restype = ctypes.c_int
    return library, function


def decode_hdr(function, payload, size):
    result = np.empty((size, size, 3), dtype=np.float32)
    source = ctypes.create_string_buffer(payload)
    if function(source, len(payload), result.ctypes.data, size, size) != 0:
        raise ValueError('BC6H数据长度与尺寸不符')
    if not np.isfinite(result).all():
        raise ValueError('HDR探针存在非有限颜色')
    return result


def prepare_probe(folder, function):
    with ZipFile(INSTALL / 'IPL_Textures-part0.pak') as base, ZipFile(INSTALL / 'Textures-part0.pak') as stream:
        raw = base.read(PROBE)
        assert struct.unpack_from('<I', raw, 128)[0] == 95
        payloads = {size: stream.read(PROBE + '.' + str(suffix))
                    for size, suffix in ((128, 3), (64, 2), (32, 1))}
    cube = Texture('KCD2-original-pasture-13')
    cube.setupCubeMap(128, Texture.TFloat, Texture.FRgb16)
    levels = []
    for size in (128, 64, 32, 16, 8, 4):
        level = []
        for face in range(6):
            if size >= 32:
                length = size * size
                payload = payloads[size][face * length:(face + 1) * length]
            else:
                offset = 148 + face * 336 + {16: 0, 8: 256, 4: 320}[size]
                payload = raw[offset:offset + size * size]
            level.append(decode_hdr(function, payload, size))
        levels.append(np.stack(level))
    # 补足GPU完整mip链；原件0–5级保留，新增的2/1像素级仅作常规平均。
    for _ in range(2):
        previous = levels[-1]
        size = previous.shape[1] // 2
        levels.append(previous.reshape(6, size, 2, size, 2, 3).mean(axis=(2, 4)))
    for mip, faces in enumerate(levels):
        size = faces.shape[1]
        for face in range(6):
            pixels = PfmFile()
            pixels.clear(size, size, 3)
            for y in range(size):
                for x in range(size):
                    pixels.setPoint3(x, y, tuple(float(v) for v in faces[face, y, x]))
            if not cube.load(pixels, face, mip):
                raise OSError('无法建立原始HDR立方纹理')
    environment = EnvMap(cube, skip_prepare=True)
    environment.filtered_env_map = cube
    for index, coefficient in enumerate(get_sh_coeffs_from_cube_map(cube)):
        environment.sh_coefficients[index] = coefficient
    environment.is_prepared.set_result(environment)
    environment.write(Filename.fromOsSpecific(str(folder / 'original-pasture.env')))
    # 原引擎的预滤波链与simplepbr粗糙度约定不同；从同一HDR原件生成匹配本引擎的GGX链。
    pbr_environment = EnvMap(cube, prefiltered_size=64, prefiltered_samples=32, blocking_prepare=True)
    pbr_environment.write(Filename.fromOsSpecific(str(folder / 'original-pasture-pbr.env')))
    # 可见天空由同一原始探针展开，避免另一套天空颜色混入光照对照。
    peeker, color = cube.peek(), LColor()
    sky = PfmFile()
    sky.clear(1024, 512, 3)
    for y in range(512):
        latitude = (.5 - (y + .5) / 512) * math.pi
        for x in range(1024):
            longitude = ((x + .5) / 1024 - .5) * math.tau
            peeker.lookup(color, math.cos(latitude) * math.cos(longitude),
                          math.cos(latitude) * math.sin(longitude), math.sin(latitude))
            sky.setPoint3(x, y, color.xyz)
    if not sky.write(Filename.fromOsSpecific(str(folder / 'original-sky.pfm'))):
        raise OSError('无法保存原始探针天空')
    return {'source': PROBE, 'source_mip_sizes': [128, 64, 32, 16, 8, 4],
            'added_mips': [2, 1], 'hdr_min': float(levels[0].min()), 'hdr_max': float(levels[0].max())}


def texture_image(package, stem, suffix, size, *, alpha=False):
    raw = package.read(stem + ('.a' if alpha else ''))
    header = bytearray((b'DDS ' + raw)[:148] if alpha else raw[:148])
    width, height = (size, size) if isinstance(size, int) else size
    struct.pack_into('<II', header, 12, height, width)
    struct.pack_into('<I', header, 28, 1)
    format_id = struct.unpack_from('<I', header, 128)[0]
    struct.pack_into('<I', header, 128, {72: 71, 78: 77}.get(format_id, format_id))
    payload = package.read(stem + suffix + ('a' if alpha else ''))
    return Image.open(io.BytesIO(header + payload)).convert('RGB')


def prepare_surface(package, folder, name, stem, size, suffix, height_suffix):
    diffuse = texture_image(package, stem + '_diff.dds', suffix, size)
    diffuse.save(folder / (name + '-albedo.png'))
    normal = np.array(texture_image(package, stem + '_ddna.dds', suffix, size), dtype=np.float32) / 255
    xy = normal[:, :, :2] * 2 - 1
    z = np.sqrt(np.maximum(0, 1 - np.sum(xy * xy, axis=2)))
    normal[:, :, 2] = z * .5 + .5
    Image.fromarray(np.uint8(np.clip(normal, 0, 1) * 255)).save(folder / (name + '-normal.png'))
    gloss = texture_image(package, stem + '_ddna.dds', suffix, size, alpha=True).getchannel('R')
    gloss.save(folder / (name + '-gloss.png'))
    height_size = 512
    height = texture_image(package, stem + '_displ.dds', height_suffix, height_size)
    height.save(folder / (name + '-height.png'))
    return {'name': name, 'source': stem, 'diffuse_size': size, 'height_size': height_size,
            'normal_encoding': 'BC5 signed XY; positive Z reconstructed',
            'gloss_encoding': 'original separate BC4 alpha; runtime roughness=1-gloss'}


def prepare(folder):
    folder.mkdir(parents=True, exist_ok=True)
    _library, function = decoder(folder)
    probe = prepare_probe(folder, function)
    with ZipFile(INSTALL / 'IPL_Textures-part1.pak') as package:
        surfaces = [prepare_surface(package, folder, 'pasture', 'Textures/terrain/grass/grass_pasture_a_2x2',
                                    1024, '.5', '.4'),
                    prepare_surface(package, folder, 'forest', 'Textures/terrain/forest/forest_ground_beech_oak_4x4',
                                    1024, '.5', '.4')]
    with ZipFile(INSTALL / 'Levels/trosecko/level.pak') as package:
        mission = package.read('mission_mission0.xml')
    root = ET.fromstring(mission)
    light = root.find('Environment/Lighting').attrib
    variables = {v.attrib['Name']: v.attrib for v in root.find('TimeOfDay').findall('Variable')}
    report = {'scope': '本机KCD2原件的本地资源试用，不属于可再分发游戏资源', 'probe': probe,
              'surfaces': surfaces, 'lighting': light, 'time': root.find('TimeOfDay').attrib,
              'sun_color': variables['Sun color']['Color'], 'sun_lux': variables['Sun intensity']['Value'],
              'sun_specular': variables['Sun specular multiplier']['Value'],
              'mission_sha256': hashlib.sha256(mission).hexdigest()}
    (folder / 'original-environment.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('KCD ORIGINAL ENVIRONMENT READY', folder, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'logs/local-kcd-original-environment')
    prepare(parser.parse_args().output.resolve())
