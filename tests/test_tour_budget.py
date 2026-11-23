"""预算巡回的合成规则夹具；不作为真人成绩或道路平衡证据。"""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES
from challenge_rules import MedalTarget
from challenge_run import ChallengeStatus
from driving_tour import LEGS
from highway_run import HighwayResult
from season_cup import CUP_INPUT, CUP_LEGS, cup_specs
from tour_budget import BudgetTour, total, tour_medal, tour_points

SOURCE = {'fixture': 'rules-test-only'}


def result(mode, build=None, *, seconds=59., oil=5.5, valid=True):
    spec = ROAD_CHALLENGES[mode]
    measured = spec.evaluate(BuildDraft() if build is None else build, seconds,
                             oil*spec.distance_m/100_000, valid=valid)
    status = ChallengeStatus(spec.id, spec.name, spec.budget, measured.cost, seconds,
                             spec.distance_m, measured.litres, measured.consumption, (), measured)
    return HighwayResult(finished=True, succeeded=valid, engineering=status)


def complete(tour, builds=None, *, seconds=59., oil=5.5):
    builds = (BuildDraft(),)*3 if builds is None else builds
    for mode, build in zip(LEGS, builds, strict=True):
        tour.accept(mode, tour.variant, SOURCE, result(mode, build, seconds=seconds, oil=oil))


@pytest.fixture
def graded(monkeypatch):
    for mode in LEGS:
        monkeypatch.setitem(ROAD_CHALLENGES, mode, replace(ROAD_CHALLENGES[mode], targets=(
            MedalTarget('铜', 120., 10.), MedalTarget('银', 90., 8.), MedalTarget('金', 60., 6.)), provisional=False))


def test_trial_can_complete_and_resume_without_awarding_or_rewriting_legacy(tmp_path, monkeypatch):
    for mode in LEGS:
        spec = ROAD_CHALLENGES[mode]
        monkeypatch.setitem(ROAD_CHALLENGES, mode, replace(spec, provisional=True))
    legacy = tmp_path/'driving-tour.json'
    legacy.write_bytes(b'old tour bytes')
    tour = BudgetTour(tmp_path/'budget-tour.json', 'game', SOURCE)
    builds = (BuildDraft(power=1.05), BuildDraft(front_tire=1.15), BuildDraft(brake_share=.7))
    complete(tour, builds)
    assert len(tour.current) == 3 and not tour_medal(tour.current) and not tour_points(tour.current)
    assert tour.current[1].medal == '金'
    assert tour.latest == tour.current and not tour.bests
    assert tuple(row.build for row in tour.current) == builds
    restored = BudgetTour(tour.path, 'game', SOURCE)
    assert restored.latest == tour.current and restored.current == tour.current
    restored.restart()
    assert not restored.current and restored.latest == tour.current
    assert legacy.read_bytes() == b'old tour bytes'


def test_provisional_leg_requires_trial_copper_and_does_not_award_ranked_round(tmp_path, graded, monkeypatch):
    mode = LEGS[1]
    monkeypatch.setitem(ROAD_CHALLENGES, mode, replace(ROAD_CHALLENGES[mode], provisional=True))
    tour = BudgetTour(tmp_path/'tour.json', 'game', SOURCE)
    tour.accept(LEGS[0], 'game', SOURCE, result(LEGS[0]))
    assert '未达试行铜牌' in tour.accept(mode, 'game', SOURCE, result(mode, seconds=130.))
    assert len(tour.current) == 1
    tour.accept(mode, 'game', SOURCE, result(mode))
    assert '暂不授奖' in tour.accept(LEGS[2], 'game', SOURCE, result(LEGS[2]))
    assert all(entry.medal == '金' for entry in tour.latest)
    assert not tour_points(tour.latest) and not tour_medal(tour.latest) and not tour.bests


def test_whole_round_records_separate_speed_economy_cost_and_never_stitch_legs(tmp_path, graded):
    tour = BudgetTour(tmp_path/'tour.json', 'game', SOURCE)
    complete(tour, (BuildDraft(power=1.1),)*3)
    first = tour.current
    assert tour_medal(first) == '金' and tour_points(first) == 9 and tour.new_best
    tour.restart()
    complete(tour, seconds=58., oil=5.8)
    second = tour.current
    assert tour.bests['fastest'] == second and tour.bests['cheapest'] == second
    assert tour.bests['economy'] == first
    assert total(first, 'cost') > total(second, 'cost')
    assert all(len(rows) == 3 for rows in tour.bests.values())
    loaded = BudgetTour(tour.path, 'game', SOURCE)
    assert loaded.bests == tour.bests and loaded.best == second


