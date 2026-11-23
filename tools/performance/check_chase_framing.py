"""同一真实完成状态对照追车高度；不移动权威车辆或更改阴影。"""

import argparse
import json
import math
import multiprocessing
import sys
from dataclasses import asdict
from pathlib import Path

from panda3d.core import Filename, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/environment'))

import check_interactive_local_drive
from check_interactive_local_drive import DrivingProbe, check


def capture(app):
    state = app.framing_state
    original = app.camera.getTransform()
    position = Vec3(*state.player.position)
    heading = app.chase_camera.heading
    road = app.session.simulation.road
    pose = road.sample_lateral(road.locate(state.player)[0], 0.)
    direction = Vec3(-math.sin(math.radians(heading)), math.cos(math.radians(heading)),
                     math.tan(math.radians(pose.grade))*math.cos(math.radians(heading-pose.heading)))
    look = position+direction*6+Vec3(0, 0, .7)
    images = []
    for label, drop in (('original-4p2', -1.), ('candidate-3p2', 0.), ('candidate-2p7', .5)):
        app.camera.setPos(original.getPos()-Vec3(0, 0, drop))
        app.camera.lookAt(look)
        for _ in range(12):
            yield
        app.graphicsEngine.syncFrame()
        name = label+'.png'
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(app.probe_output/name)))
        images.append({'file': name, 'position': list(app.camera.getPos()), 'look_at': list(look)})
    assert asdict(app.session.current) == app.framing_authority
    app.camera.setTransform(original)
    report = {'vehicle': app.vehicle_model_id, 'display_state': asdict(state), 'images': images,
              'scope': '正常120Hz权威行驶120m后暂停；三镜位同一显示状态/原车型/画质/阴影，非性能样本或设计图',
              'authority_unchanged': True}
    (app.probe_output/'framing.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


class FramingProbe(DrivingProbe):
    inspection = None

    def apply_scene(self, state, camera_dt):
        super().apply_scene(state, camera_dt)
        self.framing_state = state

    def probe_frame(self, task):
        if self.inspection is not None:
            try:
                next(self.inspection)
            except StopIteration:
                self.userExit()
                return task.done
            return task.cont
        if self.probe_driver and self.session.simulation.road.locate(self.session.current.player)[0] >= 120:
            self.session.pause()
            self.framing_authority = asdict(self.session.current)
            self.taskMgr.remove('drive-update')
            self.inspection = capture(self)
            return task.cont
        return super().probe_frame(task)


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check_interactive_local_drive.DrivingProbe = FramingProbe
    try:
        check(args.output.resolve(), False, False)
    except RuntimeError:
        if not (args.output/'framing.json').is_file():
            raise
