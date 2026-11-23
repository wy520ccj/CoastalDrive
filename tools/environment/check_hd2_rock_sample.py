"""在实际沿海120m镜位对照HD2原岩壁，行驶过程仍使用原权威物理。"""

import argparse
import hashlib
import json
from pathlib import Path

from check_driving_composition import check
from hd2_local_rocks import SOURCE, load_rock
from local_coastal_landscape import outside_road
from local_kcd_drive import floor_point
from panda3d.core import Filename, Shader, Vec3


def replace_rocks(app):
    curve = app.session.simulation.stream.curve
    root = app.scene.render
    template = load_rock()
    placed = []
    # 设计32只试左侧主岩群，原小石保留；与既有172m主石同一中心。
    for node in tuple(root.findAllMatches('**/kcd-sandstone-medium')):
        low, high = node.getTightBounds(root)
        if high.z - low.z < 4:
            continue
        point = node.getPos(root)
        distance, lateral = curve.project((point.x, point.y + app.session.current.origin_y))
        if lateral > 0:
            continue
        position = floor_point(curve, lateral, distance, 0)
        if position is None:
            continue
        stone = template.copyTo(root)
        height = 4.2
        scale = height / float(template.getTag('source-height'))
        stone.setScale(scale)
        stone.setH(curve.sample(distance).heading)
        stone.setPos(position - Vec3(0, app.session.current.origin_y, 0)
                     - Vec3(0, 0, float(template.getTag('source-base')) * scale + height * .23))
        if not outside_road(stone, root, Vec3(0, app.session.current.origin_y, 0), curve):
            stone.removeNode()
            continue
        placed.append({'old': node, 'new': stone, 'progress': distance, 'lateral': lateral,
                       'position': list(stone.getPos(root)), 'heading': stone.getH(), 'scale': scale})
        stone.hide()
    if not placed:
        raise ValueError('没有安全且可对照的设计32岩壁位置')
    return placed


def compare(app, output):
    placed = replace_rocks(app)
    snapshot = app.session.current
    for tree in app.scene.render.findAllMatches('**/+FadeLODNode'):
        tree.node().setFadeTime(0.)
    original = placed[0]['new'].getShader()
    fragment = original.getText(Shader.STFragment)
    normals = fragment.replace('hd2_normal(v_view_tbn[2],v_view_position)', 'normalize(v_view_tbn[2])').replace(
        'hd2_normal(v_world_tbn[2],v_world_position)', 'normalize(v_world_tbn[2])')
    output_line = 'o_color = vec4(expressway_haze(color.rgb, v_world_position), color.a);'
    variants = {'hd2-sample': original,
        'no-normal': Shader.make(Shader.SLGLSL, original.getText(Shader.STVertex), normals),
        'albedo-only': Shader.make(Shader.SLGLSL, original.getText(Shader.STVertex),
            fragment.replace(output_line, 'o_color=hd2_color();')),
        'ao-only': Shader.make(Shader.SLGLSL, original.getText(Shader.STVertex),
            fragment.replace(output_line, 'o_color=vec4(vec3(ambient_occlusion),1.);'))}
    assert output_line in fragment
    for label, enabled in (('current', False), ('hd2-sample', True), ('no-normal', True),
                           ('albedo-only', True), ('ao-only', True), ('restored', False)):
        for item in placed:
            (item['old'].hide if enabled else item['old'].show)()
            (item['new'].show if enabled else item['new'].hide)()
            item['new'].setShader(variants.get(label, original), 3)
        for _ in range(12):
            app.graphicsEngine.renderFrame()
        app.graphicsEngine.syncFrame()
        assert app.session.current == snapshot
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output / ('rocks-' + label + '.png'))))
    assert all(not shader.getErrorFlag() for shader in variants.values())
    report = {'scope': '正常权威车辆驶至沿海120m后，同一随车镜位/快照局部岩壁选型；非HD2材质完整复原或性能Gate',
              'source': str(SOURCE), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              'placed': [{key: value for key, value in item.items() if key not in ('old', 'new')} for item in placed],
              'omitted': ['原引擎泥土/风化/地形输入', '原引擎GI/色调映射', '原引擎完整法线投影']}
    (output / 'hd2-sample.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for item in placed:
        item['new'].removeNode()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--full-drive', action='store_true')
    arguments = parser.parse_args()
    check(arguments.output.resolve(), False, (1440, 810), end_distance=450 if arguments.full_drive else 120,
          inspect_at_120=None if arguments.full_drive else compare, hd2_rocks=arguments.full_drive)
