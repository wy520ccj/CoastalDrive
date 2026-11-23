"""正常随车比较相机输入共享存储；诊断包装不写入产品或第三方依赖。"""

import argparse
import hashlib
import json
import multiprocessing
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/environment'))

import check_interactive_local_drive
from check_interactive_local_drive import DrivingProbe, check
from panda3d.core import WindowProperties
from simplepbr import Pipeline

import application
from rendering import ScenePipeline


def run(output, mutable, hold=False, end_distance=450):
    original = application.ScenePipeline
    original_probe = check_interactive_local_drive.DrivingProbe

    class CameraStateProbe(DrivingProbe):
        def __init__(self, *args, **kwargs):
            self.preview_held = False
            super().__init__(*args, **kwargs)
            if hold:
                properties = WindowProperties()
                properties.setTitle('CoastalDrive · 较低追车镜位试跑 · 按Esc继续驾驶')
                self.win.requestProperties(properties)

        def probe_finish(self):
            super().probe_finish()
            path = self.probe_output/'summary.json'
            report = json.loads(path.read_text(encoding='utf-8'))
            report.update(camera_position_buffers=len(self.pipeline._camera_positions) if mutable else 0,
                          vehicle_model=self.vehicle_model_id, road_shape=self.session.road_shape,
                          vehicle_config_sha256=hashlib.sha256(json.dumps(
                              asdict(self.session.vehicle_config), sort_keys=True).encode()).hexdigest())
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

        def userExit(self):
            if hold and not self.preview_held and (self.probe_output/'summary.json').exists():
                self.preview_held = True
                self.taskMgr.remove('probe-frame')
                self.session.set_controller(self.session.keyboard)
                self.session.pause()
                self.refresh_panel()
                return
            super().userExit()

    application.ScenePipeline = ScenePipeline if mutable else Pipeline
    check_interactive_local_drive.DrivingProbe = CameraStateProbe
    try:
        check(output, False, False, trace_state_cache=True, end_distance=end_distance)
    finally:
        application.ScenePipeline = original
        check_interactive_local_drive.DrivingProbe = original_probe


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mutable', action='store_true')
    parser.add_argument('--hold', action='store_true', help='试跑完成后暂停并保留窗口，Esc继续手动驾驶')
    parser.add_argument('--end-distance', type=int, choices=(270, 450, 900), default=450)
    args = parser.parse_args()
    run(args.output.resolve(), args.mutable, args.hold, args.end_distance)
