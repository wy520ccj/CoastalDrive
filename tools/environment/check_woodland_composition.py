"""正常山脊随车行驶，记录实际植被与原镜头的投影关系，不移动相机或车辆。"""

import argparse
import json
import multiprocessing
from pathlib import Path

from check_interactive_local_drive import DrivingProbe, check
from panda3d.core import Point2


def record(app):
    root = app.scene.render
    rows = []
    for node in root.findAllMatches('**/+LODNode'):
        if not node.getName().startswith(('kcd-oak-', 'kcd-young-oak-', 'kcd-hawthorn-', 'kcd-fern-')):
            continue
        point = node.getPos(root)
        progress, lateral = app.session.simulation.stream.curve.project(tuple(point))
        image = Point2()
        visible = app.camLens.project(app.camera.getRelativePoint(root, point), image)
        rows.append({'name': node.getName(), 'position': list(point), 'scale': list(node.getScale(root)),
                     'road_s': progress, 'road_d': lateral,
                     'root_in_frame': visible, 'root_ndc': list(image) if visible else None})
    result = {'scope': '正常山脊270m原相机投影；根部是否入画不等于完整树冠可见，计数不是draw-call数',
              'camera': list(app.camera.getPos()), 'fov': list(app.camLens.getFov()),
              'player': list(app.session.current.player.position), 'plants': rows}
    (app.probe_output/'composition.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pstats', action='store_true')
    arguments = parser.parse_args()
    original = DrivingProbe.probe_finish

    def finish(app):
        record(app)
        original(app)

    DrivingProbe.probe_finish = finish
    check(arguments.output.resolve(), False, False, pstats=arguments.pstats, hd2_rocks=True)
