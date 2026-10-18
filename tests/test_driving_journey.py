"""真实成绩文件派生的六档目标、平衡推荐、损坏边界与无额外进度写入。"""

import json

import pytest

from braking_lesson import BrakingScores
from driving_journey import read_driving_journey
from road_comparison import TrialScores
from slalom_lesson import SlalomScores


def read(root, key="car"):
    return read_driving_journey(BrakingScores(root/"braking.json", key), SlalomScores(root/"slalom.json", key))


def test_empty_progress_has_specific_first_target_without_creating_files(tmp_path):
    data = read(tmp_path)
    assert data["steps"] == 0 and data["next_index"] == 0 and data["stage"] == "铜牌起步"
    assert data["projects"][0]["target"] == 10. and data["projects"][1]["target"] == 24.
    assert not list(tmp_path.iterdir())


def test_six_real_saved_medal_targets_advance_in_balanced_order_and_restart(tmp_path):
    for index, (topic, target) in enumerate((("braking", 10.), ("slalom", 24.),
            ("braking", 5.), ("slalom", 18.), ("braking", 2.), ("slalom", 15.))):
        before = read(tmp_path)
        assert before["projects"][before["next_index"]]["topic"] == topic
        assert before["projects"][before["next_index"]]["target"] == target
        score = BrakingScores(tmp_path/"braking.json", "car") if topic == "braking" else SlalomScores(tmp_path/"slalom.json", "car")
        score.record(target)
        assert read(tmp_path)["steps"] == index+1
    data = read(tmp_path)
    assert data["next_index"] is None and data["stage"] == "双项金牌"
    assert all(item["level"] == 3 and item["target"] is None for item in data["projects"])
    raw = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    read(tmp_path)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == raw
    assert read(tmp_path, "other-hardware")["steps"] == 0


@pytest.mark.parametrize("error,seconds,levels,next_index,stage,gaps", [
    (10., 24., (1, 1), 0, "银牌进阶", (5., 6.)),
    (5.0001, 18.0001, (1, 1), 0, "银牌进阶", (.0001, .0001)),
    (5., 18., (2, 2), 0, "金牌冲刺", (3., 3.)),
    (2.0001, 15.0001, (2, 2), 0, "金牌冲刺", (.0001, .0001)),
    (0., 24., (3, 1), 1, "银牌进阶", (None, 6.)),
    (10., 12., (1, 3), 0, "银牌进阶", (5., None)),
])
def test_thresholds_match_existing_course_awards_and_next_improvement(tmp_path, error, seconds, levels, next_index, stage, gaps):
    BrakingScores(tmp_path/"braking.json", "car").record(error)
    SlalomScores(tmp_path/"slalom.json", "car").record(seconds)
    data = read(tmp_path)
    assert tuple(item["level"] for item in data["projects"]) == levels
    assert data["next_index"] == next_index and data["stage"] == stage
    for item, gap in zip(data["projects"], gaps, strict=True):
        assert item["gap"] == pytest.approx(gap) if gap is not None else item["gap"] is None


def test_damaged_one_course_keeps_other_and_bad_optional_detail_keeps_total(tmp_path):
    (tmp_path/"braking.json").write_text("broken", encoding="utf-8")
    (tmp_path/"slalom.json").write_text(json.dumps({"version": 1, "scores": {"car": 14.},
                                                 "runs": {"car": "broken"}}), encoding="utf-8")
    data = read(tmp_path)
    assert data["steps"] == 3 and data["next_index"] == 0 and len(data["errors"]) == 2
    assert data["projects"][1]["medal"] == "金" and data["projects"][0]["best"] is None


def test_failed_write_and_virtual_trial_do_not_create_progress(tmp_path):
    blocked = tmp_path/"blocked"
    blocked.write_text("file", encoding="utf-8")
    braking = BrakingScores(blocked/"braking.json", "car")
    braking.record(1.)
    virtual = TrialScores()
    virtual.record(12., gate_times=(2., 4., 6., 8., 10., 12.), clearances=(.5,)*6)
    # 虚拟接口结果不会进入玩家文件；面板只读玩家的两类成绩。
    data = read_driving_journey(braking, SlalomScores(tmp_path/"slalom.json", "car"))
    assert data["steps"] == 0 and data["errors"] and not (tmp_path/"slalom.json").exists()
