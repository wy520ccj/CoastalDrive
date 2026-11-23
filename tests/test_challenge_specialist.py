"""极短专项共用预算与方案，但不能用油耗替代刹停/过门的原目标。"""

import json

import pytest

from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES, course_gates
from challenge_run import ChallengeRun
from challenge_scores import ChallengeScores
from fuel import FuelState
from race import BestTimes, GameMode
from session import Session


@pytest.mark.parametrize('key,seconds,value,medal', [
    ('parking', 30., 3., '金'), ('parking', 30., 10., '银'), ('parking', 30., 11., '铜'),
    ('slalom', 36., 5, '金'), ('slalom', 37., 5, '银'), ('slalom', 37., 3, '铜'),
    (GameMode.BRAKING_LESSON, 20., 2., '金'), (GameMode.BRAKING_LESSON, 20., 5., '银'),
    (GameMode.SHORT_BRAKING, 20., 33., '金'), (GameMode.SHORT_BRAKING, 20., 42., '铜'),
    (GameMode.SLALOM_LESSON, 23., 15., '金'), (GameMode.FAST_SLALOM, 20., 12.5, '银')])
def test_specialist_medal_uses_real_metric_and_cost_not_total_start_time_or_fuel(key, seconds, value, medal):
    spec = ROAD_CHALLENGES[key]
    result = spec.evaluate(BuildDraft(), seconds, .2, metric_value=value)
    assert result.medal == medal
    assert spec.evaluate(BuildDraft(), seconds, 2., metric_value=value).medal == medal
    assert not spec.evaluate(BuildDraft(), seconds, .01).official
    assert not spec.evaluate(BuildDraft(), seconds, .01, metric_value=value, valid=False).medal


def test_specialist_saved_full_result_revalidates_actual_metric_across_reload(tmp_path):
    spec = ROAD_CHALLENGES[GameMode.SHORT_BRAKING]
    scores = ChallengeScores(tmp_path/'best.json', spec, 'keyboard', 'physics-v1')
    result = spec.evaluate(BuildDraft(brake_share=.7), 20., .1, metric_value=33.)
    assert scores.record(result)
    data = json.loads(scores.path.read_text(encoding='utf-8'))
    row = data['contexts'][scores.key]['records']['金']['fastest']
    assert row['metric_value'] == 33.
    restored = ChallengeScores(scores.path, spec, 'keyboard', 'physics-v1')
    assert restored.records['金']['fastest']['metric_value'] == 33.


def test_shortest_stop_wins_even_when_its_full_run_is_slower_and_costlier(tmp_path):
    mode = GameMode.SHORT_BRAKING
    spec = ROAD_CHALLENGES[mode]
    path = tmp_path/'best.json'
    scores = ChallengeScores(path, spec, 'keyboard', 'physics-v1')
    quick = spec.evaluate(BuildDraft(), 11., .04, metric_value=32.35)
    short = spec.evaluate(BuildDraft(brakes=1.25, brake_share=.65), 12., .05, metric_value=28.22)
    assert scores.record(quick)
    assert scores.record(short) == (('完赛', 'specialist'), ('铜', 'specialist'),
                                    ('银', 'specialist'), ('金', 'specialist'))
    reopened = ChallengeScores(path, spec, 'keyboard', 'physics-v1')
    assert reopened.records['金']['fastest']['metric_value'] == 32.35
    assert reopened.records['金']['specialist']['metric_value'] == 28.22
    run = ChallengeRun(spec, BuildDraft(), FuelState(), gates=course_gates(mode), scores=reopened)
    assert run.snapshot.reference_result == short
    assert not reopened.record(spec.evaluate(BuildDraft(), 10., .03, metric_value=25., valid=False))
    assert reopened.reference['metric_value'] == 28.22


def test_legacy_specialist_comparison_uses_best_metric_from_retained_rows(tmp_path):
    mode = GameMode.FAST_SLALOM
    spec = ROAD_CHALLENGES[mode]
    path = tmp_path/'best.json'
    scores = ChallengeScores(path, spec, 'keyboard', 'physics-v1')
    scores.record(spec.evaluate(BuildDraft(), 18., .1, metric_value=11.5))
    scores.record(spec.evaluate(BuildDraft(front_tire=1.3), 19., .08, metric_value=11.))
    document = json.loads(path.read_text(encoding='utf-8'))
    group = document['contexts'][scores.key]
    for rows in (group['completed'], *group['records'].values()):
        del rows['specialist']
    path.write_text(json.dumps(document), encoding='utf-8')
    before = path.read_bytes()
    restored = ChallengeScores(path, spec, 'keyboard', 'physics-v1')
    assert restored.reference == restored.records['金']['economy']
    assert restored.records['金']['fastest']['metric_value'] == 11.5
    assert path.read_bytes() == before


def test_specialist_actual_session_suppresses_old_score_writes_and_preserves_criteria(tmp_path):
    for mode in (GameMode.BRAKING_LESSON, GameMode.SHORT_BRAKING, GameMode.SLALOM_LESSON, GameMode.FAST_SLALOM):
        app = Session(track='test', scores=BestTimes(tmp_path/(mode.value+'.json')))
        try:
            app.start(mode=mode, track='endless', challenge_spec=ROAD_CHALLENGES[mode], countdown=False)
            rule = app.highway.braking if app.highway.braking is not None else app.highway.slalom
            assert not rule.record_scores
            for _ in range(4):
                app.tick()
            app.finish()
            assert not app.highway.snapshot.engineering.result.official
        finally:
            app.close()
