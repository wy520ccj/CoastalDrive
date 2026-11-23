"""按实际玩家车辆和大窗口自然撞栏，记录撞前/撞后/恢复及声音分项。"""

import argparse
import gc
import json
import multiprocessing
import os
import sys
import time
from functools import partial
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'src'),str(ROOT/'tools/environment'),str(ROOT/'tools/performance')]

# spawn子进程也在导入会话前选择同一份已保存的原实现。
selection = argparse.ArgumentParser(add_help=False)
selection.add_argument('--baseline-source',type=Path)
selection.add_argument('--source',type=Path)
baseline,_unused = selection.parse_known_args()
if baseline.source is not None:
    # 只隔离执行源码，运行资源仍取主工作区；候选目录不复制或替换玩家资源。
    import_module('paths')
    sys.path.insert(0,str(baseline.source.resolve()))
    # 两个原生模块和机械装配必须来自同一份隔离源；spawn重复执行同一入口。
    for name in ('mechanical_kernels','wheel_contact_kernels','simulation','session_process'):
        import_module(name)
if baseline.baseline_source is not None:
    for name in ('suspension_contacts','vehicle_suspension','session_clock','session'):
        spec = spec_from_file_location(name,baseline.baseline_source/(name+'.py'))
        module = module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)

from check_coastal_stalls import CoastalStallProbe, capture_authority
from check_driving_composition import ViewDriver
from panda3d.core import Filename, WindowProperties

import session_process
from race import GameMode
from session import Phase
from simulation import Control
from vehicle_workspace import WorkspaceVehicle


class ImpactDriver(ViewDriver):
    def __init__(self, impact_distance=20.):
        super().__init__()
        self.impact_distance = impact_distance

    def sample(self, state, dt):
        if state.collisions:
            return Control(brake=1.)
        if self.simulation.road.locate(state.player)[0]>self.impact_distance:
            return Control(steering=1.,throttle=.3)
        return super().sample(state,dt)


