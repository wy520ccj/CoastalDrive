"""真实控件的逐门布局；明确显示夹具不作为物理通关证据。"""

from dataclasses import replace

import pytest

from application import CoastalDrive
from race import GameMode
from session import Phase
from slalom_lesson import SlalomResult


@pytest.fixture
def app(tmp_path):
    game = CoastalDrive(smoke=True, output=tmp_path, render_size=(1024, 768))
    game.taskMgr.remove("finish-smoke")
    game.taskMgr.remove("drive-update")
    game.back_to_menu()
    game.start_slalom_lesson()
    for _ in range(360):
        game.session.tick()
    yield game
    game.close_game()


def result(**changes):
    return replace(SlalomResult(entry_kph=60., entry_time=5., run_seconds=12., gates=6,
        errors=(.1, -.2, .3, -.4, .2, 0.), clearances=(.9, .8, .7, .6, .8, 1.),
        gate_times=(2., 4., 6., 8., 10., 12.), reference_times=(2.1, 4.2, 6.3, 8.4, 10.5, 12.6),
        medal="金", finished=True, succeeded=True, reason="金牌 · 连续通过全部6道门",
        best_seconds=12., new_best=True), **changes)


def test_hud_current_gate_and_frozen_difference_fit_existing_card(app):
    state = result(gates=2, gate_times=(2., 4.), finished=False, succeeded=False, new_best=False)
    highway = replace(app.session.highway.snapshot, slalom=state)
    app.hud.update(app.session.current, app.session.race.snapshot, highway,
                   track="endless", countdown="", notice="")
    assert "第2门" in app.hud.split.getText() and "累计差 -0.200s" in app.hud.split.getText()
    lower, upper = app.hud.split.getTightBounds(app.hud.status_frame)
    assert lower.z > -.54 and upper.x < .84
    assert not app.hud.split.isHidden() and app.hud.notice_frame.getZ() == pytest.approx(.36)
    app.hud.update(app.session.current, replace(app.session.race.snapshot, mode=GameMode.FREE_DRIVE),
                   highway, track="endless", countdown="", notice="")
    assert app.hud.split.isHidden()


@pytest.mark.parametrize("failed", [False, True])
def test_six_gate_table_with_notice_clears_detail_and_buttons_and_retry(app, failed):
    state = result(save_notice="本次过门成绩未保存，请检查存储目录。", new_best=False)
    if failed:
        state = result(gates=2, gate_times=(2., 4., 6.), clearances=(.9, .8, -.3),
                       errors=(.1, -.2, 1.3), succeeded=False, new_best=False, reason="错过第3门；车身超出门线0.30m，提前回正/稍早减速。")
    app.session.highway.snapshot = replace(app.session.highway.snapshot, slalom=state,
        running=False, finished=True, reason=state.reason, succeeded=state.succeeded)
    app.session.phase = Phase.RESULTS
    app._shown_phase = None
    app.refresh_panel()
    assert "个人新最佳" not in app.panel_note.getText()
    for column in app.result_sectors:
        assert not column.isHidden() and len(column.getText().splitlines()) == 7
        lower, upper = column.getTightBounds(app.panel)
        assert lower.z > app.buttons[0].getZ()+app.buttons[0]["frameSize"][3]
        assert upper.z < app.panel_detail.getTightBounds(app.panel)[0].z-.01
        assert lower.x > -.94 and upper.x < .94
    if failed:
        assert "3左漏" in app.result_sectors[0].getText() and "4右 · 未到达" in app.result_sectors[0].getText()
        assert all(line.endswith(" / —") for line in app.result_sectors[2].getText().splitlines()[1:])
    app.buttons[0]["command"]()
    app.refresh_panel()
    assert all(column.isHidden() for column in app.result_sectors)
