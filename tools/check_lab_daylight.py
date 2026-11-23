"""真实实验台独立/共享窗口及回放视图采集；不代替人工或驾驶性能验收。"""

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from lab_application import VehicleLab
from lab_experiment import LabOptions
from lab_records import model_fingerprint


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    before = model_fingerprint()
    images = []

    def capture(lab, name):
        for _ in range(8):
            lab.engine.taskMgr.step()
        lab.engine.graphicsEngine.syncFrame()
        assert lab.engine.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        images.append(name+'.png')

    lab = VehicleLab(offscreen=True, output=output/'records', scheme_root=output/'schemes', render_size=size)
    try:
        capture(lab, 'standalone-ready')
        lab.set_options(LabOptions(speed_kph=30, duration=.5))
        lab.start_experiment()
        for _ in range(3000):
            lab.engine.taskMgr.step()
            if lab.run_state.done:
                break
        assert lab.run_state.done and lab.record is not None
        trial = {'summary': lab.run_state.summary(), 'first': asdict(lab.run_state.snapshots[0]),
                 'last': asdict(lab.run_state.snapshots[-1])}
        for mode, name in ((0, 'chase'), (1, 'top'), (2, 'side')):
            lab.scene.camera_mode = mode
            lab.show_sample(30)
            capture(lab, 'trial-'+name)
    finally:
        lab.close_game()

    app = CoastalDrive(smoke=True, output=output/'game', render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        window, pipeline = app.win, app.pipeline
        app.open_vehicle_lab()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == 'lab' and app._workspace_steps is None
        assert app.lab.engine is app and app.lab.pipeline is pipeline and app.win is window
        capture(app.lab, 'shared-ready')
        lab_root = app.lab.scene.root
        shadow = app.lab.scene.light.node()
        app.lab.back_to_game()
        for _ in range(30):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app.workspace == 'game' and app.lab is None and app.win is window and app.pipeline is pipeline
        assert lab_root.isEmpty() and not shadow.isShadowCaster()
        for _ in range(8):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/'returned-game.png')))
        images.append('returned-game.png')
        after = model_fingerprint()
        assert before == after
        resource = ROOT/'assets/game/environment/daylight/daylight.env'
        metadata = json.loads(resource.with_name('daylight-manifest.json').read_text(encoding='utf-8'))
        assert hashlib.sha256(resource.read_bytes()).hexdigest() == metadata['environment_sha256']
        report = {'passed': True, 'size': size, 'images': images, 'trial': trial,
                  'model_fingerprints_equal': True, 'model_fingerprints': before,
                  'same_window_pipeline': True, 'lab_root_and_shadow_released': True,
                  'daylight_env_matches_accepted_source': True,
                  'scope': '真实离屏独立实验台/默认工况60步及三视角/主窗口进入与返回；不是正常驾驶FPS或人工视觉验收。'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print('LAB DAYLIGHT PASSED', size, len(images), flush=True)
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    arguments = parser.parse_args()
    check(arguments.output.resolve(), tuple(arguments.size))
