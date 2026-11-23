"""诊断原着色器改读原生相机矩阵，保留实际镜位并检查根材质不再按帧切换。"""

import argparse
import importlib
import json
import multiprocessing
import os
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar

from panda3d.core import Shader, ShaderInput
from simplepbr import Pipeline

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tools/environment'))

import check_interactive_local_drive
from check_interactive_local_drive import DrivingProbe, check

import application
from rendering import ScenePipeline


def capture_serve(*args):
    import session_process
    from simulation import Simulation

    original = Simulation.step
    output = Path(os.environ['COASTAL_PERFORMANCE_CAPTURE'])

    def step(world, control, *values, **kwargs):
        if world._tick == 0:
            world._performance_controls = []
        world._performance_controls.append(asdict(control))
        try:
            return original(world, control, *values, **kwargs)
        except ArithmeticError as error:
            (output/'mechanical-failure.json').write_text(json.dumps({
                'exception': str(error), 'seed': world.seed, 'track': world.track,
                'road_shape': world.road_shape, 'config': asdict(world.config),
                'before': asdict(world.snapshot()), 'controls': world._performance_controls,
                'scope': '实际权威进程的原参数/逐拍Control与失败前完成状态；诊断记录不作吞吐验收'},
                ensure_ascii=False, indent=2), encoding='utf-8')
            raise

    Simulation.step = step
    session_process._serve(*args)


def native_source(source):
    source = source.replace('uniform vec3 camera_world_position;', '')
    if 'camera_world_position' not in source or '#define camera_world_position' in source:
        return source
    header = '#define camera_world_position (p3d_ViewMatrixInverse[3].xyz)\n'
    if 'uniform mat4 p3d_ViewMatrixInverse;' not in source:
        header += 'uniform mat4 p3d_ViewMatrixInverse;\n'
    # #version必须仍为第一行；其余原宏/源码变换均保留。
    first, rest = source.split('\n', 1)
    return first+'\n'+header+rest


def native_shader(shader):
    return Shader.make(Shader.SLGLSL, native_source(shader.getText(Shader.STVertex)),
                       native_source(shader.getText(Shader.STFragment)))


class NativeCameraPipeline(ScenePipeline):
    def _recompile_pbr(self):
        super()._recompile_pbr()
        self.render_node.setShader(native_shader(self.render_node.getShader()))

    def _update(self, task):
        result = Pipeline._update(self, task)
        self.render_node.clearShaderInput('camera_world_position')
        return result


def install():
    def make(language, vertex, fragment):
        assert language == Shader.SLGLSL
        return Shader.make(language, native_source(vertex), native_source(fragment))

    def load(language, vertex, fragment):
        return native_shader(Shader.load(language, vertex, fragment))

    facade = SimpleNamespace(SLGLSL=Shader.SLGLSL, STVertex=Shader.STVertex, STFragment=Shader.STFragment,
                             make=make, load=load)
    names = ('environment.expressway_materials', 'environment.water', 'sky_dome', 'ui.garage_reflection',
             'ui.garage_paint', 'local_kcd_drive', 'local_coastal_landscape', 'kcd_local_environment')
    originals = []
    for name in names:
        module = importlib.import_module(name)
        originals.append((module, module.Shader))
        module.Shader = facade
    return originals


class NativeProbe(DrivingProbe):
    instances: ClassVar[list] = []
    native_enabled: ClassVar[bool] = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instances.append(self)

    def probe_finish(self):
        super().probe_finish()
        report = {'camera_input_present': self.render.getShaderInput('camera_world_position').getValueType() != ShaderInput.M_invalid,
                  'native_enabled': self.native_enabled,
                  'scope': '相机候选或当前正式入口的诊断；逐拍记录机械控制输入，非原生求解器吞吐验收'}
        (self.probe_output/'native-camera.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true', help='保留正式相机输入，仅捕获机械异常')
    parser.add_argument('--end-distance', type=int, choices=(270, 450, 900), default=450)
    args = parser.parse_args()
    import session_process

    os.environ['COASTAL_PERFORMANCE_CAPTURE'] = str(args.output.resolve())
    session_process._serve = capture_serve
    originals = [] if args.baseline else install()
    NativeProbe.native_enabled = not args.baseline
    if not args.baseline:
        application.ScenePipeline = NativeCameraPipeline
    check_interactive_local_drive.DrivingProbe = NativeProbe
    try:
        check(args.output.resolve(), False, False, trace_state_cache=True, end_distance=args.end_distance)
    finally:
        if NativeProbe.instances and not (args.output/'summary.json').exists():
            app = NativeProbe.instances[-1]
            (args.output/'partial-frames.json').write_text(json.dumps(app.probe_frames), encoding='utf-8')
            (args.output/'partial-states.json').write_text(json.dumps({
                'counts': app.probe_state_counts, 'collections': app.probe_gc_samples,
                'scope': '未完成450m，不是通过样本'}), encoding='utf-8')
        for module, original in originals:
            module.Shader = original
