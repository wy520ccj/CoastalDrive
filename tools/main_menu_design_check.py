"""首页与车库/设置的正常往返；隔离用户目录，只采集界面，不推进驾驶。"""

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


def check(output, size, only=()):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    captures = []

    def key(value):
        app.key_down(value)
        app.key_up(value)

    def shot(name):
        app.main_menu.resize(app.getAspectRatio())
        app.career_panel.resize(app.getAspectRatio())
        before = asdict(app.session.current)
        for _ in range(8):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert before == asdict(app.session.current)
        if only and name not in only:
            return
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        captures.append(name+'.png')

    try:
        app.back_to_menu()
        app._shown_phase = None
        app.refresh_panel()
        shot('01-home')
        snapshot = asdict(app.session.current)
        menu, view = app.main_menu, app.workshop_vehicle
        count = app.graphicsEngine.getNumWindows()
        assert menu.selected == 2 and view.frame.getParent() == menu.home
        # 左列所有控件与车辆展示区互不覆盖，文字必须落在各自命中区域内。
        for index in (2, 3, 1, 0, 6):
            button = menu.buttons[index]
            left, right, bottom, top = button['frameSize']
            width = button.component('text0').textNode.calcWidth(button['text'])*button['text_scale'][0]
            assert button['text_pos'][0] > left and button['text_pos'][0]+width < right
            assert button.getX()+right < menu.car_box[0]
            low, high = menu.subtitles[index].getTightBounds(button)
            assert low.x > left and high.x < right and low.z > bottom and high.z < top, (index, low, high, button['frameSize'])
        for cycle in range(2):
            key('arrow_down')
            assert menu.selected == 3
            shot('02-garage-focus' if len(captures) == 1 else '07-garage-focus-return')
            key('enter')
            assert app.career_panel.page == 'garage' and not app.career_panel.root.isHidden()
            assert view.frame.getParent() == app.career_panel.content
            shot(f'03-garage-{cycle}')
            app.career_action('garage-tab', 'upgrade')
            shot(f'04-upgrades-{cycle}')
            app.career_action('garage-tab', 'paint')
            shot(f'05-paint-{cycle}')
            key('escape')
            assert app.career_panel.root.isHidden() and menu.selected == 3
            assert view.frame.getParent() == menu.home and view.buffer.isActive()
            shot(f'06-home-return-{cycle}')
            menu.select(2)
        assert app.graphicsEngine.getNumWindows() == count
        menu.select(6)
        key('arrow_down')
        assert menu.selected == 7
        key('arrow_right')
        assert menu.selected == 4
        shot('08-footer-focus')
        key('enter')
        assert app.audio_settings_page and view.buffer.isActive()
        assert view.frame.getParent() == app.driving_cards.content
        shot('09-audio')
        key('escape')
        assert menu.selected == 4 and not app.audio_settings_page and view.buffer.isActive()
        key('arrow_left')
        assert menu.selected == 7
        key('enter')
        assert app.driving_mode_page and view.buffer.isActive()
        assert view.frame.getParent() == app.driving_cards.content
        shot('10-assists')
        key('escape')
        assert menu.selected == 7 and not app.driving_mode_page
        key('arrow_up')
        assert menu.selected == 6
        menu.select(2)
        key('enter')
        assert app.career_panel.page == 'board' and not view.buffer.isActive()
        shot('11-events')
        key('escape')
        assert app.career_panel.root.isHidden() and menu.selected == 2
        assert snapshot == asdict(app.session.current)
        shot('12-home-final')
        assert app.graphicsEngine.getNumWindows() == count
        report = {'passed': True, 'size': size, 'captures': captures, 'new_driving_steps': 0,
                  'initial_snapshot_tick': snapshot['tick'],
                  'snapshot_unchanged': True, 'display_windows_unchanged': count,
                  'scope': '真实原生菜单与键盘往返；隔离空进度，0新驾驶拍，非人工审美验收'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--only', nargs='+', default=())
    args = parser.parse_args()
    check(args.output.resolve(), tuple(args.size), args.only)
