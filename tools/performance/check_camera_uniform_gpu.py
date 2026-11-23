"""实际GPU检查移动相机的输入与当前Draw矩阵一致，并比较原输入像素。"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from direct.showbase.ShowBase import ShowBase
from panda3d.core import CardMaker, Filename, Shader, Vec3, loadPrcFileData

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from rendering import ScenePipeline


def check(output, model):
    output.mkdir(parents=True, exist_ok=False)
    loadPrcFileData('camera-uniform-gpu', '\n'.join((
        'window-type offscreen', 'win-size 64 64', 'audio-library-name null',
        'sync-video false', 'transform-cache false', 'threading-model '+model)))
    app = ShowBase()
    try:
        pipeline = ScenePipeline(enable_shadows=False, max_lights=1, use_330=True)
        app.taskMgr.remove('simplepbr update')
        card = CardMaker('camera-uniform-probe')
        card.setFrame(-1, 1, -1, 1)
        node = app.render.attachNewNode(card.generate())
        vertex = '''#version 330
uniform mat4 p3d_ViewMatrixInverse;
uniform vec3 camera_world_position;
in vec4 p3d_Vertex;
flat out vec3 supplied;
flat out vec3 from_matrix;
void main() {
    supplied = camera_world_position;
    from_matrix = p3d_ViewMatrixInverse[3].xyz;
    gl_Position = vec4(p3d_Vertex.x, p3d_Vertex.z, 0., 1.);
}
'''
        fragment = '''#version 330
flat in vec3 supplied;
flat in vec3 from_matrix;
out vec4 o_color;
void main() { o_color = vec4(min(abs(supplied-from_matrix),vec3(1.)),1.); }
'''
        shader = Shader.make(Shader.SLGLSL, vertex, fragment)
        node.setShader(shader, 100)
        # 禁止CPU视锥剔除这张诊断满屏卡，保证每帧都真正执行shader。
        from panda3d.core import OmniBoundingVolume

        node.node().setBounds(OmniBoundingVolume())
        maxima, states = [], set()
        for frame in range(180):
            app.camera.setPos(Vec3((frame % 17)*.125, (frame % 23)*.25, (frame % 31)*.5))
            app.camera.setHpr(frame % 90, frame % 30, 0)
            # update和igLoop沿产品顺序运行；不在输入更新和Draw间额外同步。
            pipeline._update(type('Task', (), {'DS_cont': 1})())
            states.add(app.render.getState())
            app.taskMgr.step()
            if frame > 5:
                app.graphicsEngine.syncFrame()
                picture = app.win.getScreenshot()
                maxima.append(int(np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).max()))
        assert not shader.getErrorFlag()
        picture.write(Filename.fromOsSpecific(str(output/'matrix-error.png')))
        report = {'threading_model': model, 'frames': len(maxima),
                  'position_buffers': len(pipeline._camera_positions), 'root_states': len(states),
                  'maximum_rgb8_matrix_error': max(maxima), 'passed': max(maxima) == 0}
        (output/'gpu.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        assert report['passed'], report
        assert len(states) == len(pipeline._camera_positions), report
        return report
    finally:
        app.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pipeline', choices=('single', 'draw', 'cull-draw'), default='draw')
    args = parser.parse_args()
    print(check(args.output.resolve(), {'single': '', 'draw': '/Draw', 'cull-draw': 'Cull/Draw'}[args.pipeline]))
