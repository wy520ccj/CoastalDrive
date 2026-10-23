"""普通驾驶暂停/结算的真实控件往返与两画幅采集；成绩为隔离显示夹具。"""

import argparse
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from direct.gui.DirectGuiBase import DirectGuiWidget
from panda3d.core import Filename

from application import CoastalDrive
from race import GameMode, RaceSnapshot
from session import Phase


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    captures, checks, initializations = [], [], []

    def record_start():
        initializations.append({'mode': app.session.mode.value,
            'snapshot_tick_after_start': app.session.current.tick,
            'completed_initialization_ticks': app.session.simulation.initialisation_ticks})

    def key(name):
        app.key_down(name)
        app.key_up(name)

    def draw():
        app.main_menu.resize(app.getAspectRatio())
        app.driving_cards.resize(app.getAspectRatio())
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()

    def shot(name):
        app.refresh_panel()
        before = asdict(app.session.current)
        draw()
        assert asdict(app.session.current) == before
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        captures.append(name+'.png')
        if app.driving_cards.garage_page not in ('pause', 'result'):
            return
        view = app.workshop_vehicle
        content = app.driving_cards.content
        for index in app.driving_cards.summary_order:
            button = app.buttons[index]
            left, right, bottom, top = button['frameSize']
            scale = button['text_scale'][0]
            assert button.component('text0').textNode.calcWidth(button['text'])*scale < right-left
            x, z = button.getX(), button.getZ()
            a, b, c, d = view.frame['frameSize']
            assert min(b, x+right) <= max(a, x+left) or min(d, z+top) <= max(c, z+bottom)
        for label in app.driving_cards.summary_values.get('sectors', ()):
            low, high = label.getTightBounds(content)
            assert high.z < view.frame['frameSize'][2] and low.z > 1-860*2/941
        checks.append({'page': name, 'display_windows': app.graphicsEngine.getNumWindows(),
                       'gui_widgets': len(DirectGuiWidget.guiDict), 'tick': app.session.current.tick})

    def refresh():
        app._shown_phase = None
        app.refresh_panel()

    try:
        app.back_to_menu()
        refresh()
        app.main_menu.select(0)
        app.main_menu.activate()
        record_start()
        assert app.session.phase == Phase.COUNTDOWN and app.session.mode == GameMode.TIME_TRIAL
        # 跳过等待仅用于静态页面夹具，不推进驾驶，也不作为实际完成成绩。
        app.session.phase = Phase.DRIVING
        refresh()
        frozen, world = app.session.current, app.session.simulation
        key('escape')
        shot('01-pause-time-trial')
        count = app.graphicsEngine.getNumWindows()
        key('arrow_down')
        assert app.panel_selection == 2
        key('enter')
        assert app.audio_settings_page and app.session.phase == Phase.PAUSED
        shot('02-pause-audio')
        key('escape')
        assert app.panel_selection == 2 and app.session.phase == Phase.PAUSED
        shot('03-pause-return-focus')
        key('escape')
        assert app.session.phase == Phase.DRIVING and app.session.simulation is world
        assert app.session.current == frozen and not app.workshop_vehicle.buffer.isActive()
        base = RaceSnapshot(mode=GameMode.TIME_TRIAL, finished=True, elapsed=60, last_lap=60,
            best_lap=60, reference_lap=70, new_best=True, splits=(12, 24, 36, 48, 60),
            reference_splits=(14, 28, 42, 56, 70), ghost_notice='最佳圈幽灵已保存，下次挑战可对照。')
        cases = (
            ('04-result-silver', base),
            ('05-result-gold', replace(base, elapsed=50, last_lap=50, best_lap=50, splits=(10, 20, 30, 40, 50))),
            ('06-result-bronze', replace(base, elapsed=75, last_lap=75, best_lap=60, new_best=False, splits=(15, 30, 45, 60, 75))),
            ('07-result-no-medal', replace(base, elapsed=90, last_lap=90, best_lap=60, new_best=False, splits=(18, 36, 54, 72, 90))),
            ('08-result-invalid', replace(base, invalidated=True, invalid_reason='错过检查点后驶离赛道，本圈成绩无效',
                                          new_best=False, ghost_notice='本圈无效，未更新幽灵。')),
            ('09-result-save-failed', replace(base, best_lap=70, save_error='成绩暂未保存，请检查存储空间或目录权限。',
                                              ghost_notice='成绩未保存，本次幽灵未关联。')),
            ('10-result-ended-early', RaceSnapshot(mode=GameMode.TIME_TRIAL, elapsed=24, best_lap=70)),
        )
        widgets = None
        for name, race in cases:
            app.session.race.snapshot = race
            app.session.phase = Phase.RESULTS
            refresh()
            shot(name)
            current = len(DirectGuiWidget.guiDict)
            widgets = current if widgets is None else widgets
            assert widgets == current
            assert app.graphicsEngine.getNumWindows() == count
            if race.invalidated:
                assert all(label.getText() == '—' for label in app.driving_cards.summary_values['sectors'][2::3])
            if race.save_error:
                assert '新个人最佳' not in app.driving_cards.summary_values['notice'].getText()
        key('arrow_right')
        key('enter')
        assert app.session.phase == Phase.MENU and not app.main_menu.root.isHidden()
        assert app.main_menu.selected == 0
        shot('11-return-home')
        app.main_menu.select(1)
        app.main_menu.activate()
        record_start()
        app.session.phase = Phase.DRIVING
        refresh()
        key('escape')
        shot('12-pause-free-drive')
        assert app.session.phase == Phase.PAUSED
        app.select_panel_option(4)
        key('enter')
        assert app.session.phase == Phase.RESULTS
        shot('13-free-drive-ended')
        app.start_game(mode=GameMode.FREE_DRIVE, track='endless')
        record_start()
        app.session.highway.snapshot = replace(app.session.highway.snapshot,
            finished=True, distance=8731, elapsed=372.38, collisions=4)
        app.session.phase = Phase.RESULTS
        refresh()
        shot('14-endless-free-drive')
        app.start_game(mode=GameMode.DISTANCE_CHALLENGE, track='endless')
        record_start()
        for succeeded in (False, True):
            app.session.highway.snapshot = replace(app.session.highway.snapshot, finished=True, succeeded=succeeded,
                distance=5000 if succeeded else 4321, elapsed=152.3, collisions=0 if succeeded else 1,
                reason='完成 5 公里无碰撞挑战' if succeeded else '车辆复位后本次五公里无碰撞挑战结束，请返回菜单重新开始。')
            app.session.phase = Phase.RESULTS
            refresh()
            shot('16-distance-success' if succeeded else '15-distance-failed')
        app.select_panel_option(1)
        app.buttons[1]['command']()
        refresh()
        assert app.session.phase == Phase.MENU and not app.main_menu.root.isHidden()
        shot('17-home-final')
        report = {'passed': True, 'size': size, 'captures': captures, 'checks': checks,
                  'initializations': initializations,
                  'new_driving_steps': 0, 'scope': '真实原生UI与正常键鼠动作；成绩为隔离夹具；非实际跑圈或人工审美验收'}
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
