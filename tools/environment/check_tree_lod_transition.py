"""实际原树与GPU帧验证LOD过渡；固定正交镜位的技术检查，不代替随车验收。"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from panda3d.core import ClockObject, Filename, OrthographicLens, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from local_kcd_drive import LocalVegetation

from application import CoastalDrive
from race import GameMode


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output / 'user')
    profile = LocalVegetation(output / 'assets', ROOT / 'logs/local-kcd-original-environment')
    profile.install()
    app = None
    try:
        app = CoastalDrive(smoke=True, output=output, render_size=(640, 480), threading_model='', sync_video=False)
        app.taskMgr.remove('finish-smoke')
        app.taskMgr.remove('drive-update')
        app.taskMgr.remove('render-frame-pacing')
        app.start_game(mode=GameMode.FREE_DRIVE, track='endless')
        app.aspect2d.hide()
        for child in tuple(app.scene.render.getChildren()):
            child.hide()
        tree = app.scene.expressway_kit['local-kcd-trees'][0].copyTo(app.scene.render)
        tree.show()
        center = float(tree.getTag('source-height')) * .5
        lens = OrthographicLens()
        lens.setFilmSize(26, 19.5)
        lens.setNearFar(1, 300)
        app.cam.node().setLens(lens)
        app.setBackgroundColor(.11, .13, .15)
        app.scene.update_lighting(Vec3(0, 0, 0))
        clock = ClockObject.getGlobalClock()
        clock.setMode(ClockObject.MNonRealTime)
        clock.setDt(1 / 60)
        result = {}

        def capture():
            app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            return app.win.getScreenshot()

        for label, fade_time in (('hard', 0.), ('fade', .45)):
            tree.node().setFadeTime(fade_time)
            app.camera.setPos(0, -48, center)
            app.camera.lookAt(0, 0, center)
            for _ in range(36):
                capture()
            previous = np.frombuffer(capture().getRamImageAs('RGB'), dtype=np.uint8).copy()
            app.camera.setPos(0, -42, center)
            app.camera.lookAt(0, 0, center)
            differences = []
            for frame in range(36):
                picture = capture()
                current = np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy()
                differences.append(float(np.abs(current.astype(float) - previous).mean()))
                previous = current
                if frame in (0, 6, 13, 20, 29, 35):
                    picture.write(Filename.fromOsSpecific(str(output / f'{label}-{frame:02}.png')))
            result[label] = {'frame_differences_rgb8': differences, 'largest_change': max(differences)}
        report = {'scope': '同一真实原树/正交镜位，48→42m跨45m阈值；60Hz仅技术取样时钟，无新驾驶步',
                  'variants': result}
        (output / 'transition.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        assert result['hard']['largest_change'] > .1
        assert result['fade']['largest_change'] < result['hard']['largest_change'] * .6, report
        assert sum(d > .01 for d in result['fade']['frame_differences_rgb8']) > 8, report
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
