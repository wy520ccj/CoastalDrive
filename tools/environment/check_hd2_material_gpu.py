"""单独原岩壁的真实GPU分量检查；不算驾驶画面验收。"""

import argparse
import json
from pathlib import Path

import numpy as np
from hd2_local_rocks import load_rock
from panda3d.core import Filename, Shader, loadPrcFileData


def check(output):
    from direct.showbase.ShowBase import ShowBase

    output.mkdir(parents=True, exist_ok=False)
    loadPrcFileData('hd2-material-check', 'window-type offscreen\nwin-size 800 450\naudio-library-name null\nframebuffer-srgb true')
    app = ShowBase()
    try:
        app.disableMouse()
        app.setBackgroundColor(.1, .12, .14)
        rock = load_rock()
        rock.reparentTo(app.render)
        rock.node().forceSwitch(0)
        app.camera.setPos(0, -15, 5)
        app.camera.lookAt(0, 0, 1.5)
        app.render.setShaderInput('camera_world_position', app.camera.getPos())
        app.camLens.setNearFar(.1, 100)
        shader = rock.getShader()
        output_line = 'o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);'
        fragment = shader.getText(Shader.STFragment)
        variants = {'solid': 'vec4(1.,0.,1.,1.)', 'albedo': 'hd2_color()',
                    'base-b': 'vec4(vec3(texture(hd2_base,v_texcoord).b),1.)',
                    'array-b': 'vec4(vec3(hd2_surface().b),1.)',
                    'ao': 'vec4(vec3(ambient_occlusion),1.)'}
        records, mask = [], None
        for label, expression in variants.items():
            candidate = Shader.make(Shader.SLGLSL, shader.getText(Shader.STVertex),
                                    fragment.replace(output_line, 'o_color=' + expression + ';'))
            rock.setShader(candidate, 3)
            for _ in range(4):
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            assert not candidate.getErrorFlag(), label
            pixels = app.win.getScreenshot()
            pixels.write(Filename.fromOsSpecific(str(output / (label + '.png'))))
            values = np.frombuffer(pixels.getRamImageAs('RGB'), dtype=np.uint8).reshape(450, 800, 3)
            if label == 'solid':
                mask = (values[:, :, 0] > 250) & (values[:, :, 1] < 5) & (values[:, :, 2] > 250)
                assert np.count_nonzero(mask) > 10000
            minimum = int(values[:, :, 0][mask].min())
            records.append({'variant': label, 'center_rgb8': values[225, 400].tolist(),
                            'rock_min_red8': minimum})
            if label == 'base-b':
                # 原AO最小117，sRGB显示只会更亮；预乘损坏会使这项实际GPU检查出现0。
                assert minimum >= 117, records
        (output / 'gpu-components.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    finally:
        app.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    check(arguments.output.absolute())
