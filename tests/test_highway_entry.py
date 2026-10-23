"""首页无限高速真实入口与键鼠往返。"""

import pytest

from application import CoastalDrive
from race import GameMode
from session import Phase


@pytest.mark.parametrize('size', [(1280, 720), (1024, 768)])
def test_home_highway_entry_and_actual_streamed_drive(tmp_path, size):
    app = CoastalDrive(smoke=True, output=tmp_path, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        app.back_to_menu()
        menu = app.main_menu
        assert menu.buttons[8]['text'] == '无限高速'
        menu.select(1)
        menu.move(1)
        assert menu.selected == 8
        menu.activate()
        assert app.highway_menu and app.panel_title.getText() == '无限高速'
        assert '自由驾驶' in app.buttons[2]['text'] and '5公里' in app.buttons[3]['text']
        app.back_to_modes()
        menu.buttons[8]['command']()
        assert app.highway_menu
        app.highway_density_index = 0
        app.session.traffic_density = 'light'
        app.buttons[2]['command']()
        while app.session.phase == Phase.COUNTDOWN:
            app.session.tick()
        assert app.session.mode is GameMode.FREE_DRIVE
        assert app.session.simulation.track == 'endless' and app.session.simulation.stream is not None
        tick = app.session.current.tick
        app.session.keyboard.press('w')
        for _ in range(120):
            app.session.tick()
        assert app.session.current.tick == tick+120
        app.session.keyboard.clear()
        app.back_to_menu()
        app.refresh_panel()
        assert not menu.root.isHidden() and menu.buttons[8]['text'] == '无限高速'
    finally:
        app.close_game()
