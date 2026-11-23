"""同一实际岩岸着色器比较原GLB加载与原生资源，三档LOD的真实像素不放宽。"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, DirectionalLight, Filename, Mat4, Vec3, loadPrcFileData
from simplepbr import Pipeline

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools/environment'))

from local_coastal_landscape import load_rocks

from environment.expressway_materials import daylight_assets


def check(output, baseline):
    output.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('rock_runtime_baseline', baseline)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    loadPrcFileData('rock-runtime-gpu', 'window-type offscreen\nwin-size 640 360\naudio-library-name null\nsync-video false\nthreading-model ')
    app = ShowBase()
    try:
        Pipeline(enable_shadows=True, max_lights=1, use_330=True)
        app.disableMouse()
        app.setBackgroundColor(.1, .12, .14)
        ambient = AmbientLight('ambient')
        ambient.setColor((.15, .15, .15, 1))
        app.render.setLight(app.render.attachNewNode(ambient))
        sun = app.render.attachNewNode(DirectionalLight('sun'))
        sun.node().setColor((3, 3, 3, 1))
        sun.node().setShadowCaster(True, 1024, 1024)
        app.render.setLight(sun)
        app.render.setShaderInput('expressway_sky', daylight_assets()[0])
        app.render.setShaderInput('expressway_sky_tint', (1., 1., 1.))
        app.render.setShaderInput('expressway_sky_inverse', Mat4.identMat())
        parents = [app.render.attachNewNode('original'), app.render.attachNewNode('native')]
        models = [original.load_rocks(parents[0]), load_rocks(parents[1])]
        for parent in parents:
            parent.stash()
        rows = []
        for name in models[0]:
            for family in models:
                for item, node in family.items():
                    node.show() if item == name else node.hide()
            low, high = models[0][name].getTightBounds()
            center, size = (low+high)*.5, max(high-low)
            app.camera.setPos(center+Vec3(size*.7, -size*1.8, size*.9))
            app.camera.lookAt(center)
            app.camLens.setFov(48)
            app.camLens.setNearFar(.1, 1000)
            sun.node().getLens().setFilmSize(size*2, size*2)
            sun.node().getLens().setNearFar(.1, size*8)
            sun.setPos(center+Vec3(-size*2, -size*2, size*3))
            sun.lookAt(center)
            for level in range(3):
                for family in models:
                    family[name].node().forceSwitch(level)
                images = []
                for index in (0, 1, 0):
                    parents[index].unstash()
                    for _ in range(8):
                        app.taskMgr.step()
                    app.graphicsEngine.syncFrame()
                    picture = app.win.getScreenshot()
                    picture.write(Filename.fromOsSpecific(str(output/(name+'-'+str(level)+'-'+str(len(images))+'.png'))))
                    pixels = np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).reshape(360, 640, 3).copy()
                    assert np.count_nonzero(np.any(abs(pixels.astype(np.int16)-pixels[0, 0]) > 4, axis=2)) > 1000
                    images.append(pixels)
                    parents[index].stash()
                difference = abs(images[0].astype(np.int16)-images[1])
                repeat = abs(images[0].astype(np.int16)-images[2])
                rows.append({'model': name, 'lod': level, 'max_rgb8': int(difference.max()),
                             'changed_channels': int(np.count_nonzero(difference)),
                             'repeat_max_rgb8': int(repeat.max())})
        report = {'passed': all(row['max_rgb8'] == 0 for row in rows), 'runs': rows,
                  'scope': '四份实际岩岸/每份三档LOD/同一运行岩岸着色器与光照；原/新/原逐像素比较，不是驾驶帧率、完整道路画面或人工体验Gate。'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        assert report['passed'], report
    finally:
        app.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    arguments = parser.parse_args()
    check(arguments.output.resolve(), arguments.baseline.resolve())
