"""真实输入逐拍留证，自动试车不冒充真人，结果截取同一条原始记录。"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from challenge_build import BuildDraft
from challenge_calibration import replay_fuel
from challenge_catalog import SPRINT_CHALLENGES
from challenge_trace import TRACE_COLUMNS
from controls import ConstantController
from race import BestTimes, GameMode
from session import Session
from vehicle_state import Control


def test_short_actual_attempt_exports_contiguous_raw_commands_fuel_and_full_conditions(tmp_path):
    mode = GameMode.BEND_SPRINT
    app = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    try:
        app.start(mode=mode, track='endless', countdown=False, challenge_spec=SPRINT_CHALLENGES[mode],
                  build=BuildDraft(power=1.1))
        app.set_controller(ConstantController(Control(throttle=.3, steering=.1)))
        for _ in range(24):
            app.tick()
        app.finish()
        path = app.engineering.trace.path
        data = json.loads(path.read_text(encoding='utf-8'))
        assert data['columns'] == list(TRACE_COLUMNS)
        assert len(data['samples']) == 25 and data['build']['power'] == 1.1
        assert data['source_start'] == data['source_end']
        assert data['version'] == 2 and len(data['fuel_steps']) == len(data['samples'])
        replayed = replay_fuel(app.challenge_spec, data)
        assert replayed.litres == data['samples'][-1][3]
        assert replayed.rate_lph == data['samples'][-1][4]
        assert data['controller'] == 'controls.ConstantController'
        assert not data['result']['official'] and not data['result']['medal']
        for index, row in enumerate(data['samples']):
            assert row[0] == data['initial_tick']+index
            assert row[1] == pytest.approx(index/120, abs=1e-10)
            if index:
                assert row[10:12] == [.3, 0.]
                assert row[3] >= data['samples'][index-1][3]
        assert data['result']['litres'] == pytest.approx(data['samples'][-1][3]-data['start_litres'])
        count = len(tuple(path.parent.glob('*.json')))
        app.finish()
        assert len(tuple(path.parent.glob('*.json'))) == count
    finally:
        app.close()


def test_discontinuous_sample_rejected_instead_of_interpolating_missing_raw_physics(tmp_path):
    mode = GameMode.BEND_SPRINT
    app = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    try:
        app.start(mode=mode, track='endless', countdown=False, challenge_spec=SPRINT_CHALLENGES[mode])
        trace = app.engineering.trace
        with pytest.raises(ValueError, match='连续'):
            trace.append(replace(app.current, tick=app.current.tick+2), Control(), 0.)
    finally:
        app.close()


def test_automatic_controller_attached_during_countdown_never_becomes_human_trace(tmp_path):
    mode = GameMode.BEND_SPRINT
    app = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    try:
        app.start(mode=mode, track='endless', challenge_spec=SPRINT_CHALLENGES[mode])
        app.set_controller(ConstantController(Control(throttle=.3)))
        app.countdown_step(360)
        assert not app.engineering.player_driven and app.engineering.scores is None
        assert app.engineering.trace.controller == 'controls.ConstantController'
        app.tick()
        app.finish()
        assert not app.engineering.result.official
    finally:
        app.close()


@pytest.mark.parametrize('exit_action', ['menu', 'restart', 'close'])
def test_abandoned_attempt_is_saved_once_with_original_raw_steps(tmp_path, exit_action):
    mode = GameMode.BEND_SPRINT
    app = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    closed = False
    try:
        app.start(mode=mode, track='endless', countdown=False, challenge_spec=SPRINT_CHALLENGES[mode])
        for _ in range(3):
            app.tick()
        trace = app.engineering.trace
        if exit_action == 'restart':
            app.start(mode=mode, track='endless', countdown=False)
        else:
            getattr(app, exit_action)()
            closed = exit_action == 'close'
        data = json.loads(trace.path.read_text(encoding='utf-8'))
        assert len(data['samples']) == 4 and not data['result']['valid']
        assert not data['result']['medal']
    finally:
        if not closed:
            app.close()


def test_failed_trace_export_freezes_original_rows_and_can_retry_without_losing_or_duplicating(tmp_path, monkeypatch):
    mode = GameMode.BEND_SPRINT
    app = Session(track='test', scores=BestTimes(tmp_path/'best.json'))
    try:
        app.start(mode=mode, track='endless', countdown=False, challenge_spec=SPRINT_CHALLENGES[mode])
        app.tick()
        trace = app.engineering.trace

        def fail(self, target):
            raise OSError('测试写入失败')

        with monkeypatch.context() as patch:
            patch.setattr(Path, 'replace', fail)
            app.finish()
            assert trace.closed and trace.path is None and '未保存' in trace.notice
        frozen = tuple(trace.rows)
        app.finish()
        assert trace.path.exists() and trace.notice == '' and app.engineering.save_notice == ''
        assert tuple(trace.rows) == frozen
        assert len(tuple(trace.folder.glob('*.json'))) == 1
    finally:
        app.close()
