"""同一原树逐档渲染，核对坡度改走纹理矩阵后树根形状和二维UV保持。"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from panda3d.core import Filename, OrthographicLens, Shader, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from local_kcd_drive import LocalVegetation, set_root_slope

from application import CoastalDrive
from race import GameMode


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output / 'user')
    profile = LocalVegetation(ROOT / 'logs/local-kcd-drive/assets', ROOT / 'logs/local-kcd-original-environment')
    profile.install()
    app = None
    try:
        app = CoastalDrive(smoke=True, output=output, render_size=(640, 480), threading_model='', sync_video=False)
        for name in ('finish-smoke', 'drive-update', 'render-frame-pacing'):
            app.taskMgr.remove(name)
        app.start_game(mode=GameMode.FREE_DRIVE, track='endless')
        app.aspect2d.hide()
        for child in tuple(app.scene.render.getChildren()):
            child.hide()
        lens = OrthographicLens()
        lens.setFilmSize(8, 6)
        lens.setNearFar(1, 300)
        app.cam.node().setLens(lens)
        app.camera.setPos(0, -25, 2)
        app.camera.lookAt(0, 0, 1)
        app.scene.update_lighting(Vec3(0, 0, 0))
        rows = []
        for number, template in enumerate(app.scene.expressway_kit['local-kcd-trees']):
            tree = template.copyTo(app.scene.render)
            tree.show()
            tree.node().setFadeTime(0.)
            current = tree.getChild(0).getShader()
            vertex = current.getText(Shader.STVertex).replace(
                'vec2 root_slope = p3d_TextureMatrix[2].xy;', '')
            vertex = vertex.replace('uniform float root_anchor;', 'uniform float root_anchor;\nuniform vec2 root_slope;')
            previous = Shader.make(Shader.SLGLSL, vertex, current.getText(Shader.STFragment))
            for level in range(3):
                tree.node().forceSwitch(level)
                for slope in ((.35, -.2), (-.4, .25)):
                    images = []
                    for label in ('previous', 'current'):
                        if label == 'previous':
                            for stage in tree.findAllTextureStages():
                                tree.clearTexTransform(stage)
                            tree.setShader(previous, 4)
                            tree.setShaderInput('root_slope', slope)
                        else:
                            tree.clearShaderInput('root_slope')
                            tree.setShader(current, 4)
                            set_root_slope(tree, slope)
                        for _ in range(4):
                            app.taskMgr.step()
                        app.graphicsEngine.syncFrame()
                        assert not tree.getShader().getErrorFlag()
                        picture = app.win.getScreenshot()
                        images.append(np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy())
                        if number == 0 and level == 0:
                            picture.write(Filename.fromOsSpecific(str(output / f'{label}-{slope[0]}.png')))
                    difference = np.abs(images[0].astype(float) - images[1])
                    row = {'tree': number, 'lod': level, 'slope': slope, 'mean_rgb8': float(difference.mean()),
                           'max_rgb8': float(difference.max()), 'changed_channels': int(np.count_nonzero(difference))}
                    rows.append(row)
                    assert row['max_rgb8'] == 0, row
            tree.removeNode()
        report = {'scope': '五种原树/三档LOD/两组坡度，同一真实GPU图逐通道比较；技术根部镜位，不代替随车美术验收',
                  'cases': rows}
        (output / 'root-transport.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        return report
    finally:
        if app is not None:
            app.close_game()
        profile.restore()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(check(arguments.output.resolve()), ensure_ascii=False))
