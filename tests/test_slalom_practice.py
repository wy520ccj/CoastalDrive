"""练习允许低速和漏门；实际驾驶不写入正式成绩与道路A/B。"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from slalom_driver import SlalomDriver, apply_keys

from player_road_ab import checked_record
from race import BestTimes, GameMode
from session import Phase, Session
from session_process import _decode_frame, _encode_frame, _output
from slalom_lesson import GATES, SlalomLesson, SlalomScores
from vehicle_config import CAR


@pytest.mark.parametrize('miss', [True, False])
def test_low_speed_and_missed_gates_continue_without_awards(tmp_path, miss):
    path = tmp_path/'scores.json'
    scores = SlalomScores(path, 'ordinary')
    scores.record(15.)
    original = path.read_bytes()
    run = SlalomLesson(8., SlalomScores(path, 'practice'), CAR, practice=True)
    run.update(87., 10., 7.9)
    run.update(88., 10., 8.)
    assert not run.snapshot.finished and run.snapshot.entry_kph == 36.
    for index, (distance, center) in enumerate(GATES):
        run.update(8.+distance, 10., 8.+(index+1)*3., lateral=0. if miss else center)
        if index < 5:
            assert not run.snapshot.finished
    result = run.snapshot
    assert result.finished and result.practice and result.succeeded
    assert len(result.gate_times) == 6 and result.gates == (1 if miss else 6)
    assert not result.medal and not result.new_best and result.best_seconds is None
    assert path.read_bytes() == original


def test_real_keyboard_slow_straight_practice_completes_but_is_not_valid_challenge(tmp_path):
    session = Session(scores=BestTimes(tmp_path/'best.json'))
    try:
        session.start(mode=GameMode.SLALOM_PRACTICE, track='endless', countdown=False, settle_initial=True)
        assert session.current.player.speed == 0
        config = session.vehicle_config
        driver = SlalomDriver(35., config, origin=session.highway.snapshot.slalom.start_progress, straight=True)
        for _ in range(4802):
            apply_keys(session.keyboard, driver.sample(session.current, 1/120))
            session.tick()
            if session.phase == Phase.RESULTS:
                break
        result = session.highway.snapshot.slalom
        assert result.practice and result.succeeded and result.entry_kph < 40
        assert result.gates == 1 and len(result.clearances) == 6 and min(result.clearances) < 0
        assert session.vehicle_config == config and not (tmp_path/'slalom-best.json').exists()
        output = _output(session)
        assert _decode_frame(_encode_frame(output)).highway == output.highway
        with pytest.raises(ValueError, match='题目'):
            checked_record({'context': {'mode': GameMode.SLALOM_PRACTICE.value}, 'config': {}, 'created_at': 'test'})
    finally:
        session.close()
