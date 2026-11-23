"""首页无限高速真实入口与键鼠往返。"""

import pytest

from application import CoastalDrive
from challenge_build import BuildDraft
from challenge_catalog import distance_challenge_spec
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


def test_budget_distance_uses_highway_menu_conditions_on_start_and_retry(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    app = CoastalDrive(smoke=True, output=tmp_path/'game')
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    try:
        app.back_to_menu()
        app.highway_shape = 'straight'
        app.highway_density_index = app.highway_density_keys.index('normal')
        app.choose_highway()
        app.buttons[3]['command']()
        panel = app.career_panel
        choices = [button for button in panel.buttons if button['extraArgs'][0] == 'challenge-preset']
        assert [button['text'] for button in choices] == ['低风阻 · 1780', '轻量低阻 · 4780', '原车方案 · 0']
        choices[0]['command'](*choices[0]['extraArgs'])
        assert panel.challenge_readouts['preset-title'].getText() == '参考方案 · 实跑 189.0 s / 9.96 L/100km'
        app.challenge_action('challenge-auto')
        assert app.session.challenge_build == BuildDraft(drag=.95)
        assert app.session.simulation.road_shape == 'straight' and len(app.session.current.traffic) == 12
        app.challenge_action('challenge-back')
        app.cycle_highway_shape()
        app.cycle_highway_density()
        app.buttons[3]['command']()
        assert app.career_panel.page == 'challenge'
        assert not any(button['extraArgs'][0] == 'challenge-preset' for button in panel.buttons)
        assert 'preset-title' not in panel.challenge_readouts
        app.challenge_action('challenge-reset')
        labels = [label.getText() for label in app.career_panel.labels]
        expected = distance_challenge_spec('hills', 'busy')
        gold = expected.targets[-1]
        assert '弯坡高速 · 繁忙' in labels and f'≤ {gold.seconds:.1f}' in labels
        assert app.career_panel.challenge_readouts['start']['text'] == '开始挑战'
        app.challenge_action('challenge-tab', 1)
        assert app.career_panel.challenge_data[0] == expected
        app.challenge_action('challenge-start')
        while app.session.phase == Phase.COUNTDOWN:
            app.session.countdown_step(360)
        assert app.session.mode == GameMode.DISTANCE_CHALLENGE and app.session.simulation.road_shape == 'hills'
        assert len(app.session.current.traffic) == 18
        highway = app.session.highway.snapshot
        assert highway.engineering.targets == expected.targets
        app.hud.update(app.session.current, app.session.race.snapshot, highway,
                       track='endless', countdown='', notice='')
        assert '分段 0 / 4' in app.hud.coastal.checkpoints.getText()
        assert f'≤{gold.seconds:.1f}s' in app.hud.coastal.cumulative.getText()
        app.session.finish()
        app._shown_phase = None
        app.refresh_panel()
        assert '路段' in [label.getText() for label in app.career_panel.labels]
        assert app.career_panel.challenge_result_data[0] == expected
        app.challenge_action('challenge-retry')
        assert app.session.simulation.road_shape == 'hills' and len(app.session.current.traffic) == 18
        assert app.session.challenge_spec == expected
        app.challenge_action('challenge-back')
        assert '弯坡高速 · 繁忙' in app.panel_note.getText()

        app.start_highway('hills', mode=GameMode.DISTANCE_CHALLENGE)
        panel = app.career_panel
        automatic = next(button for button in panel.buttons if button['extraArgs'][0] == 'challenge-auto')
        automatic['command'](*automatic['extraArgs'])
        busy = app._automatic_trial_group()
        while app.session.phase == Phase.COUNTDOWN:
            app.session.countdown_step(360)
        for _ in range(18):
            app.session.tick()
        assert app.budget_auto and len(app.session.current.traffic) == 18 and app.session.last_control.throttle > 0.
        app.challenge_action('challenge-back')
        app.highway_density_index = app.highway_density_keys.index('light')
        app.start_highway('hills', mode=GameMode.DISTANCE_CHALLENGE)
        app.challenge_action('challenge-auto')
        assert app._automatic_trial_group() != busy
        assert app.session.seed == 0 and app.session.challenge_spec == distance_challenge_spec('hills', 'light')
    finally:
        app.close_game()
