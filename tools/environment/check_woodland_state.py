"""固定真实随车镜位，核对林地输入缩小继承范围后的GPU像素与树木材质状态。"""

import argparse
import json
from pathlib import Path

import numpy as np
from check_driving_composition import check
from local_kcd_drive import apply_woodland_inputs
from panda3d.core import Filename, ShaderAttrib


def compare(app, output):
    roots = list(app.scene.segment_nodes.values())
    for tree in app.scene.render.findAllMatches('**/+FadeLODNode'):
        tree.node().setFadeTime(0.)
    nodes = list(app.scene.render.findAllMatches('**/+GeomNode'))
    images, rows, references = [], [], []
    verified_consumers, verified_unused = 0, 0
    names = ('local_forest_coverage', 'local_forest_bounds')
    for label in ('root', 'scoped', 'root-repeat', 'scoped-repeat'):
        for root in roots:
            texture, bounds = root.getPythonTag('woodland-coverage')
            if label.startswith('root'):
                for node in root.findAllMatches('**/+GeomNode'):
                    node.clearShaderInput(names[0])
                    node.clearShaderInput(names[1])
                root.setShaderInput(names[0], texture)
                root.setShaderInput(names[1], bounds)
            else:
                root.clearShaderInput(names[0])
                root.clearShaderInput(names[1])
                apply_woodland_inputs(root, texture, bounds)
        states, count, number = set(), 0, 0
        for node in nodes:
            for geom_index in range(node.node().getNumGeoms()):
                geom = node.node().getGeom(geom_index)
                state = node.getNetState().compose(node.node().getGeomState(geom_index))
                attrib = state.getAttrib(ShaderAttrib)
                if label == 'root':
                    references.append((geom, state, attrib))
                elif label == 'scoped':
                    old_geom, old_state, old_attrib = references[number]
                    assert geom == old_geom, node
                    assert state.removeAttrib(ShaderAttrib) == old_state.removeAttrib(ShaderAttrib), node
                    assert attrib.clearShaderInput(names[0]).clearShaderInput(names[1]) == (
                        old_attrib.clearShaderInput(names[0]).clearShaderInput(names[1])), node
                    shader = attrib.getShader()
                    # 固定功能/自动着色器不读取这两个自定义uniform。
                    text = '' if shader is None else shader.getText(shader.STVertex) + shader.getText(shader.STFragment)
                    if names[0] in text or names[1] in text:
                        assert attrib.getShaderInput(names[0]).getTexture() == old_attrib.getShaderInput(names[0]).getTexture(), node
                        assert tuple(attrib.getShaderInput(names[1]).getVector()) == tuple(old_attrib.getShaderInput(names[1]).getVector()), node
                        verified_consumers += 1
                    else:
                        verified_unused += 1
                number += 1
                if node.getName().startswith(('kcd-oak-', 'kcd-young-oak-', 'kcd-hawthorn-')):
                    states.add(attrib)
                    count += 1
        # 不运行任务或推进时钟/物理；默认状态排序造成的像素变化单独记录。
        for _ in range(12):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        picture = app.win.getScreenshot()
        picture.write(Filename.fromOsSpecific(str(output / ('woodland-state-' + label + '.png'))))
        images.append(np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy())
        rows.append({'mode': label, 'tree_geom_states': count, 'unique_tree_shader_attribs': len(states)})
    differences = []
    for first, second in ((0, 1), (0, 2), (1, 3)):
        difference = np.abs(images[first].astype(np.int16) - images[second])
        differences.append({'pair': [rows[first]['mode'], rows[second]['mode']],
                            'max_rgb8': int(difference.max()), 'changed_channels': int(np.count_nonzero(difference))})
    result = {'scope': '真实沿海120m随车完整场景；逐Geom核对着色器实际读取的输入与其余状态相同；默认排序像素差原样记录，非整帧绝对相等保证或性能Gate',
              'states': rows, 'pixel_differences': differences,
              'identical_consumed_inputs': verified_consumers, 'shaders_without_woodland_uniforms': verified_unused,
              'same_geometry_and_other_render_state': len(references)}
    (output / 'woodland-state.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    assert verified_consumers > 0 and verified_unused > 0
    assert rows[1]['unique_tree_shader_attribs'] < rows[0]['unique_tree_shader_attribs'], rows



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    import kcd_lighting_diagnostics

    kcd_lighting_diagnostics.inspect_woodland_cover = compare
    check(arguments.output.resolve(), False, (1280, 720), end_distance=120, woodland_variants=True)
