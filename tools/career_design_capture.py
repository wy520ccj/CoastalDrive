"""生涯统一设计的真实UI采集；隔离成绩夹具，不运行道路物理。"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from career import EVENT_BY_ID, CareerProgress
from career_run import CareerResult
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle


def capture(output, size, only=()):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    vehicle = WorkspaceVehicle('club-coupe', vehicle_design('club-coupe').config)
    app = CoastalDrive(smoke=True, output=output, render_size=size, workspace_vehicle=vehicle)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    app.back_to_menu()
    app._shown_phase = None
    app.refresh_panel()
    names = []
    before = asdict(app.session.current)

    def shot(name):
        if only and name not in only:
            return
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        assert before == asdict(app.session.current)
        names.append(name+'.png')

    try:
        shot('00-home-new')
        app.open_career()
        shot('01-events-new')
        app.key_down('arrow_down')
        app.key_up('arrow_down')
        shot('01-events-parking')
        app.career_action('board-chapter', 2)
        shot('01-events-locked-final')
        for event in ('first-drive', 'slalom', 'parking', 'coastal-cup'):
            app.career_action('brief', event)
            shot('02-brief-'+event)
        result = CareerResult('first-drive', 8., elapsed=16.71, finished=True, succeeded=True, stars=3)
        award = app.career_progress.record(result)
        app.career_panel.show_result(app.career_progress, result, award)
        shot('03-result-unlocks')
        parking = CareerResult('parking', 8., elapsed=21., finished=True, succeeded=True, stars=2)
        award = app.career_progress.record(parking)
        app.career_panel.show_result(app.career_progress, parking, award)
        shot('03-result-five-stars')
        multi = CareerProgress(output/'multi-career.json')
        multi.record(CareerResult('first-drive', 8., elapsed=30., finished=True, succeeded=True, stars=2))
        three = CareerResult('parking', 8., elapsed=21., finished=True, succeeded=True, stars=3)
        app.career_panel.show_result(multi, three, multi.record(three))
        shot('03-result-multiple-unlocks')
        app.open_career()
        shot('04-events-progress')
        if '00-home-progress' in only:
            app.career_action('exit')
            shot('00-home-progress')
            app.open_career()
        panel = app.career_panel
        panel.select(next(i for i, item in enumerate(panel.buttons) if item['extraArgs'] == ['brief', 'parking']))
        shot('04-events-focus')
        app.career_panel.show_result(app.career_progress, result, app.career_progress.record(result))
        shot('05-result-repeat')
        failure = CareerResult('slalom', 8., elapsed=24.82, finished=True, succeeded=False, stars=0,
                               reason='车辆驶离赛道，请提前看向下一道门。')
        app.career_panel.show_result(app.career_progress, failure, app.career_progress.record(failure))
        shot('06-result-failed')
        app.career_progress.notice = '生涯进度未保存：测试文件访问失败。'
        app.career_panel.show_result(app.career_progress, result,
                                    {'credits': 0, 'vehicles': (), 'unlocked': (), 'saved': False})
        shot('07-save-retry')
        app.career_progress.notice = ''
        app.career_panel.show_pause(app.career_progress, EVENT_BY_ID['slalom'])
        shot('08-pause')
        report = {'passed': True, 'size': size, 'captures': names, 'new_driving_steps': 0,
                  'scope': '真实DirectGUI/当前车辆；成绩和解锁为隔离夹具，非新驾驶或人工验收'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--only', nargs='+', default=())
    args = parser.parse_args()
    capture(args.output.resolve(), tuple(args.size), args.only)
