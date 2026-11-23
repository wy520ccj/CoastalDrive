"""用已知斜面深度图验证接收平面比较，区分算法错误与实际投影几何问题。"""

import argparse
import json
from pathlib import Path

import numpy as np
from direct.showbase.ShowBase import ShowBase
from panda3d.core import CardMaker, Shader, Texture, loadPrcFileData

ROOT = Path(__file__).resolve().parents[2]


def check(output):
    loadPrcFileData('city-shadow-check', '''window-type offscreen
win-size 256 128
audio-library-name null
framebuffer-srgb false
sync-video false''')
    app = ShowBase()
    try:
        card = CardMaker('receiver-plane')
        card.setFrameFullscreenQuad()
        node = app.render2d.attachNewNode(card.generate())
        size = 32
        u, v = np.meshgrid((np.arange(size)+.5)/size, (np.arange(size)+.5)/size)
        depths = (.25+.35*u+.1*v).astype('float32')
        texture = Texture('known-sloped-shadow-depth')
        texture.setup2dTexture(size, size, Texture.TFloat, Texture.FDepthComponent32)
        texture.setMinfilter(Texture.FTShadow)
        texture.setMagfilter(Texture.FTShadow)
        texture.setRamImage(depths.tobytes())
        node.setShaderInput('shadowmap', texture)
        node.setShaderInput('global_shadow_bias', .0007)
        vertex = '''#version 330
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
void main() { gl_Position=p3d_ModelViewProjectionMatrix*p3d_Vertex; }
'''
        rows = []
        for label in ('shadow-transition.glsl', 'city-shadow.glsl'):
            folder = ('art/expressway/candidates/city-shadow' if label == 'city-shadow.glsl' else
                      'assets/game/expressway/shaders')
            source = (ROOT/folder/label).read_text(encoding='utf-8')
            fragment = '''#version 330
uniform sampler2DShadow shadowmap;
uniform float global_shadow_bias;
out vec4 o_color;
'''+source+'''
void main() {
    vec2 uv=vec2(.22)+gl_FragCoord.xy/vec2(256.,128.)*.56;
    // 右半是比接收面更近的真实遮挡；左半应全受光。
    float z=.25+.35*uv.x+.1*uv.y+(gl_FragCoord.x>=128. ? .08 : 0.);
    float shadow=shadow_caster_contrib(shadowmap,vec4(uv,z,1.));
    o_color=vec4(vec3(shadow),1.);
}
'''
            shader = Shader.make(Shader.SLGLSL, vertex, fragment)
            node.setShader(shader)
            for _ in range(3):
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            assert not shader.getErrorFlag()
            values = np.frombuffer(app.win.getScreenshot().getRamImageAs('RGB'), dtype=np.uint8).reshape(128, 256, 3)
            rows.append({'shader': label, 'lit_min': int(values[:, :120, 0].min()),
                         'lit_mean': float(values[:, :120, 0].mean()),
                         'occluded_max': int(values[:, 136:, 0].max())})
        report = {'scope': '256x128离屏、已知斜面32x32深度图；不是游戏画面或帧耗。', 'rows': rows}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')
        assert rows[0]['lit_min'] < 200
        assert rows[1]['lit_min'] >= 254
        assert rows[1]['occluded_max'] <= 1
        return report
    finally:
        app.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve()), indent=2))
