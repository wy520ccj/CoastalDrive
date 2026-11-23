"""用默认渲染线程和独立物理会话实际行驶，记录显示帧耗；不是正式全步性能Gate。"""

import argparse
import json
import multiprocessing
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from panda3d.core import (
    ClockObject,
    Filename,
    PStatClient,
    RenderState,
    Shader,
    TransformState,
    WindowProperties,
    loadPrcFileData,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

import local_kcd_drive
from check_driving_composition import ViewDriver
from local_kcd_drive import LocalVegetation

from application import CoastalDrive
from driving_modes import DrivingMode
from session import Phase
from vehicle_workspace import WorkspaceVehicle


class DrivingProbe(CoastalDrive):
    def __init__(self, output, *, hard_lod=False, hide_grass=False, flat_roots=False, legacy_roots=False,
                 legacy_woodland=False, no_sky_transmission=False, legacy_grass_vertices=False,
                 end_distance=270, threading_model='/Draw', trace_state_cache=False):
        self.probe_output = output
        self.probe_hard_lod = hard_lod
        self.probe_hide_grass = hide_grass
        self.probe_flat_roots = flat_roots
        self.probe_legacy_roots = legacy_roots
        self.probe_legacy_woodland = legacy_woodland
        self.probe_no_sky_transmission = no_sky_transmission
        self.probe_legacy_grass_vertices = legacy_grass_vertices
        self.probe_driver = False
        self.probe_frames = []
        self.probe_views = []
        self.probe_capture_frame = -1
        self.probe_update = (0., 0.)
        self.probe_started = time.perf_counter()
        self.probe_requested = None
        self.probe_ready_seconds = None
        self.probe_end_distance = end_distance
        self.probe_trace_state_cache = trace_state_cache
        self.probe_gc_samples, self.probe_state_counts = [], []
        super().__init__(driving_mode=DrivingMode.GAME, workspace_vehicle=WorkspaceVehicle.load(),
                         threading_model=threading_model)
        if legacy_roots:
            self.render.setShaderInput('root_slope', (0., 0.))
        properties = WindowProperties()
        properties.setTitle('CoastalDrive · 自动随车复测（完成后关闭）')
        properties.setSize(1280, 720)
        properties.setFixedSize(True)
        self.win.requestProperties(properties)
        self.probe_last = time.perf_counter(), time.process_time()
        self.taskMgr.doMethodLater(1, self.probe_start, 'probe-start')
        self.taskMgr.add(self.probe_frame, 'probe-frame', sort=99)

    def probe_start(self, task):
        if self._workspace_steps is not None:
            return task.again
        self.open_career()
        self.probe_requested = time.perf_counter()
        self.career_action('start', 'ridge-run')
        return task.done

    def update(self, task):
        wall, cpu = time.perf_counter(), time.process_time()
        result = super().update(task)
        self.probe_update = (time.perf_counter() - wall, time.process_time() - cpu)
        return result

    def _ShowBase__garbageCollectStates(self, task):
        if not self.probe_trace_state_cache:
            return super()._ShowBase__garbageCollectStates(task)
        wall, cpu = time.perf_counter(), time.thread_time()
        result = super()._ShowBase__garbageCollectStates(task)
        self.probe_gc_samples.append({'frame': ClockObject.getGlobalClock().getFrameCount(),
            'wall_ms': (time.perf_counter()-wall)*1000, 'thread_cpu_ms': (time.thread_time()-cpu)*1000})
        if len(self.probe_gc_samples) % 30 == 0:
            self.probe_state_counts.append({'time': time.perf_counter()-self.probe_started,
                'render_states': RenderState.getNumStates(), 'transform_states': TransformState.getNumStates()})
        return result

    def probe_frame(self, task):
        now, cpu = time.perf_counter(), time.process_time()
        previous, previous_cpu = self.probe_last
        self.probe_last = now, cpu
        time_limit = 120+max(0, (self.probe_end_distance-270)/10)
        if now - self.probe_started > time_limit:
            raise TimeoutError('正常随车复测超时：'+str(time_limit)+'秒')
        if self.workspace != 'game' or self.session is None or self.session.phase != Phase.DRIVING:
            return task.cont
        if not self.probe_driver:
            self.probe_ready_seconds = now - self.probe_requested
            if self.probe_hard_lod:
                for node in self.scene.render.findAllMatches('**/+FadeLODNode'):
                    node.node().setFadeTime(0.)
            if self.probe_hide_grass:
                for node in self.scene.render.findAllMatches('**/local-kcd-grass-distance'):
                    node.hide()
            if self.probe_flat_roots:
                for node in self.scene.render.findAllMatches('**'):
                    node.clearShaderInput('root_slope')
                    if node.getName().startswith(('kcd-oak-', 'kcd-young-oak-', 'kcd-hawthorn-', 'local-collision-tree-')):
                        for stage in node.findAllTextureStages():
                            node.clearTexTransform(stage)
                self.scene.render.setShaderInput('root_slope', (0., 0.))
            self.session.set_controller(ViewDriver(), bind_world=True)
            self.probe_driver = True
            return task.cont
        state = self.session.current
        progress = self.session.simulation.road.locate(state.player)[0]
        properties = self.win.getProperties()
        row = {'wall_frame_ms': (now - previous) * 1000, 'parent_cpu_ms': (cpu - previous_cpu) * 1000,
               'update_wall_ms': self.probe_update[0] * 1000, 'update_cpu_ms': self.probe_update[1] * 1000,
               'render_frame': ClockObject.getGlobalClock().getFrameCount(), 'tick': state.tick,
               'progress_m': progress, 'speed_mps': state.player.speed,
               'dropped_time': self.session.stepper.dropped_time, 'backlog_time': self.session.stepper.backlog_time,
               'stream_frame_ms': self.scene.segment_work['frame_ms'],
               'size': [self.win.getXSize(), self.win.getYSize()],
               'foreground': properties.getForeground(), 'minimized': properties.getMinimized(),
               'after_capture': task.frame == self.probe_capture_frame + 1}
        self.probe_frames.append(row)
        targets = (40, 120, 190, 270)+tuple(d for d in (450, 900) if d <= self.probe_end_distance)
        if len(self.probe_views) < len(targets) and progress >= targets[len(self.probe_views)]:
            self.graphicsEngine.syncFrame()
            self.win.getScreenshot().write(Filename.fromOsSpecific(
                str(self.probe_output / (str(targets[len(self.probe_views)]) + 'm.png'))))
            self.probe_views.append({'tick': state.tick, 'progress_m': progress, 'speed_mps': state.player.speed,
                                     'collisions': state.collisions})
            self.probe_capture_frame = task.frame
            print('NORMAL VIEW', self.probe_views[-1], flush=True)
        if progress >= self.probe_end_distance:
            self.probe_finish()
            self.userExit()
            return task.done
        return task.cont

    def probe_finish(self):
        frames = self.probe_frames

        def summarize(rows):
            return {name: {'median': float(np.median([r[name] for r in rows])),
                           'p95': float(np.percentile([r[name] for r in rows], 95)),
                           'p99': float(np.percentile([r[name] for r in rows], 99)),
                           'max': max(r[name] for r in rows)} for name in (
                               'wall_frame_ms', 'parent_cpu_ms', 'update_wall_ms', 'update_cpu_ms', 'stream_frame_ms')}

        owner_tick, owner_dropped, owner_time = self.session.progress()
        report = {'scope': '默认/Draw、独立120Hz物理会话、正常跟车；Controller通过Control执行，不是人工驾驶或完整物理性能Gate',
                  'hard_lod': self.probe_hard_lod, 'hide_grass': self.probe_hide_grass,
                  'flat_roots': self.probe_flat_roots,
                  'legacy_root_transport': self.probe_legacy_roots,
                  'legacy_woodland_state': self.probe_legacy_woodland,
                  'no_sky_transmission': self.probe_no_sky_transmission,
                  'sky_transmission_compiled_out': self.probe_no_sky_transmission,
                  'legacy_grass_vertices': self.probe_legacy_grass_vertices,
                  'display_frames': len(frames), 'views': self.probe_views,
                  'foreground_frames': sum(row['foreground'] for row in frames),
                  'minimized_frames': sum(row['minimized'] for row in frames),
                  'entry_to_driving_seconds': self.probe_ready_seconds,
                  'stream_work': dict(self.scene.segment_work),
                  'woodland_maps': [{'segment': index,
                      'size': [node.getPythonTag('woodland-coverage')[0].getXSize(),
                               node.getPythonTag('woodland-coverage')[0].getYSize()]}
                                    for index, node in self.scene.segment_nodes.items()],
                  'sizes': sorted({tuple(row['size']) for row in frames}),
                  'renderer': self.win.getGsg().getDriverRenderer(),
                  'render_buffers': [{'name': buffer.getName(),
                                      'multisamples': buffer.getFbProperties().getMultisamples()}
                                     for buffer in self.pipeline._filtermgr.buffers],
                  'all_frames': summarize(frames),
                  'without_capture_readback': summarize([row for row in frames if not row['after_capture']]),
                  'owner_end': {'tick': owner_tick, 'dropped_time': owner_dropped, 'monotonic': owner_time},
                  'limits': 'parent_cpu不含独立物理进程；update_wall不是完整物理求解/IPC等待分解，不通过全步性能Gate'}
        (self.probe_output / 'frames.json').write_text(json.dumps(frames, indent=2), encoding='utf-8')
        if self.probe_trace_state_cache:
            (self.probe_output/'state-cache.json').write_text(json.dumps({
                'scope': '原ShowBase每帧原生缓存回收；CPU为主线程，不含绘制/物理线程',
                'collection_samples': self.probe_gc_samples, 'counts': self.probe_state_counts}, indent=2), encoding='utf-8')
        (self.probe_output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def check(output, hard_lod, hide_grass, pstats=False, flat_roots=False, legacy_roots=False, loading_profile=False,
          legacy_woodland=False, no_sky_transmission=False, legacy_grass_vertices=False, hd2_rocks=False,
          unfiltered_canopy_shadows=False, end_distance=270, threading_model='/Draw',
          gc_rate=None, trace_state_cache=False):
    output.mkdir(parents=True, exist_ok=False)
    source = Path(os.environ['LOCALAPPDATA']) / 'CoastalDrive'
    if source.is_dir():
        shutil.copytree(source, output / 'user/CoastalDrive')
    os.environ['LOCALAPPDATA'] = str(output / 'user')
    import kcd_local_environment

    original_foliage = kcd_local_environment.vegetation_material
    if no_sky_transmission:
        def compiled_without_sky(shader):
            material = original_foliage(shader)
            fragment = material.getText(Shader.STFragment).replace(
                'uniform float local_sky_transmission;', 'const float local_sky_transmission=0.;')
            return Shader.make(Shader.SLGLSL, material.getText(Shader.STVertex), fragment)

        kcd_local_environment.vegetation_material = compiled_without_sky
    original_root_vertex, original_root_slope = local_kcd_drive.rooted_vertex, local_kcd_drive.set_root_slope
    original_grass_shader = local_kcd_drive.grass_shader
    original_tree_shader = local_kcd_drive.tree_shader
    if unfiltered_canopy_shadows:
        def unfiltered_tree_shader(foliage):
            return original_tree_shader(foliage, filtered_shadows=False)

        local_kcd_drive.tree_shader = unfiltered_tree_shader
    if legacy_grass_vertices:
        def full_grass_vertices(foliage):
            return original_grass_shader(foliage, cull_absent=False)

        local_kcd_drive.grass_shader = full_grass_vertices
    original_woodland = local_kcd_drive.apply_woodland_inputs
    if legacy_woodland:
        def root_woodland(root, texture, bounds):
            root.setPythonTag('woodland-coverage', (texture, bounds))
            root.setShaderInput('local_forest_coverage', texture)
            root.setShaderInput('local_forest_bounds', bounds)

        local_kcd_drive.apply_woodland_inputs = root_woodland
    if legacy_roots:
        def legacy_vertex(vertex, position_line, position_name):
            return original_root_vertex(vertex, position_line, position_name).replace(
                'vec2 root_slope = p3d_TextureMatrix[2].xy;', '').replace(
                'uniform float root_anchor;', 'uniform float root_anchor;\nuniform vec2 root_slope;')

        local_kcd_drive.rooted_vertex = legacy_vertex
        local_kcd_drive.set_root_slope = lambda node, slope: node.setShaderInput('root_slope', slope)
    profile = LocalVegetation(ROOT / 'logs/local-kcd-drive/assets', ROOT / 'logs/local-kcd-original-environment',
                              sky_transmission=0. if no_sky_transmission else 1., hd2_rocks=hd2_rocks)
    profile.install()
    loading_samples = {}
    if loading_profile:
        actual_load = local_kcd_drive.expressway.load_kit
        actual_segment = local_kcd_drive.expressway_route.segment_steps

        def record(label, wall, cpu):
            loading_samples.setdefault(label, []).append(((time.perf_counter() - wall) * 1000,
                                                         (time.thread_time() - cpu) * 1000))

        def measured_load(*args, **kwargs):
            wall, cpu = time.perf_counter(), time.thread_time()
            try:
                return actual_load(*args, **kwargs)
            finally:
                record('load_kit', wall, cpu)

        def measured_segment(*args, **kwargs):
            work = actual_segment(*args, **kwargs)
            try:
                while True:
                    wall, cpu = time.perf_counter(), time.thread_time()
                    try:
                        phase = next(work)
                    except StopIteration:
                        record('segment-finish', wall, cpu)
                        return
                    record(phase, wall, cpu)
                    yield phase
            finally:
                work.close()

        local_kcd_drive.expressway.load_kit = measured_load
        local_kcd_drive.expressway_route.segment_steps = measured_segment
    app, recorder, record_log = None, None, None
    try:
        if pstats:
            import panda3d_tools

            with socket.socket() as endpoint:
                endpoint.bind(('127.0.0.1', 0))
                port = endpoint.getsockname()[1]
            record_log = (output / 'pstats-server.log').open('w', encoding='utf-8')
            recorder = subprocess.Popen([str(Path(panda3d_tools.__file__).parent / 'text-stats.exe'),
                '-p', str(port), '-o', str(output / 'pstats.txt')], stdout=record_log, stderr=record_log,
                creationflags=subprocess.CREATE_NO_WINDOW)
            loadPrcFileData('render-probe', 'pstats-gpu-timing true\npstats-tasks true\npstats-max-rate 20')
        app = DrivingProbe(output, hard_lod=hard_lod, hide_grass=hide_grass, flat_roots=flat_roots,
                           legacy_roots=legacy_roots, legacy_woodland=legacy_woodland,
                           no_sky_transmission=no_sky_transmission, legacy_grass_vertices=legacy_grass_vertices,
                           end_distance=end_distance, threading_model=threading_model, trace_state_cache=trace_state_cache)
        if gc_rate is not None:
            loadPrcFileData('local-state-cache-probe', 'garbage-collect-states-rate '+str(gc_rate))
        if pstats:
            assert recorder.poll() is None, 'PStats记录器退出，查看pstats-server.log'
            assert PStatClient.connect('127.0.0.1', port), '无法连接本轮PStats记录器'
        app.run()
        if not (output/'summary.json').exists():
            (output/'incomplete.json').write_text(json.dumps({
                'completed': False, 'target_distance': end_distance, 'phase': app.session.phase.value,
                'recorded_frames': len(app.probe_frames), 'views': app.probe_views,
                'state_counts': app.probe_state_counts, 'collection_samples': app.probe_gc_samples,
                'reason': '窗口在目标行驶完成前结束；不能作为该距离或性能通过证据'}, ensure_ascii=False, indent=2), encoding='utf-8')
            raise RuntimeError('正常随车复测提前结束，见incomplete.json')
        summary = json.loads((output/'summary.json').read_text(encoding='utf-8'))
        summary.update(threading_model=threading_model, gc_rate=gc_rate, target_distance=end_distance,
                       trace_state_cache=trace_state_cache)
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        if app is not None:
            app.close_game()
        if recorder is not None:
            PStatClient.disconnect()
            if recorder.poll() is None:
                recorder.terminate()
            recorder.wait(timeout=10)
        if record_log is not None:
            record_log.close()
        if loading_profile:
            report = {'scope': '安装本机表现后实际绑定入口；生成器仅测next执行，不含yield间等待；CPU仅主线程；非全步物理Gate',
                      'phases': {name: {'count': len(samples),
                          'wall_ms': {'total': sum(row[0] for row in samples), 'max': max(row[0] for row in samples),
                                      'p95': float(np.percentile([row[0] for row in samples], 95))},
                          'main_thread_cpu_ms': {'total': sum(row[1] for row in samples), 'max': max(row[1] for row in samples)}}
                                 for name, samples in loading_samples.items()}}
            (output / 'loading-phases.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        profile.restore()
        kcd_local_environment.vegetation_material = original_foliage
        local_kcd_drive.apply_woodland_inputs = original_woodland
        local_kcd_drive.rooted_vertex, local_kcd_drive.set_root_slope = original_root_vertex, original_root_slope
        local_kcd_drive.grass_shader = original_grass_shader
        local_kcd_drive.tree_shader = original_tree_shader


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hard-lod', action='store_true')
    parser.add_argument('--hide-grass', action='store_true')
    parser.add_argument('--pstats', action='store_true')
    parser.add_argument('--flat-roots', action='store_true', help='仅诊断逐树ShaderInput切换成本')
    parser.add_argument('--legacy-root-transport', action='store_true', help='诊断时恢复旧逐树ShaderInput')
    parser.add_argument('--loading-profile', action='store_true', help='分解安装后实际资源入口与构建步骤')
    parser.add_argument('--legacy-woodland-state', action='store_true', help='诊断时恢复整段继承的林地输入')
    parser.add_argument('--no-sky-transmission', action='store_true', help='诊断时关闭木本叶片的背面天空透光')
    parser.add_argument('--legacy-grass-vertices', action='store_true', help='诊断时不跳过已经判为不显示的草顶点')
    parser.add_argument('--hd2-rocks', action='store_true', help='本机HD2岩壁样板，原安装只读')
    parser.add_argument('--unfiltered-canopy-shadows', action='store_true', help='对照时仅恢复旧木本阴影读取')
    parser.add_argument('--end-distance', type=int, choices=(270, 450, 900), default=270)
    parser.add_argument('--pipeline', choices=('draw', 'cull-draw'), default='draw')
    parser.add_argument('--gc-rate', type=float, help='仅诊断进程的原生状态缓存回收比例')
    parser.add_argument('--trace-state-cache', action='store_true', help='测量原回收任务成本及缓存数量')
    arguments = parser.parse_args()
    if arguments.gc_rate is not None and not 0 < arguments.gc_rate <= 1:
        parser.error('--gc-rate须在(0,1]内')
    check(arguments.output.resolve(), arguments.hard_lod, arguments.hide_grass, arguments.pstats,
          arguments.flat_roots, arguments.legacy_root_transport, arguments.loading_profile, arguments.legacy_woodland_state,
          arguments.no_sky_transmission, arguments.legacy_grass_vertices, arguments.hd2_rocks,
          arguments.unfiltered_canopy_shadows, arguments.end_distance,
          {'draw': '/Draw', 'cull-draw': 'Cull/Draw'}[arguments.pipeline],
          arguments.gc_rate, arguments.trace_state_cache)
