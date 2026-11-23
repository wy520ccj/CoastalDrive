"""固定相机检查实际水面绘制状态和时间响应；不作为正常驾驶性能Gate。"""

import argparse
import hashlib
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
from panda3d.core import Filename, Shader, ShaderAttrib, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))

from application import CoastalDrive
from coastal_map import offset_point, point_at


def water_states(scene):
    """读取实际Geom的最终状态，不能只检查Scene持有节点上的输入。"""
    result = []
    for path in scene.render.findAllMatches('**/+GeomNode'):
        for index in range(path.node().getNumGeoms()):
            state = path.getNetState().compose(path.node().getGeomState(index))
            attrib = state.getAttrib(ShaderAttrib)
            if attrib is None or attrib.getShader() is None:
                continue
            if 'wave_normals' in attrib.getShader().getText(Shader.STFragment):
                result.append({'node':str(path),'geom':index,
                               'time':attrib.getShaderInput('sea_time').getVector()[0]})
    return result


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True,output=output)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    captures, pixels = [], []
    try:
        p,q = point_at(0),point_at(26)
        eye = Vec3(*offset_point(p,-1.,3.8))
        app.camera.setPos(eye)
        app.camera.lookAt(Vec3(*offset_point(q,0,2)))
        app.aspect2d.hide()
        app.scene.update_lighting(eye)
        original = app.session.current
        for index,seconds in enumerate((0.,0.,.5,1.,2.)):
            app.scene.apply(replace(original,time=seconds))
            app.scene.sky.setPos(eye)
            app.taskMgr.step()
            for _ in range(8):
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            shot = app.win.getScreenshot()
            filename = f'water-{index:02d}-{seconds:g}s.png'
            assert shot.write(Filename.fromOsSpecific(str(output/filename)))
            rgb = np.frombuffer(shot.getRamImageAs('RGB'),dtype=np.uint8).reshape(
                shot.getYSize(),shot.getXSize(),3)[::-1].copy()
            height,width,_ = rgb.shape
            region = rgb[int(height*.44):int(height*.63),int(width*.92):int(width*.99)]
            pixels.append(region)
            captures.append({'seconds':seconds,'file':filename,
                'effective_water':water_states(app.scene),
                'water_roi_sha256':hashlib.sha256(region.tobytes()).hexdigest()})
        differences = []
        for row in pixels[1:]:
            delta = np.abs(row.astype(np.int16)-pixels[0].astype(np.int16))
            differences.append({'changed_pixels':int(np.count_nonzero(np.any(delta>0,axis=2))),
                                'mean_channel_difference':float(delta.mean()),
                                'maximum_channel_difference':int(delta.max())})
        passed = (captures[0]['water_roi_sha256']==captures[1]['water_roi_sha256']
                  and all(row['mean_channel_difference']>1 for row in differences[1:])
                  and all(len(row['effective_water'])==1 and
                          abs(row['effective_water'][0]['time']-row['seconds'])<1e-6
                          for row in captures))
        report = {'passed':passed,'scope':'固定相机和权威状态，仅替换表现时间；验证实际Geom输入及GPU像素，不冒充真实120Hz驾驶。',
                  'ocean_node':str(app.scene.ocean),'captures':captures,'differences':differences,
                  'roi_normalized':[.92,.44,.99,.63]}
        (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
        return passed
    finally:
        app.close_game()


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    arguments = parser.parse_args()
    raise SystemExit(0 if check(arguments.output.resolve()) else 1)
