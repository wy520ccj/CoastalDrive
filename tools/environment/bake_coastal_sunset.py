"""离线分块烘焙设计38落日云层；运行时不增加体积云绘制步骤。"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    CardMaker,
    Filename,
    FrameBufferProperties,
    Shader,
    Texture,
    loadPrcFileData,
)
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]


def periodic_noise(grid, size):
    """平滑周期值噪声；只用于离线素材，不进入游戏帧。"""
    count=grid.shape[0]
    positions=np.arange(size)*count/size
    indices=np.floor(positions).astype(int)
    fraction=positions-indices
    fraction=fraction*fraction*(3-2*fraction)
    for axis in range(3):
        shape=[1,1,1]
        shape[axis]=size
        weight=fraction.reshape(shape)
        grid=np.take(grid,indices,axis=axis)*(1-weight)+np.take(grid,(indices+1)%count,axis=axis)*weight
    return grid


def write_hdr(path, pixels):
    """标准Radiance RGBE逐像素编码；原生PfmFile复读验证另行执行。"""
    peak=pixels.max(axis=2)
    mantissa,exponent=np.frexp(peak)
    scale=np.divide(mantissa*256,peak,out=np.zeros_like(peak),where=peak>1e-32)
    rgb=np.clip(pixels*scale[:,:,None],0,255).astype(np.uint8)
    power=np.where(peak>1e-32,exponent+128,0).clip(0,255).astype(np.uint8)
    encoded=np.dstack((rgb,power))
    height,width,_=pixels.shape
    with path.open('wb') as stream:
        stream.write(f'#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y {height} +X {width}\n'.encode())
        stream.write(encoded.tobytes())


def bake(output, width, steps):
    output.mkdir(parents=True,exist_ok=False)
    tile=256
    height=width//2
    loadPrcFileData('sky-bake','window-type offscreen\nwin-size 64 64\naudio-library-name null\nsync-video false\nthreading-model\n')
    app=ShowBase()
    try:
        rng=np.random.default_rng(38)
        channels=[periodic_noise(rng.random((n,n,n)),128) for n in (8,16,32,64)]
        noise_bytes=(np.stack(channels,axis=3)*255).astype(np.uint8).tobytes()
        noise=Texture('offline-coastal-cloud-noise')
        noise.setup3dTexture(128,128,128,Texture.TUnsignedByte,Texture.FRgba8)
        noise.setRamImageAs(noise_bytes,'RGBA')
        for setter in (noise.setWrapU,noise.setWrapV,noise.setWrapW):
            setter(Texture.WMRepeat)
        noise.setMinfilter(Texture.FTLinear)
        noise.setMagfilter(Texture.FTLinear)
        props=FrameBufferProperties()
        props.setRgbColor(True)
        props.setFloatColor(True)
        props.setRgbaBits(16,16,16,16)
        buffer=app.win.makeTextureBuffer('coastal-sunset-offline',tile,tile,fbp=props,to_ram=True)
        app.makeCamera2d(buffer)
        card=CardMaker('offline-sky-tile')
        card.setFrame(-1,1,-1,1)
        quad=app.render2d.attachNewNode(card.generate())
        source=ROOT/'art/expressway/sky'
        quad.setShader(Shader.load(Shader.SLGLSL,Filename.fromOsSpecific(str(source/'coastal-sunset-bake.vert')),
                                  Filename.fromOsSpecific(str(source/'coastal-sunset-bake.frag'))))
        azimuth,altitude=map(math.radians,(60,3.5))
        direction=(math.cos(altitude)*math.cos(azimuth),math.cos(altitude)*math.sin(azimuth),math.sin(altitude))
        quad.setShaderInput('cloud_noise',noise)
        quad.setShaderInput('sun_direction',direction)
        quad.setShaderInput('trace_steps',steps)
        pixels=np.zeros((height,width,3),dtype=np.float32)
        texture=buffer.getTexture()
        for y in range(0,height,tile):
            for x in range(0,width,tile):
                quad.setShaderInput('tile_rect',(x/width,y/height,tile/width,tile/height))
                app.graphicsEngine.renderFrame()
                app.graphicsEngine.syncFrame()
                raw=texture.getRamImageAs('RGB')
                dtype={2:np.float16,4:np.float32}[texture.getComponentWidth()]
                values=np.frombuffer(raw,dtype=dtype).reshape(tile,tile,3)
                pixels[y:y+tile,x:x+tile]=values
            print('SKY ROW',y+tile,'/',height,flush=True)
        pixels=pixels[::-1]
        assert np.isfinite(pixels).all() and pixels.max()>1 and pixels.mean()>.01
        path=output/'coastal-sunset.hdr'
        write_hdr(path,pixels)
        exposed=np.maximum(pixels*2**-2.3-.004,0)
        display=(exposed*(6.2*exposed+.5))/(exposed*(6.2*exposed+1.7)+.06)
        Image.fromarray(np.clip(display*255,0,255).astype(np.uint8)).save(output/'preview.png')
        metadata={'file':path.name,'source':'CoastalDrive procedural sunset sample for design38',
                  'authors':{'CoastalDrive':'project-authored offline atmosphere and thin cloud layer'},
                  'license':'Project-authored procedural asset; research source RenderPipeline MIT',
                  'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'noise_sha256':hashlib.sha256(noise_bytes).hexdigest(),
                  'sun_pixel':[round(width*60/360),round(height*(.5-3.5/180))],
                  'width':width,'height':height,'trace_steps':steps,'status':'offline candidate; not runtime acceptance',
                  'reference':'https://github.com/tobspr/RenderPipeline/tree/f858d071d54902e7d00eb0046dd5730eac9e4678/rpplugins/clouds'}
        (output/'source.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    finally:
        app.destroy()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--width',type=int,choices=(2048,4096,8192),default=2048)
    parser.add_argument('--steps',type=int,default=80)
    arguments=parser.parse_args()
    bake(arguments.output.resolve(),arguments.width,arguments.steps)