def test_failed_overbudget_auto_and_changed_conditions_cannot_advance(tmp_path, graded):
    tour = BudgetTour(tmp_path/'tour.json', 'game', SOURCE)
    assert '未通过' in tour.accept(LEGS[0], 'game', SOURCE, HighwayResult())
    assert '未计' in tour.accept(LEGS[0], 'game', SOURCE, result(LEGS[0], BuildDraft(power=1.2)))
    auto = result(LEGS[0])
    auto = replace(auto, engineering=replace(auto.engineering,
        result=replace(auto.engineering.result, official=False, medal='', next_target=None)))
    assert '亲自驾驶' in tour.accept(LEGS[0], 'game', SOURCE, auto)
    assert '条件改变' in tour.accept(LEGS[0], 'other', SOURCE, result(LEGS[0]))
    assert '条件改变' in tour.accept(LEGS[0], 'game', {'changed': True}, result(LEGS[0]))
    assert '铜牌' in tour.accept(LEGS[0], 'game', SOURCE, result(LEGS[0], seconds=130.))
    assert not tour.current and not tour.path.exists()
    with pytest.raises(ValueError, match='站序'):
        tour.accept(LEGS[1], 'game', SOURCE, result(LEGS[1]))


def test_save_failure_keeps_old_disk_and_can_retry_complete_memory_round(tmp_path):
    tour = BudgetTour(tmp_path/'tour.json', 'game', SOURCE)
    tour.accept(LEGS[0], 'game', SOURCE, result(LEGS[0]))
    old = tour.path.read_bytes()
    with patch.object(Path, 'replace', side_effect=OSError('测试只读')):
        for mode in LEGS[1:]:
            tour.accept(mode, 'game', SOURCE, result(mode))
    assert len(tour.current) == 3 and tour.unsaved and '未保存' in tour.notice
    assert tour.path.read_bytes() == old
    assert tour.save() and not tour.unsaved
    assert BudgetTour(tour.path, 'game', SOURCE).latest == tour.current


def test_failed_restart_preserves_unsaved_completed_stage_and_saved_progress(tmp_path):
    tour = BudgetTour(tmp_path/'tour.json', 'game', SOURCE)
    tour.accept(LEGS[0], 'game', SOURCE, result(LEGS[0]))
    saved = tour.path.read_bytes()
    with patch.object(Path, 'replace', side_effect=OSError('测试只读')):
        tour.accept(LEGS[1], 'game', SOURCE, result(LEGS[1]))
        pending = tour.current
        assert not tour.restart()
    assert len(pending) == 2 and tour.current == pending and tour.unsaved
    assert tour.path.read_bytes() == saved
    assert tour.save() and BudgetTour(tour.path, 'game', SOURCE).current == pending
    assert tour.restart() and not BudgetTour(tour.path, 'game', SOURCE).current


def test_context_groups_and_corrupt_file_remain_separate(tmp_path):
    path = tmp_path/'tour.json'
    first = BudgetTour(path, 'game', SOURCE)
    first.accept(LEGS[0], 'game', SOURCE, result(LEGS[0]))
    second = BudgetTour(path, 'other', SOURCE)
    assert not second.current
    complete(second)
    assert BudgetTour(path, 'game', SOURCE).current == first.current
    document = json.loads(path.read_text(encoding='utf-8'))
    assert len(document['groups']) == 2
    path.write_bytes(b'{')
    broken = BudgetTour(path, 'game', SOURCE)
    broken.accept(LEGS[0], 'game', SOURCE, result(LEGS[0]))
    assert broken.blocked and broken.unsaved and path.read_bytes() == b'{'


def test_cup_requires_actual_car_and_saves_resume_pointer_with_stage(tmp_path):
    path = tmp_path/'season-cup.json'
    specs = cup_specs('coastal-hatch')
    cup = BudgetTour(path, CUP_INPUT, SOURCE, specs=specs)
    assert cup.save()
    first = CUP_LEGS[0]
    spec = specs[first]
    target = spec.targets[-1]
    measured = spec.evaluate(BuildDraft(), target.seconds, target.consumption*spec.distance_m/100_000)
    status = ChallengeStatus(spec.id, spec.name, spec.budget, 0, measured.seconds,
                             spec.distance_m, measured.litres, measured.consumption, (), measured)
    highway = HighwayResult(finished=True, succeeded=True, engineering=status)
    assert '车辆' in cup.accept(first, CUP_INPUT, SOURCE, highway,
                             vehicle_config=cup_specs('game-tuned')[first].base_config)
    original = path.read_bytes()
    with patch.object(Path, 'replace', side_effect=OSError('测试只读')):
        cup.accept(first, CUP_INPUT, SOURCE, highway, vehicle_config=spec.base_config)
    assert cup.unsaved and len(cup.current) == 1 and path.read_bytes() == original
    assert cup.save()
    second = BudgetTour(path, CUP_INPUT, SOURCE, specs=cup_specs('game-tuned'))
    assert second.save() and not second.current
    reopened = BudgetTour(path, CUP_INPUT, SOURCE, specs=specs)
    assert reopened.current == cup.current and reopened.save()
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['active'][CUP_INPUT] == cup.key and len(data['groups']) == 2
