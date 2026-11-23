"""设计38海岸：离线过滤原始8K落日天空，并烘焙周期风浪法线。"""

import json
import sys
from pathlib import Path

import numpy as np
from panda3d.core import Filename, PfmFile, Texture

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/environment'))
from prepare_daylight_environment import prepare


def build():
    folder = ROOT/'art/expressway/sources/coastal-sunset38-citrus'
    output = ROOT/'assets/game/environment/coastal-sunset'
    prepare(folder,output,azimuth=60,match_sun_elevation=True,sky_tint=(1.08,1.,.94))
    build_waves(output)
    path = output/'daylight-manifest.json'
    metadata = json.loads(path.read_text(encoding='utf-8'))
    metadata.update(art_direction='design38',exposure_ev=-2.3,sky_diffuse_scale=.65,
                    career_sky_diffuse_scale=2.6,
                    direct_sun_color=[1.,.67,.37],direct_sun_scale=14.,
                    color_basis='8K original linear HDR; scene exposure in EV')
    path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def build_waves(output):
    """周期64米的多尺度风浪法线；预计算后运行时只取两次纹理。"""
    size = 512
    y,x = np.mgrid[:size,:size]*(64/size)
    slopes = np.zeros((size,size,2))
    rng = np.random.default_rng(38)
    for octave in range(6):
        for _ in range(8):
            angle = rng.uniform(-np.pi,np.pi)
            frequency = rng.uniform(2**(octave+1),2**(octave+2))
            k = np.rint(frequency*np.array([np.cos(angle),np.sin(angle)]))
            phase = (k[0]*x+k[1]*y)*2*np.pi/64+rng.uniform(0,2*np.pi)
            slope = np.cos(phase)*(.042/(1+octave*.16))
            slopes += slope[:,:,None]*(k/np.linalg.norm(k))
    normals = np.dstack((-slopes,np.ones((size,size))))
    normals /= np.linalg.norm(normals,axis=2)[:,:,None]
    pixels = PfmFile()
    pixels.clear(size,size,3)
    for row in range(size):
        for col in range(size):
            pixels.setPoint3(col,row,tuple(normals[row,col]*.5+.5))
    texture = Texture('coastal-wind-wave-normals')
    assert texture.load(pixels)
    texture.setFormat(Texture.FRgb16)
    texture.generateRamMipmapImages()
    assert texture.write(Filename.fromOsSpecific(str(output/'wave-normals.txo.pz')))


if __name__ == '__main__':
    build()
