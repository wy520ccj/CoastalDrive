"""同一场景、同一完整车型比较原合批与等值材质共享后的真实GPU像素。"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from direct.showbase.ShowBase import ShowBase
from panda3d.core import AmbientLight, DirectionalLight, Filename, Vec3, Vec4, loadPrcFileData
from simplepbr import Pipeline

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))

from scene import make_quad
from skins import apply_skin, vehicle_definition
from vehicle_visual import batch_driving_geometry, load_vehicle


def legacy(root, wheels):
    for part in (root.getChild(0), *wheels):
        children = tuple(part.getChildren())
        geometry = part.attachNewNode('driving-geometry')
        for child in children:
            child.reparentTo(geometry)
        geometry.clearModelNodes()
        geometry.flattenStrong()


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    loadPrcFileData('driving-materials', 'window-type offscreen\nwin-size 960 600\naudio-library-name null\nsync-video false\nthreading-model ')
    app = ShowBase()
    try:
        Pipeline(enable_shadows=True, max_lights=1, use_330=True)
        ambient = AmbientLight('ambient')
        ambient.setColor((.15, .15, .15, 1))
        app.render.setLight(app.render.attachNewNode(ambient))
        sun = app.render.attachNewNode(DirectionalLight('sun'))
        sun.node().setColor((3, 3, 3, 1))
        sun.node().setShadowCaster(True, 1024, 1024)
        sun.node().getLens().setFilmSize(20, 20)
        sun.node().getLens().setNearFar(1, 60)
        sun.setPos(-10, -15, 25)
        sun.lookAt(0, 0, 0)
        app.render.setLight(sun)
        make_quad('floor', Vec3(0), 18, 18, Vec4(.3, .3, .3, 1), 0).reparentTo(app.render)
        results = []
        for model in ('coastal-gt', 'sports', 'subaru-wrx-sti'):
            parents, counts = [], []
            for batch in (legacy, batch_driving_geometry):
                parent = app.render.attachNewNode('variant')
                body, wheels = load_vehicle(parent, vehicle_definition(model))
                apply_skin(body.getChild(0), 0)
                batch(body, wheels)
                counts.append(sum(part.node().getNumGeoms() for part in parent.findAllMatches('**/+GeomNode')))
                parents.append(parent)
                parent.stash()
            for angle, position in (('rear', (-6, -8, 3)), ('front', (6, 8, 2))):
                app.camera.setPos(*position)
                app.camera.lookAt(0, 0, .5)
                images = []
                for index in (0, 1, 0):
                    parents[index].unstash()
                    for _ in range(12):
                        app.taskMgr.step()
                    app.graphicsEngine.syncFrame()
                    picture = app.win.getScreenshot()
                    picture.write(Filename.fromOsSpecific(str(output/(model+'-'+angle+'-'+str(len(images))+'.png'))))
                    images.append(np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy())
                    parents[index].stash()
                delta = abs(images[0].astype(np.int16)-images[1])
                repeat = abs(images[0].astype(np.int16)-images[2])
                results.append({'model': model, 'view': angle, 'geoms_before_after': counts,
                                'max_rgb8': int(delta.max()), 'changed_channels': int(np.count_nonzero(delta)),
                                'repeat_max_rgb8': int(repeat.max()), 'repeat_changed_channels': int(np.count_nonzero(repeat))})
            for parent in parents:
                parent.removeNode()
        report = {'scope': '三个原完整车型、各前后两镜位，原材质数值与完整几何；默认状态排序像素差不放宽',
                  'results': results, 'passed': all(row['max_rgb8'] == 0 for row in results)}
        (output/'materials.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        assert report['passed'], report
    finally:
        app.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check(args.output.resolve())
