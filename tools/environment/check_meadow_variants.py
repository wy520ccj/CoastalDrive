"""同一真实随车时刻比较31草坡高度斑块，并输出生长场；不改物理。"""

import argparse
import json
from pathlib import Path

from check_driving_composition import check
from panda3d.core import Filename, Shader, ShaderAttrib


def compare(app, output):
    items = [(node, number, node.node().getGeomState(number),
              node.getNetState().compose(node.node().getGeomState(number)).getAttrib(ShaderAttrib))
             for node in app.scene.render.findAllMatches('**/+GeomNode')
             if node.getName() in ('kcd-stream-grass', 'course-landscape', 'route-landscape')
             for number in range(node.node().getNumGeoms())]
    for tree in app.scene.render.findAllMatches('**/+FadeLODNode'):
        tree.node().setFadeTime(0.)
    report = []
    for label, scale in (('current', 'mix(.3,1.35,grass_growth)'),
                         ('strong', 'mix(.25,1.65,grass_growth)'),
                         ('lower', 'mix(.4,1.12,grass_growth)'), ('field', None)):
        shaders = []
        for node, number, state, attrib in items:
            shader = attrib.getShader()
            vertex, fragment = shader.getText(Shader.STVertex), shader.getText(Shader.STFragment)
            if scale is not None and node.getName() == 'kcd-stream-grass':
                assert 'mix(.3,1.35,grass_growth)' in vertex
                vertex = vertex.replace('mix(.3,1.35,grass_growth)', scale)
            if label == 'field':
                output_line = 'o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);'
                assert output_line in fragment
                fragment = fragment.replace(output_line, 'o_color = vec4(vec3(meadow_growth(v_world_position.xy)),1.);')
            changed = Shader.make(Shader.SLGLSL, vertex, fragment)
            shaders.append(changed)
            node.node().setGeomState(number, state.setAttrib(attrib.setShader(changed, 100), 100))
        for _ in range(12):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        assert all(not shader.getErrorFlag() for shader in shaders), label
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / ('meadow-' + label + '.png'))))
        report.append({'variant': label, 'height_scale': scale, 'shader_errors': 0})
    for node, number, state, _attrib in items:
        node.node().setGeomState(number, state)
    (output / 'meadow-variants.json').write_text(json.dumps({
        'scope': '沿海120m实际随车固定时刻，当前/强/中草高与生长场诊断；源模型和候选数不变，非性能Gate',
        'variants': report}, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    import kcd_lighting_diagnostics

    kcd_lighting_diagnostics.inspect_woodland_cover = compare
    check(arguments.output.resolve(), False, (1280, 720), end_distance=120, woodland_variants=True)
