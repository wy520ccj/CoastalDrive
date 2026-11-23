"""固定同一轮廓验证近远树交接互补，不因两次alpha覆盖而凭空少一半树。"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Filename, OrthographicLens, RenderState, Shader, Vec3, loadPrcFileData

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/environment'))
sys.path.insert(0, str(ROOT/'src'))

from kcd_tree_batches import SOURCE_DTYPE, make_batch, shaders

from environment.surface_mesh import surface_mesh


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    loadPrcFileData('tree-coverage', 'window-type offscreen\nwin-size 128 128\naudio-library-name null\nsync-video false\nthreading-model ')
    app = ShowBase()
    try:
        app.setBackgroundColor(0, 0, 0)
        lens = OrthographicLens()
        lens.setFilmSize(4, 4)
        lens.setNearFar(1, 1000)
        app.cam.node().setLens(lens)
        points = [(-1, 0, -1), (1, 0, -1), (1, 0, 1), (-1, 0, 1)]
        faces = [(0, 1, 2), (0, 2, 3)]
        near = surface_mesh('near', points, faces, [(0, -1, 0)]*4, [(1, 1, 1, 1)]*4,
                            [(0, 0), (1, 0), (1, 1), (0, 1)])
        near.reparentTo(app.render)
        source = Shader.make(Shader.SLGLSL, '''#version 330
uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
void main() { gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; }
''', '''#version 330
out vec4 color;
void main() { float foliage_visibility = 1.; color=vec4(1.,1.,1.,foliage_visibility); }
''')
        near_shader, far_shader = shaders(source)
        near.setShader(near_shader, 2)
        near.setShaderInput('tree_center', Vec3(0))
        vertices = np.zeros(4, dtype=SOURCE_DTYPE)
        vertices['p'] = points
        vertices['n'] = (0, -1, 0)
        vertices['c'] = 255
        make_batch(app.render, 'far', [(vertices, np.zeros((4, 3), dtype='<f4'),
                                       np.array(faces, dtype='<u4').ravel())], RenderState.makeEmpty(), far_shader)
        rows = []
        for distance in (100, 120, 125, 130, 135, 140, 160):
            app.camera.setPos(0, -distance, 0)
            app.camera.lookAt(0, 0, 0)
            app.render.setShaderInput('camera_world_position', Vec3(0, -distance, 0))
            for _ in range(8):
                app.graphicsEngine.renderFrame()
            image = app.win.getScreenshot()
            image.write(Filename.fromOsSpecific(str(output/(str(distance)+'.png'))))
            rgb = np.frombuffer(image.getRamImageAs('RGB'), dtype=np.uint8).reshape(128, 128, 3)
            interior = rgb[36:92, 36:92]
            rows.append({'distance': distance, 'interior_min_rgb8': int(interior.min()),
                         'missing_channels': int(np.count_nonzero(interior != 255))})
        result = {'scope': '同轮廓固定尺度，100–160m，近远交接全部内部像素应持续覆盖；不是原树轮廓/美术或性能验收',
                  'samples': rows, 'passed': all(row['missing_channels'] == 0 for row in rows)}
        (output/'coverage.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        assert not near_shader.getErrorFlag() and not far_shader.getErrorFlag()
        assert result['passed'], result
    finally:
        app.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    check(args.output.resolve())
