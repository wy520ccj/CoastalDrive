"""真实购买/恢复/免费重装/试车简报与两画幅采集，进度为隔离夹具。"""

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
from career import EVENTS, PARTS
from ui.garage_layout import TRIAL_EVENTS


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    captures, readouts = [], []
    snapshot = asdict(app.session.current)

    def capture(name):
        panel = app.career_panel
        for _ in range(8):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert asdict(app.session.current) == snapshot
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        captures.append(name+'.png')
        if panel.page != 'garage':
            return
        for widget in panel.garage_values.values():
            low, high = widget.getTightBounds(panel.content)
            primary = panel.buttons[panel.primary]
            button_top = primary.getZ()+primary['frameSize'][3]
            assert low.z > button_top
            assert high.x < app.workshop_vehicle.frame['frameSize'][0]
        readouts.append({'capture': name, 'topic': panel.garage_topic,
            'current': panel.garage_values['current'].getText(),
            'target': panel.garage_values['target'].getText(),
            'action': panel.buttons[panel.primary]['extraArgs'], 'credits': app.career_progress.credits})

    try:
        # 星级仅作明示显示夹具，一次保存并核对结果，不把快速领奖写入当实际比赛。
        fixture_credits = sum(event.reward*3 for event in EVENTS)
        fixture_records = {event.id: {'stars': 3, 'seconds': 25.} for event in EVENTS}
        assert app.career_progress.save(fixture_records, set(), fixture_credits), app.career_progress.notice
        assert app.career_progress.stars == 18
        app.open_career_collection()
        app.career_action('garage-car', 'game-tuned')
        app.career_action('garage-select')
        app.career_action('garage-tab', 'upgrade')
        original = app.workspace_vehicle
        expected_credits = app.career_progress.credits
        panel = app.career_panel
        for part in PARTS:
            app.career_action('garage-topic', part.topic)
            capture(part.topic+'-before')
            panel.key('enter')
            expected_credits -= part.price
            assert app.career_progress.credits == expected_credits
            capture(part.topic+'-installed')
            panel.key('enter')
            assert panel.page == 'brief' and panel.event_id == TRIAL_EVENTS[part.topic]
            assert not app.workshop_vehicle.buffer.isActive()
            capture(part.topic+'-trial')
            app.career_action('garage')
        for _ in PARTS:
            app.career_action('restore')
        assert app.workspace_vehicle == original
        app.career_action('garage-topic', 'tires')
        capture('owned-free-reinstall')
        assert panel.buttons[panel.primary]['text'] == '安装已购零件'
        panel.key('enter')
        assert app.career_progress.credits == expected_credits
        app.career_action('garage-tab', 'cars')
        app.career_action('garage-car', 'gr86-2022-premium-6mt')
        app.career_action('garage-select')
        app.career_action('garage-tab', 'upgrade')
        app.career_action('garage-topic', 'brakes')
        assert panel.garage_values['target'].getText() == '当前已是该设定'
        capture('gr86-stock-brakes')
        panel.key('enter')
        assert panel.page == 'brief' and panel.event_id == 'parking'
        capture('gr86-stock-trial')
        assert app.career_progress.credits == expected_credits
        report = {'passed': True, 'size': size, 'captures': captures, 'readouts': readouts,
            'fixture_stars': app.career_progress.stars, 'initial_credits': fixture_credits,
            'credits_after_purchases': expected_credits, 'new_driving_steps': 0,
            'scope': '18星为隔离夹具；正常原生购买与导航，不代表完整比赛或人工审美'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    args = parser.parse_args()
    check(args.output.resolve(), tuple(args.size))
