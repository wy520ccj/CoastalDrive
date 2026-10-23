"""真实HUD/结算控件与完整会话状态传输，不把规则夹具当人工跑圈。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from race import GameMode, RaceSnapshot
from session import Phase, Session
from session_process import _decode_frame, _encode_frame, _output


def feedback_state(**changes):
    return replace(RaceSnapshot(mode=GameMode.TIME_TRIAL, elapsed=19., checkpoints=2,
                                next_checkpoint=3, splits=(11., 19.),
                                reference_splits=(10., 20., 30., 40., 50.), reference_lap=50., best_lap=50.),
                   **changes)


@pytest.fixture
def app(tmp_path):
    game = CoastalDrive(smoke=True, output=tmp_path, render_size=(1024, 768))
    game.taskMgr.remove("finish-smoke")
    yield game
    game.close_game()


def test_hud_shows_sector_and_total_deltas_within_card_and_hides_for_cruise(app):
    race = feedback_state()
    app.hud.update(app.session.current, race, app.session.highway.snapshot,
                   track="coastal", countdown="", notice="")
    assert "Δ -2.000" in app.hud.split.getText()
    assert "累计差 -1.000" in app.hud.split.getText()
    bounds = app.hud.split.getTightBounds(app.hud.status_frame)
    assert bounds[0].z > -.54 and bounds[1].x < .84
    app.hud.update(app.session.current, replace(race, mode=GameMode.FREE_DRIVE), app.session.highway.snapshot,
                   track="coastal", countdown="", notice="")
    assert app.hud.split.isHidden() and app.hud.status_frame["frameSize"][2] == -.40


@pytest.mark.parametrize("invalid", [False, True])
def test_result_table_stays_clear_of_total_and_buttons_even_with_warning(app, invalid):
    state = feedback_state(finished=True, running=False, elapsed=49., last_lap=49.,
                           best_lap=49. if not invalid else 50., splits=(11., 19., 29., 39., 49.),
                           new_best=not invalid, invalidated=invalid, invalid_reason="车辆复位" if invalid else "",
                           save_error="成绩暂未保存，请检查存储空间或目录权限")
    app.session.phase = Phase.RESULTS
    app.session.mode = GameMode.TIME_TRIAL
    app.session.race.snapshot = state
    app._shown_phase = None
    app.refresh_panel()
    summary = app.driving_cards.summary_values
    for label in summary['sectors']:
        assert not label.isHidden()
        lower, upper = label.getTightBounds(app.driving_cards.content)
        assert upper.z < app.workshop_vehicle.frame['frameSize'][2]
        assert lower.z > 1-860*2/941
    deltas = [label.getText() for label in summary['sectors'][2::3]]
    if invalid:
        assert all(value == "—" for value in deltas)
    else:
        assert "本圈更快 · 尚未保存" in summary['notice'].getText()
        assert deltas[0] == "+1.000"
    app.session.phase = Phase.MENU
    app.refresh_panel()
    assert all(column.isHidden() for column in app.result_sectors)


def test_full_session_frame_keeps_reference_and_sector_times_exactly(tmp_path):
    session = Session(track="test")
    try:
        expected = feedback_state()
        session.race.snapshot = expected
        restored = _decode_frame(_encode_frame(_output(session)))
        assert restored.race == expected
        assert restored.race.splits is not restored.race.reference_splits
    finally:
        session.close()


def test_score_group_uses_full_actual_hardware_even_without_explicit_base(tmp_path):
    session = Session(track="test")
    try:
        original = session.score_variant()
        assert len(original.rsplit("hardware-", 1)[1]) == 64 and "splits-v1" in original
        session.set_vehicle_config(session.vehicle_config)
        assert session.score_variant() == original
        session.set_vehicle_config(replace(session.vehicle_config, center_of_mass_height=.401))
        assert session.score_variant() != original
        changed = session.score_variant()
        session.set_abs_enabled(False)
        assert session.score_variant() != changed
    finally:
        session.close()