class ImpactProbe(CoastalStallProbe):
    def __init__(self, output, vehicle, size, *, region='coastal', impact_distance=20.):
        self.probe_region = region
        self.impact_distance = impact_distance
        self.impact_time = None
        self.impact_wall = None
        self.measured_sound = None
        self.actual_config = None
        super().__init__(output,render_size=size,workspace_vehicle=vehicle)
        self.probe_modes = (GameMode.FREE_DRIVE,)
        title = {'coastal':'滨海','ridge':'山脊','highway':'无限高速'}[region]
        properties = WindowProperties()
        properties.setTitle('CoastalDrive · '+title+'撞后复测')
        self.win.requestProperties(properties)

    def begin_mode(self, task):
        if self._workspace_steps is not None:
            return task.again
        if self.probe_region == 'ridge':
            self.open_career()
            # 仅隔离测试档解锁原赛事，不改原玩家记录或实际车辆/比赛规则。
            self.career_progress.records = {key:{'stars':3,'seconds':20.} for key in ('first-drive','parking')}
            self.career_action('start-stock','ridge-run')
        elif self.probe_region == 'highway':
            self.choose_highway()
            self.start_highway('hills')
        else:
            return super().begin_mode(task)
        return task.done

    def update(self, task):
        if self.soundscape is not None and self.measured_sound is not self.soundscape:
            self.measured_sound = self.soundscape
            self.soundscape.update = partial(self.measure,'audio',self.soundscape.update)
        return super().update(task)

    def check_frame(self, task):
        now = time.perf_counter()
        limit = 120 if self.probe_region == 'coastal' else 180
        if now-self.probe_started>limit:
            raise TimeoutError('自然撞栏窗口超过'+str(limit)+'秒')
        if self.session is None or (not self.probe_driving and self.session.phase != Phase.DRIVING):
            self.probe_last = now
            return task.cont
        if not self.probe_driving:
            self.session.set_controller(ImpactDriver(self.impact_distance),bind_world=True)
            self.probe_driving = True
            self.probe_last = now
            from dataclasses import asdict

            self.actual_config = asdict(self.session.vehicle_config)
            return task.cont
        state = self.session.current
        if state.collisions and self.impact_time is None:
            self.impact_time = state.time
            self.impact_wall = now
            print('NATURAL IMPACT',state.tick,state.time,self.session.phase.value,flush=True)
        props = self.win.getProperties()
        row = {'mode':self.session.mode.value,'phase':self.session.phase.value,
               'wall_frame_ms':(now-self.probe_last)*1000,
               'progress_m':self.session.simulation.road.locate(state.player)[0],
               'tick':state.tick,'simulation_time':state.time,'collisions':state.collisions,
               'foreground':props.getForeground(),'minimized':props.getMinimized(),
               'size':[self.win.getXSize(),self.win.getYSize()],
               'dropped_time':self.session.stepper.dropped_time,'after_capture':False,
               'after_impact_s':None if self.impact_time is None else state.time-self.impact_time,
               'after_impact_wall_s':None if self.impact_wall is None else now-self.impact_wall}
        self.probe_rows.append(row)
        self.probe_last = now
        self.attach_phases()
        recovered = (now-self.impact_wall if self.session.phase == Phase.RESULTS and self.impact_wall is not None
                     else 0. if self.impact_time is None else state.time-self.impact_time)
        if self.impact_time is None or recovered<5:
            return task.cont
        self.attach_phases()
        self.write_report(True)
        self.graphicsEngine.syncFrame()
        assert self.win.getScreenshot().write(Filename.fromOsSpecific(str(self.probe_output/'after-impact.png')))
        self.userExit()
        return task.done

    def write_report(self, completed):
        self.attach_phases()
        (self.probe_output/'frames.json').write_text(json.dumps(self.probe_rows,indent=2)+'\n',encoding='utf-8')
        report = {'completed':completed,'impact_time':self.impact_time,'config':self.actual_config,
                  'region':self.probe_region,'impact_distance':self.impact_distance,
                  'track':self.session.simulation.track,'road_shape':self.session.road_shape,
                  'traffic_models':self.session.simulation.traffic_models,
                  'recovery_basis':'wall_results' if self.session.phase == Phase.RESULTS else 'simulation_driving',
                  'final_phase':self.session.phase.value,
                  'scope':'正常入口、原120Hz/碰撞精度、原音频；从静止加速后转向自然撞栏，无运行中姿态/速度修改。',
                  'baseline_source':str(baseline.baseline_source) if baseline.baseline_source else None,
                  'source':str(baseline.source.resolve()) if baseline.source else None,
                  'resource_root':str(import_module('paths').resource_root()),
                  'main_python_gc':self.gc_events,'limits':'自动控制短测，仍有观测成本，不作长期或人工流畅度验收。'}
        (self.probe_output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__,parents=[selection])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--size',type=int,nargs=2,default=(2509,1180))
    parser.add_argument('--region',choices=('coastal','ridge','highway'),default='coastal')
    parser.add_argument('--impact-distance',type=float,default=20.)
    args = parser.parse_args()
    vehicle = WorkspaceVehicle.load(args.workspace.resolve())
    if vehicle is None:
        raise FileNotFoundError(args.workspace)
    output = args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    os.environ['COASTAL_STALL_CAPTURE'] = str(output)
    profile = None
    if args.region != 'coastal':
        from local_kcd_drive import LocalVegetation

        profile = LocalVegetation(ROOT/'logs/local-kcd-drive/assets', ROOT/'logs/local-kcd-original-environment')
        profile.install()
    session_process._serve = capture_authority
    app = ImpactProbe(output,vehicle,tuple(args.size),region=args.region,impact_distance=args.impact_distance)
    try:
        app.run()
    finally:
        if not (output/'summary.json').is_file():
            app.write_report(False)
        gc.callbacks.remove(app.record_gc)
        app.close_game()
        if profile is not None:
            profile.restore()
