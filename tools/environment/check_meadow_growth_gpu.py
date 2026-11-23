"""实际GPU回读世界坐标草坡生长场，测量分布并核对原点重定位一致性。"""

import argparse
import json
from pathlib import Path

import numpy as np
from direct.showbase.ShowBase import ShowBase
from kcd_local_environment import MATERIAL, MEADOW_COLOR, source_texture
from panda3d.core import CardMaker, Shader, loadPrcFileData

ROOT = Path(__file__).resolve().parents[2]


def check(output, raw):
    loadPrcFileData('meadow-growth-check', '''window-type offscreen
win-size 200 200
audio-library-name null
framebuffer-srgb false
framebuffer-alpha true
alpha-bits 8
sync-video false''')
    app = ShowBase()
    try:
        card = CardMaker('meadow-field-readback')
        card.setFrameFullscreenQuad()
        node = app.render2d.attachNewNode(card.generate())
        field = MEADOW_COLOR
        if raw:
            assert 'return smoothstep(.059,.071,patch);' in field
            field = field.replace('return smoothstep(.059,.071,patch);', 'return patch;')
        node.setShader(Shader.make(Shader.SLGLSL, '''#version 330
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
void main() { gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; }
''', '#version 330\n' + field + '''
out vec4 o_color;
void main() {
    vec2 local = vec2(-200.,-100.)+floor(gl_FragCoord.xy)*2.-vec2(0.,local_origin_y);
    uint bits = floatBitsToUint(meadow_growth(local));
    o_color = vec4(uvec4(bits,bits>>8,bits>>16,bits>>24)&uvec4(255))/255.;
}
'''))
        folder = ROOT / 'logs/local-kcd-original-environment'
        node.setShaderInput('local_ground_meadow', source_texture(folder / 'pasture-albedo.png', color=True))
        node.setShaderInput('local_ground_dry', source_texture(folder / 'dry-albedo.png', color=True))
        arrays = []
        for origin in (0., 2000., -2000.):
            node.setShaderInput('local_origin_y', origin)
            for _ in range(3):
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            assert not node.getShader().getErrorFlag()
            arrays.append(np.frombuffer(app.win.getScreenshot().getRamImageAs('RGBA'), dtype='<f4').copy())
        assert all(np.all(np.isfinite(values)) for values in arrays)
        errors = [float(np.max(np.abs(values-arrays[0]))) for values in arrays[1:]]
        report = {'scope': '2m采样400x400m世界范围，实际GPU纹理LOD6，位编码精确回读；原点0/正负2000m',
                  'raw_signal': raw, 'percentiles_0_10_25_50_75_90_100': np.percentile(arrays[0], [0, 10, 25, 50, 75, 90, 100]).tolist(),
                  'fraction_below_point2': float(np.mean(arrays[0] < .2)),
                  'fraction_above_point8': float(np.mean(arrays[0] > .8)), 'origin_max_error': errors}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        assert max(errors) == 0., report
        if not raw:
            assert report['fraction_below_point2'] > .1 and report['fraction_above_point8'] > .1, report
        return report
    finally:
        app.destroy()


def check_city_lawn(output):
    """回读实际地表shader的城市遮罩，核对UV回绕、种子偏移和原物理树带。"""
    import sys

    sys.path.insert(0, str(ROOT/'src'))
    from environment.expressway_route import _city_shift, city_weight

    loadPrcFileData('city-lawn-check', '''window-type offscreen
win-size 200 200
audio-library-name null
framebuffer-srgb false
framebuffer-alpha true
alpha-bits 8
sync-video false''')
    app = ShowBase()
    try:
        card = CardMaker('city-lawn-readback')
        card.setFrameFullscreenQuad()
        node = app.render2d.attachNewNode(card.generate())
        field = MATERIAL[MATERIAL.index('uniform vec2 city_lawn_phase;'):MATERIAL.index('float ground_dry_weight()')]
        node.setShader(Shader.make(Shader.SLGLSL, '''#version 330
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
void main() { gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; }
''', '#version 330\nvec2 v_texcoord;\nuniform float uv_start;\nuniform int read_uv;\n'+field+'''
out vec4 o_color;
void main() {
    v_texcoord = vec2(-50.+floor(gl_FragCoord.x)*1.5,uv_start+floor(gl_FragCoord.y)*200./199.);
    uint bits = floatBitsToUint(read_uv > 0 ? v_texcoord.y : city_lawn_weight());
    o_color = vec4(uvec4(bits,bits>>8,bits>>16,bits>>24)&uvec4(255))/255.;
}
'''))

        def smooth(a, b, values):
            t = np.clip((values-a)/(b-a), 0, 1)
            return t*t*(3-2*t)

        across = -50+np.arange(200)*1.5
        rows = []
        uv_rows = {}

        def read_values():
            for _ in range(3):
                app.graphicsEngine.renderFrame()
            app.graphicsEngine.syncFrame()
            assert not node.getShader().getErrorFlag()
            return np.frombuffer(app.win.getScreenshot().getRamImageAs('RGBA'), dtype='<f4').reshape(200, 200)

        for seed in (0, 23):
            for start in (3000, 3200, 3400, 5000, 5200, 5400, 5600, 6000, 6200, 8000):
                node.setShaderInput('uv_start', float(start % 600))
                node.setShaderInput('city_lawn_phase', (start % 8000-start % 600+seed % 5*160, 1.))
                if start % 600 not in uv_rows:
                    # 先回读GPU实际UV，避免编译器常数除法与CPU除法的量化差异混入函数误差。
                    node.setShaderInput('read_uv', 1)
                    uv_rows[start % 600] = read_values()[:, 0].astype(np.float64)
                node.setShaderInput('read_uv', 0)
                actual = read_values()
                positions = start-start % 600+uv_rows[start % 600]
                along = np.array([city_weight(s, seed) for s in positions])
                shifts = np.array([_city_shift(s, seed) for s in positions])[:, None]
                transverse = smooth(61.5, 68.5, across-shifts)*(1-smooth(151.5, 158.5, across-shifts))
                expected = along[:, None]*transverse[None, :]
                error = float(np.abs(actual-expected).max())
                assert np.isfinite(actual).all()
                assert np.all(actual[:, across <= 35] == 0)
                rows.append({'seed': seed, 'start': start, 'max_error': error,
                             'max_weight': float(actual.max())})
        output.parent.mkdir(parents=True, exist_ok=True)
        report = {'scope': '200x200离屏GPU实际函数回读；局部600m UV、8000m城市周期及两种子，不是驾驶帧耗。',
                  'cases': rows, 'max_error': max(row['max_error'] for row in rows),
                  'protected_band_weight': 0, 'onscreen': False}
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        # 新桥位横向渐变比原240米纵向渐变陡；只容许单精度计算误差，保护带仍严格为零。
        assert report['max_error'] < 1e-5, report
        return report
    finally:
        app.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--raw', action='store_true')
    parser.add_argument('--city-lawn', action='store_true')
    arguments = parser.parse_args()
    result = (check_city_lawn(arguments.output.resolve()) if arguments.city_lawn else
              check(arguments.output.resolve(), arguments.raw))
    print(json.dumps(result, ensure_ascii=False))
