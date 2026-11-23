"""驾驶数值失败须中止并保留方案，不能退出窗口或获得成绩。"""

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from application import CoastalDrive
from challenge_build import BuildDraft
from race import GameMode
from session import Phase


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, output=tmp_path/'game')
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    yield game
    game.close_game()


def fail_frame(*args, **kwargs):
    raise ZeroDivisionError('回归注入的驾驶数值失败')


class NumericalFailureController:
    def sample(self, state, dt):
        raise ZeroDivisionError('回归注入的独立物理数值失败')


def test_failed_budget_frame_returns_to_same_build_without_award_and_can_retry(app, monkeypatch):
    mode = GameMode.BEND_SPRINT
    app.start_sprint(mode)
    original = app.session.vehicle_config
    app.challenge_action('challenge-value', ('power', '110'))
    app.challenge_action('challenge-start')
    while app.session.phase == Phase.COUNTDOWN:
        app.session.countdown_step(360)
    app.session.tick()
    stars = app.career_progress.stars
    with monkeypatch.context() as patch:
        patch.setattr(app.session, 'frame', fail_frame)
        assert app.update(SimpleNamespace(cont='continue')) == 'continue'
    assert app.session.phase == Phase.MENU
    assert app.session.vehicle_config == original
    assert app.budget_mode == mode and app.budget_origin == 'sprint'
    assert app.budget_drafts[mode] == BuildDraft(power=1.1)
    assert app.career_panel.page == 'challenge'
    assert '本次已中止' in app.career_panel.challenge_readouts['notice'].getText()
    assert app.career_progress.stars == stars
    assert not app.session.race.scores.path.with_name('challenge-best.json').exists()
    trace = next((app.session.race.scores.path.parent/'challenge-runs').glob('*.json'))
    assert not json.loads(trace.read_text(encoding='utf-8'))['result']['official']
    error = next((app.output/'drive-errors').glob('*.log')).read_text(encoding='utf-8')
    assert 'ZeroDivisionError' in error and '回归注入的驾驶数值失败' in error
    app.challenge_action('challenge-start')
    assert app.session.phase == Phase.COUNTDOWN and not app.driving_error
    assert app.session.vehicle_config == app.session.challenge_spec.configuration(BuildDraft(power=1.1))


def test_failed_free_drive_keeps_menu_usable_when_error_file_cannot_be_saved(app, monkeypatch):
    app.start_game(mode=GameMode.FREE_DRIVE, track='test')
    write = Path.write_text

    def deny_error_file(path, *args, **kwargs):
        if path.parent.name == 'drive-errors':
            raise OSError('回归注入的文件写入失败')
        return write(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(app.session, 'frame', fail_frame)
        patch.setattr(Path, 'write_text', deny_error_file)
        assert app.update(SimpleNamespace(cont='continue')) == 'continue'
    assert app.session.phase == Phase.MENU
    assert not app.main_menu.root.isHidden()
    assert '错误记录未能保存' in app.main_menu.notice.getText()


def test_real_failed_process_returns_to_editor_and_reuses_same_authority(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'user'))
    game = CoastalDrive(smoke=True, output=tmp_path/'game', independent_clock=True)
    game.taskMgr.remove('finish-smoke')
    game.taskMgr.remove('drive-update')
    try:
        mode = GameMode.BEND_SPRINT
        game.start_sprint(mode)
        game.challenge_action('challenge-value', ('power', '110'))
        game.challenge_action('challenge-start')
        authority = game.session
        pid = authority.process.pid
        authority.start(mode=mode, track='endless', countdown=False)
        authority.set_controller(NumericalFailureController())
        deadline = time.monotonic()+5
        while authority.phase != Phase.MENU and time.monotonic() < deadline:
            game.update(SimpleNamespace(cont='continue'))
            time.sleep(.005)
        assert authority.phase == Phase.MENU
        assert game.session is authority and authority.process.pid == pid and authority.process.is_alive()
        assert not authority.pending_frame
        assert game.career_panel.page == 'challenge'
        assert game.budget_drafts[mode] == BuildDraft(power=1.1)
        error = next((game.output/'drive-errors').glob('*.log')).read_text(encoding='utf-8')
        assert '独立物理数值失败' in error
        authority.set_controller(authority.keyboard)
        game.challenge_action('challenge-start')
        assert authority.phase == Phase.COUNTDOWN
    finally:
        game.close_game()
