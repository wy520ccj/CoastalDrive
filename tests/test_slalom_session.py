"""真实游戏机械配置、二值驾驶请求、完成步传输及课题失败。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
from slalom_driver import SlalomDriver, apply_keys

from race import BestTimes, GameMode
from session import Phase, Session
from session_process import _decode_frame, _encode_frame, _output


@pytest.mark.parametrize("target,medal,straight", [(40., "铜", False), (50., "银", False), (60., "金", False), (60., "", True)])
def test_actual_keyboard_course_has_valid_medals_and_straight_line_misses(tmp_path, target, medal, straight):
    app = Session(track="endless", road_shape="straight", scores=BestTimes(tmp_path/"best.json"), independent_clock=False)
    try:
        app.start(countdown=False, mode=GameMode.SLALOM_LESSON, settle_initial=True)
        config = app.vehicle_config
        assert config.tire_substeps == 1 and not app.simulation.npcs
        app.set_controller(app.keyboard)
        driver = SlalomDriver(target, config, origin=app.current.player.position[1], straight=straight)
        for _ in range(40*120+2):
            apply_keys(app.keyboard, driver.sample(app.current, 1/120))
            app.tick()
            if app.phase == Phase.RESULTS:
                break
        assert app.phase == Phase.RESULTS
        result = app.highway.snapshot.slalom
        assert result.medal == medal and result.succeeded == bool(medal)
        assert app.current.collisions == 0 and app.vehicle_config == config
        assert all(value >= 0 for value in result.clearances) if medal else result.clearances[0] < 0
        assert result.gates == (6 if medal else 0)
        output = _output(app)
        assert _decode_frame(_encode_frame(output)).highway == output.highway
        app.start(countdown=False, mode=GameMode.SLALOM_LESSON)
        restarted = app.highway.snapshot.slalom
        assert restarted.gates == 0 and restarted.entry_time is None
        assert (restarted.best_seconds is not None) == bool(medal)
    finally:
        app.close()


def test_context_rejects_wrong_road_and_reset_exit_and_changed_electronics_have_no_pass(tmp_path):
    app = Session(track="test", road_shape="hills", scores=BestTimes(tmp_path/"best.json"), independent_clock=False)
    try:
        with pytest.raises(ValueError):
            app.start(mode=GameMode.SLALOM_LESSON, track="test")
        with pytest.raises(ValueError):
            app.start(mode=GameMode.SLALOM_LESSON, track="endless")
        app.road_shape = "straight"
        app.start(countdown=False, mode=GameMode.SLALOM_LESSON, track="endless")
        app.finish()
        assert app.highway.snapshot.slalom.finished and not app.highway.snapshot.succeeded
        app.menu()
        old = app.score_variant()
        app.set_esc_enabled(not app.esc_enabled)
        assert app.score_variant() != old
        app.start(countdown=False, mode=GameMode.SLALOM_LESSON, track="endless")
        assert app.highway.snapshot.slalom.best_seconds is None
        app.highway.update(app.highway_progress(), 0, 1/120, reset=True)
        assert "复位" in app.highway.snapshot.slalom.reason
    finally:
        app.close()
