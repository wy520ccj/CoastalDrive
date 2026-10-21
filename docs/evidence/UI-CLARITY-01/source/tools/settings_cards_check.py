"""声音/辅助设置的实际静态画面与正常刷新，不推进道路物理。"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from direct.gui.DirectGuiBase import DirectGuiWidget
from panda3d.core import Filename

from application import CoastalDrive
from session import Phase


def check(output, size, baseline):
    output.mkdir(parents=True)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size), independent_clock=True)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    app.back_to_menu()
    before = app.session.current
    try:
        def capture(name):
            app.main_menu.resize(app.getAspectRatio())
            app.driving_cards.resize(app.getAspectRatio())
            for _ in range(4):
                app.taskMgr.step()
            app.graphicsEngine.syncFrame()
            assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))

        app.choose_audio_settings()
        app.adjust_audio_volume('master', -30)
        app.adjust_audio_volume('effects', -40)
        app.adjust_audio_volume('music', -20)
        capture('audio')
        app.back_from_audio_settings()
        app.choose_driving_mode()
        app.toggle_tcs()
        capture('assists')
        app.back_from_driving_mode()
        widget_count = len(DirectGuiWidget.guiDict)
        app.choose_highway()
        for _ in range(2):
            app._shown_phase = None
            app.refresh_panel()
        app.handle_panel_key('escape')
        widget_growth = len(DirectGuiWidget.guiDict)-widget_count
        if not baseline:
            assert widget_growth == 0
        app.session.phase = Phase.PAUSED
        app.refresh_panel()
        app.choose_audio_settings()
        app.back_from_audio_settings()
        assert app.session.phase == Phase.PAUSED and not app.audio_settings_page
        assert app.session.current == before
        result = {'passed': True, 'size': size, 'baseline': baseline, 'widget_growth': widget_growth,
                  'snapshot_unchanged': True, 'pause_return': True, 'scope': '静态设置，无新道路驾驶/物理'}
        (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.baseline), ensure_ascii=False))
