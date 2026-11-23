"""固定实际随车画面比较草顶点早退，保留原判定与可见草。"""

import argparse
import json
from pathlib import Path

import numpy as np
from check_driving_composition import check
from local_kcd_drive import grass_shader
from panda3d.core import Filename, ShaderAttrib


def compare(app, output):
    nodes = list(app.scene.render.findAllMatches('**/kcd-stream-grass'))
    ordered_nodes = list(app.scene.render.findAllMatches('**/+GeomNode'))
    node_states = [node.getState() for node in ordered_nodes]
    # shader切换会改变默认状态排序；冻结完整场景，避免把相交叶卡的遮挡次序误当草顶点差异。
    for number, node in enumerate(ordered_nodes):
        node.setBin('fixed', number, 100)
    items = [(node, number, node.node().getGeomState(number),
              node.getNetState().compose(node.node().getGeomState(number)).getAttrib(ShaderAttrib))
             for node in nodes for number in range(node.node().getNumGeoms())]
    shaders = {enabled: grass_shader(app.scene.expressway_kit['foliage-shader'], cull_absent=enabled)
               for enabled in (False, True)}
    frames, rows = [], []
    for tree in app.scene.render.findAllMatches('**/+FadeLODNode'):
        tree.node().setFadeTime(0.)
    for label, enabled in (('legacy', False), ('early', True), ('legacy-repeat', False), ('early-repeat', True)):
        for node, number, state, attrib in items:
            node.node().setGeomState(number, state.setAttrib(attrib.setShader(shaders[enabled], 2), 2))
        for _ in range(12):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        assert not shaders[enabled].getErrorFlag(), label
        picture = app.win.getScreenshot()
        picture.write(Filename.fromOsSpecific(str(output / ('grass-vertex-' + label + '.png'))))
        frames.append(np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy())
        rows.append({'mode': label, 'early_return': enabled})
    differences = []
    for first, second in ((0, 1), (0, 2), (1, 3)):
        delta = np.abs(frames[first].astype(np.int16)-frames[second])
        differences.append({'pair': [rows[first]['mode'], rows[second]['mode']],
                            'max_rgb8': int(delta.max()), 'changed_channels': int(np.count_nonzero(delta))})
    # 完整画面可能在相交叶面/车漆上有重复采样差；保留原值，另对原镜头完整草层做严格比较。
    unrelated = [node for node in ordered_nodes if node.getName() != 'kcd-stream-grass']
    for node in unrelated:
        node.stash()
    background = app.getBackgroundColor()
    app.setBackgroundColor(0, 0, 0)
    app.aspect2d.hide()
    grass_frames = []
    for label, enabled in (('legacy', False), ('early', True), ('legacy-repeat', False), ('early-repeat', True)):
        for node, number, state, attrib in items:
            node.node().setGeomState(number, state.setAttrib(attrib.setShader(shaders[enabled], 2), 2))
        for _ in range(12):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        picture = app.win.getScreenshot()
        picture.write(Filename.fromOsSpecific(str(output/('grass-layer-'+label+'.png'))))
        grass_frames.append(np.frombuffer(picture.getRamImageAs('RGB'), dtype=np.uint8).copy())
    grass_differences = []
    for first, second in ((0, 1), (0, 2), (1, 3)):
        delta = np.abs(grass_frames[first].astype(np.int16)-grass_frames[second])
        grass_differences.append({'pair': [rows[first]['mode'], rows[second]['mode']],
            'max_rgb8': int(delta.max()), 'changed_channels': int(np.count_nonzero(delta))})
    for node in unrelated:
        node.unstash()
    app.setBackgroundColor(background)
    app.aspect2d.show()
    for node, number, state, _attrib in items:
        node.node().setGeomState(number, state)
    for node, state in zip(ordered_nodes, node_states, strict=True):
        node.setState(state)
    report = {'scope': '沿海120m原随车镜位；原状态全场像素差保留，严格0差仅检查同一实际完整草层。诊断固定顺序/隔离其他物体，不接产品，不宣称全场恒等',
              'grass_geom_entries': len(items), 'pixel_differences': differences,
              'grass_layer_pixel_differences': grass_differences}
    (output / 'grass-vertex-cull.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    assert all(row['max_rgb8'] == 0 for row in grass_differences), report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    check(arguments.output.resolve(), False, (1280, 720), end_distance=120, inspect_at_120=compare)
