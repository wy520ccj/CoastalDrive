"""通过实际GPU采样核对草地浮点高度，防止16米等世界高度被普通颜色格式截断。"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from direct.showbase.ShowBase import ShowBase
from panda3d.core import CardMaker, Shader, Texture, loadPrcFileData

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from local_kcd_drive import grass_heightfield


def check(course, output, *, legacy_format=False):
    texture, _origin, _mode = grass_heightfield(course)
    if legacy_format:
        texture.setFormat(Texture.FRed)
    width, height = texture.getXSize(), texture.getYSize()
    expected = np.frombuffer(texture.getRamImage(), dtype=np.float32).reshape(height, width).copy()
    loadPrcFileData('heightfield-gpu-check', '\n'.join((
        'window-type offscreen', f'win-size {width} {height}', 'audio-library-name null',
        'framebuffer-srgb false', 'framebuffer-alpha true', 'alpha-bits 8', 'sync-video false')))
    app = ShowBase()
    try:
        card = CardMaker('heightfield-readback')
        card.setFrameFullscreenQuad()
        node = app.render2d.attachNewNode(card.generate())
        node.setShader(Shader.make(Shader.SLGLSL, '''#version 330
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
void main() { gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; }
''', '''#version 330
uniform sampler2D heights;
out vec4 o_color;
void main() {
    uint bits = floatBitsToUint(texelFetch(heights,ivec2(gl_FragCoord.xy),0).r);
    o_color = vec4(uvec4(bits,bits>>8,bits>>16,bits>>24)&uvec4(255))/255.;
}
'''))
        node.setShaderInput('heights', texture)
        for _ in range(3):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        assert not node.getShader().getErrorFlag()
        picture = app.win.getScreenshot()
        assert (picture.getXSize(), picture.getYSize()) == (width, height)
        actual = np.frombuffer(picture.getRamImageAs('RGBA'), dtype='<f4').reshape(height, width)
        assert np.all(np.isfinite(actual))
        error = float(np.max(np.abs(actual - expected)))
        report = {'course': course, 'size': [width, height], 'format': texture.getFormat(),
                  'legacy_format': legacy_format,
                  'cpu_range_m': [float(expected.min()), float(expected.max())],
                  'gpu_range_m': [float(actual.min()), float(actual.max())], 'max_error_m': error,
                  'scope': '实际GPU texelFetch后按浮点位编码回读；不改变或验证车辆物理'}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        assert error < 1e-4, report
        return report
    finally:
        app.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course', required=True, choices=('coast-club', 'ridge-club', 'coast-final'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--legacy-format', action='store_true')
    arguments = parser.parse_args()
    print(json.dumps(check(arguments.course, arguments.output, legacy_format=arguments.legacy_format), ensure_ascii=False))
