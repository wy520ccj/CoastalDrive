"""复载真实试车记录检查概览；重新运行仅初始化后即关闭，不重跑完整道路。"""

import argparse
import gzip
import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'tools')]

from panda3d.core import Filename, Point3
from PIL import Image
from road_review_check import archived_records

from lab_application import VehicleLab
from road_comparison import RoadResults


def check(output, size, before):
    output.mkdir(parents=True)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    source = ROOT/'docs/evidence/DESIGN-SCHEMES-01/normal/schemes'
    shutil.copytree(source, output/'schemes')
    for path in (output/'schemes').rglob('*.gz'):
        path.with_suffix('').write_bytes(gzip.decompress(path.read_bytes()))
    records = archived_records('normal')
    app = VehicleLab(offscreen=True, output=output/'reports', scheme_root=output/'schemes', render_size=tuple(size))
    app.engine.taskMgr.remove('lab-update')
    panel = app.schemes.virtual_driver
    try:
        app.schemes.show()
        app.schemes.move(1, 1)
        panel.show()
        panel.names = ('原配35k · 归档', '循迹50k · 归档')
        if before:
            panel.scheme_names.setText(f'A：{panel.names[0]}\nB：{panel.names[1]}')
        else:
            panel.set_scheme_names()

        def capture(name):
            app.resize()
            for _ in range(4):
                app.engine.taskMgr.step()
            app.engine.graphicsEngine.syncFrame()
            assert app.engine.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
            if not before:
                for label, parent, box in (('title', panel.root, (-1.52, .25, .60, .72)),
                        ('close', panel.close_button, panel.close_button['frameSize'])):
                    left, right, bottom, top = box
                    lower = app.engine.render2d.getRelativePoint(parent, Point3(left, 0., bottom))
                    upper = app.engine.render2d.getRelativePoint(parent, Point3(right, 0., top))
                    region = (math.floor((lower.x+1)*size[0]/2), math.floor((1-upper.z)*size[1]/2),
                              math.ceil((upper.x+1)*size[0]/2), math.ceil((1-lower.z)*size[1]/2))
                    with Image.open(output/(name+'.png')) as screenshot:
                        assert any(max(pixel) < 130 for pixel in screenshot.crop(region).convert('RGB').get_flattened_data()), label

        current = app.active_record(), app.baseline, app.workspace_vehicle
        panel.comparison = RoadResults(records, 'complete')
        panel.present()
        capture('complete')
        panel.comparison = RoadResults(records[:1], 'cancelled')
        panel.present()
        capture('only-a')
        panel.comparison = RoadResults(records, 'complete')
        panel.present()
        assert panel.save_report()
        panel.start()
        assert panel.comparison is not None and not panel.comparison.done
        assert panel.comparison.run.ticks == 0
        initialization_ticks = panel.comparison.run.simulation.initialisation_ticks
        assert ('报告已保存' in panel.note.getText()) is before
        capture('rerun')
        panel.hide()
        assert panel.comparison.run.closed
        assert (app.active_record(), app.baseline, app.workspace_vehicle) == current
        assert tuple(record.snapshots for record in records) == tuple(record.snapshots for record in archived_records('normal'))
        result = {'passed': True, 'size': size, 'before': before, 'reused_road_ticks': sum(len(record.rows) for record in records),
                  'rerun_driving_ticks': 0, 'scope': '结果来自归档真实35k/50k；新世界只有起步初始化，无新完整道路驾驶',
                  'rerun_initialization_ticks': initialization_ticks,
                  'road_record_hashes': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in (ROOT/'docs/evidence/VIRTUAL-DRIVER-01/normal/report').rglob('*.gz')},
                  'reference_baseline_vehicle_unchanged': True}
        (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'passed': True, 'images': 3}
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    parser.add_argument('--before', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.before)))
