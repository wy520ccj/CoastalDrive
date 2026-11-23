"""真实场景的缓存回收分项对照；离屏冻结车辆，只重放相机，不作驾驶性能Gate。"""

import argparse
import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
from panda3d.core import ConfigVariableDouble, Filename, RenderState, TransformState, Vec3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools/environment'))

from check_driving_composition import ViewDriver
from local_kcd_drive import LocalVegetation

from application import CoastalDrive
from career import EVENT_BY_ID
from session import Phase
from vehicle_workspace import WorkspaceVehicle


class CollectionProbe(CoastalDrive):
    def __init__(self, *args, **kwargs):
        self.collection_samples = None
        super().__init__(*args, **kwargs)

    def _ShowBase__garbageCollectStates(self, task):
        start, cpu = time.perf_counter(), time.thread_time()
        result = super()._ShowBase__garbageCollectStates(task)
        if self.collection_samples is not None:
            self.collection_samples.append(((time.perf_counter()-start)*1000,
                                            (time.thread_time()-cpu)*1000))
        return result


def check(output, rates=(1., .1, 1.), frames=360, distance=120, driving_rate=None):
    output.mkdir(parents=True, exist_ok=False)
    vehicle = WorkspaceVehicle.load()
    profile = LocalVegetation(ROOT/'logs/local-kcd-drive/assets', ROOT/'logs/local-kcd-original-environment')
    profile.install()
    app = None
    setting = ConfigVariableDouble('garbage-collect-states-rate')
    original_rate = setting.getValue()
    rows = []
    try:
        app = CollectionProbe(smoke=True, output=output, render_size=(640, 360),
                              threading_model='/Draw', workspace_vehicle=vehicle)
        application_rate = setting.getValue()
        if driving_rate is not None:
            setting.setValue(driving_rate)
        actual_driving_rate = setting.getValue()
        app.taskMgr.remove('finish-smoke')
        app.taskMgr.remove('drive-update')
        app.open_career()
        app.career_progress.records = {key: {'stars': 3, 'seconds': 20.} for key in EVENT_BY_ID}
        app.career_action('start', 'ridge-run')
        while app.session.phase == Phase.COUNTDOWN:
            app.session.tick()
        app.session.set_controller(ViewDriver(app.session))
        driving_counts = []
        for tick in range(12000):
            app.session.tick()
            state = app.session.current
            progress = app.session.simulation.road.locate(state.player)[0]
            if tick % 8 == 0:
                app.apply_scene(state, 8/120)
                app.refresh_panel()
                app.hud.resize(app.getAspectRatio())
                app.hud.update(state, app.session.race.snapshot, app.session.highway.snapshot,
                               track='endless', countdown='', notice='', driving_mode=app.session.driving_mode)
                app.taskMgr.step()
            if tick % 120 == 0:
                driving_counts.append({'tick': state.tick, 'distance_m': progress,
                                       'render_states': RenderState.getNumStates()})
            if progress >= distance:
                break
        assert progress >= distance
        # 比较前补齐本轮真实流送窗口；这次离屏诊断不拿补齐成本当驾驶帧时。
        app.scene.sync_segments()
        # 离屏会话没有独立推进线程，drive-update也已移除；不再tick即可冻结。
        # 保持DRIVING界面，调用pause/刷新会将实际画面切回车库，失去驾驶场景覆盖。
        frozen = asdict(app.session.current)
        start_camera = Vec3(app.camera.getPos())
        assert app.session.phase == Phase.DRIVING and app.main_menu.root.isHidden()
        for _ in range(12):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/'driving-scene.png')))
        for number, rate in enumerate(rates):
            setting.setValue(rate)
            app.collection_samples = None
            for _ in range(60):
                app.taskMgr.step()
            app.collection_samples = []
            counts = []
            started = time.perf_counter()
            for frame in range(frames):
                # 各档重放同一镜头轨迹，保持原世界、车辆和输入；仍使用正常Panda任务/Draw。
                app.camera.setPos(start_camera+Vec3(math.sin(frame*.03)*5, math.cos(frame*.03)*3, 0))
                app.taskMgr.step()
                if frame % 30 == 0:
                    counts.append({'frame': frame, 'render_states': RenderState.getNumStates(),
                                   'transform_states': TransformState.getNumStates()})
            samples = np.array(app.collection_samples)
            row = {'rate': rate, 'frames': len(samples), 'wall_s': time.perf_counter()-started,
                   'gc_wall_ms': {'mean': float(samples[:, 0].mean()),
                                  'p95': float(np.percentile(samples[:, 0], 95)),
                                  'max': float(samples[:, 0].max())},
                   'gc_thread_cpu_total_ms': float(samples[:, 1].sum()), 'state_counts': counts}
            rows.append(row)
            print('COLLECTION', rate, row['gc_wall_ms'], counts[-1], flush=True)
            app.collection_samples = None
            app.camera.setPos(start_camera)
            for _ in range(45):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(str(number)+'-rate-'+str(rate)+'.png'))))
            assert asdict(app.session.current) == frozen
        report = {'original_rate': original_rate, 'application_initial_rate': application_rate,
                  'actual_driving_rate': actual_driving_rate,
                  'runs': rows, 'authority_unchanged': True, 'distance_m': progress,
                  'driving_state_counts': driving_counts,
                  'completed_tick': app.session.current.tick, 'collisions': app.session.current.collisions,
                  'scope': '原GT/真实山脊到目标里程后冻结，离屏640x360、Draw；只支持缓存回收CPU与样本状态数量结论，不是前台帧率、人工驾驶或全步性能Gate。'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    finally:
        setting.setValue(original_rate)
        if app is not None:
            app.close_game()
        profile.restore()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rates', type=float, nargs='+', default=(1., .1, 1.))
    parser.add_argument('--frames', type=int, choices=(180, 360), default=360)
    parser.add_argument('--distance', type=int, choices=(120, 450, 900), default=120)
    parser.add_argument('--driving-rate', type=float, help='只用于诊断的连续推进阶段回收比例')
    args = parser.parse_args()
    if any(not 0 < rate <= 1 for rate in args.rates):
        parser.error('回收比例须在(0,1]内')
    if args.driving_rate is not None and not 0 < args.driving_rate <= 1:
        parser.error('推进阶段回收比例须在(0,1]内')
    check(args.output.resolve(), args.rates, args.frames, args.distance, args.driving_rate)
