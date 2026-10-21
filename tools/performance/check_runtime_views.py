"""冻结当前真实场景检查远景雾化，不把静态渲染当作性能样本。"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename, Vec3

from application import CoastalDrive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-haze', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    if args.baseline_haze:
        import environment.expressway_materials as materials
        original_path = materials.shader_path
        materials.shader_path = lambda name: (Filename.fromOsSpecific(str(args.baseline_haze.resolve()))
                                               if name == 'distance-haze.glsl' else original_path(name))
    app = CoastalDrive(smoke=True, track='endless', road_shape='hills', output=output)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    state = app.session.current
    try:
        app.scene.apply(state)
        app.scene.update_lighting(Vec3(*state.player.position))
        app.hud.update(state, app.session.race.snapshot, app.session.highway.snapshot,
                       track='endless', countdown='', notice='')
        origin = Vec3(*state.player.position)
        for name, position, target in (
            ('rear', (0., -12., 5.), (0., 100., 1.)),
            ('bay', (-5., 0., 10.), (650., 280., 80.)),
            ('mountain', (5., 0., 10.), (-650., 500., 100.)),
        ):
            app.camera.setPos(origin + Vec3(*position))
            app.camera.lookAt(origin + Vec3(*target))
            for _ in range(5):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
            assert app.session.current == state
        (output/'summary.json').write_text(json.dumps({'passed': True, 'new_physics_ticks': 0,
            'baseline_haze': str(args.baseline_haze), 'views': ['rear', 'bay', 'mountain'],
            'scope': '真实静态场景/固定相机；不替代实际驾驶或帧耗时验收。'}, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        app.close_game()


if __name__ == '__main__':
    main()
