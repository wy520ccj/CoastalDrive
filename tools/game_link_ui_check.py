"""游戏联动页实际短参考/对照与文件导出恢复；无新道路驾驶或成绩。"""

import argparse
import json
import math
import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename, Point3
from PIL import Image

import lab_game_comparison
from lab_application import VehicleLab
from lab_experiment import LabOptions
from lab_records import load_record


def check(output, size):
    output.mkdir(parents=True)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    app = VehicleLab(offscreen=True, output=output/'reports', render_size=tuple(size))
    app.engine.taskMgr.remove('lab-update')
    try:
        app.set_options(LabOptions(speed_kph=15., duration=.025))
        app.start_experiment()
        while not app.run_state.done:
            app.run_state.step()
        panel = app.design_loop
        panel.show()

        def capture(name):
            app.resize()
            for _ in range(6):
                app.engine.taskMgr.step()
            app.engine.graphicsEngine.renderFrame()
            app.engine.graphicsEngine.renderFrame()
            assert app.engine.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
            left, right, bottom, top = panel.close_button['frameSize']
            lower = app.engine.render2d.getRelativePoint(panel.close_button, Point3(left, 0., bottom))
            upper = app.engine.render2d.getRelativePoint(panel.close_button, Point3(right, 0., top))
            box = (math.floor((lower.x+1)*size[0]/2), math.floor((1-upper.z)*size[1]/2),
                   math.ceil((upper.x+1)*size[0]/2), math.ceil((1-lower.z)*size[1]/2))
            with Image.open(output/(name+'.png')) as screenshot:
                pixels = screenshot.crop(box).convert('RGB').get_flattened_data()
                assert any(max(pixel) < 130 for pixel in pixels), '关闭按钮字形须在实际图中可见'

        capture('ready')
        reference, baseline, vehicle = panel.record, app.baseline, app.workspace_vehicle
        panel.start_comparison()
        comparison = panel.comparison
        with patch.object(lab_game_comparison, 'export_record', side_effect=OSError('diagnostic export failure')):
            while panel.comparison is not None:
                panel.update()
        capture('export-failed')
        result = {'passed': False, 'comparison_finished': comparison.done, 'world_closed': comparison.run.closed,
                  'size': size,
                  'scope': '实际短参考/游戏对照，真实导出接口失败；无新道路驾驶或成绩'}
        assert comparison.run.closed and panel.completed_records is not None and panel.report_path is None
        completed = panel.completed_records
        panel.hide()
        panel.show()
        assert panel.completed_records is completed and panel.retry_button['state'] == 'normal'
        capture('reopened-pending-export')
        with patch.object(lab_game_comparison.GameComparison, '__init__', side_effect=AssertionError('不得重新计算')):
            panel.retry_button['command']()
        assert panel.report_path.is_file() and panel.report_button['state'] == 'normal'
        saved = load_record(panel.report_path.parent/'game')
        assert saved.snapshots == completed[1].snapshots and saved.commands == completed[1].commands
        path = panel.report_path
        panel.hide()
        panel.show()
        panel.update()
        assert panel.report_path == path and panel.completed_records is completed
        assert app.active_record() is reference and app.baseline is baseline and app.workspace_vehicle is vehicle
        assert '已导出' in app.notice.getText() and '失败' not in app.notice.getText()
        capture('export-recovered')
        result.update(passed=True, completed_records_preserved=True, exported_without_new_physics=True,
                      reference_and_vehicle_unchanged=True, export=str(path.relative_to(output)))
        (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size), ensure_ascii=False))
