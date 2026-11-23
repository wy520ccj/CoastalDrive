"""道路门与燃油同一时间窗，跨终点子步截取且原车倒计时不混入。"""

from dataclasses import replace

import pytest
from test_challenge_rules import SPEC

from challenge_build import BuildDraft
from challenge_run import ChallengeRun, EnergySplit
from challenge_scores import ChallengeScores
from fuel import FuelState


def test_authoritative_totals_and_multiple_gate_crossings_share_one_finish_window(tmp_path):
    scores = ChallengeScores(tmp_path/'scores.json', SPEC, 'keyboard', 'physics-v1')
    run = ChallengeRun(SPEC, BuildDraft(), FuelState(litres=.2), gates=(250., 500., 1000.), scores=scores)
    run.sample(FuelState(litres=.212), 200., 10., passed=0)
    run.sample(FuelState(litres=.260), 1200., 70., passed=3, finished=True, succeeded=True)
    state = run.snapshot
    assert state.result.medal == '金'
    assert state.seconds == pytest.approx(58.)
    assert state.litres == pytest.approx(.0504)
    assert state.consumption == pytest.approx(5.04)
    assert tuple(split.distance_m for split in state.splits) == (250., 500., 1000.)
    assert state.splits[-1].seconds == state.result.seconds
    assert state.splits[-1].litres == state.result.litres
    assert scores.records['金']['fastest']['splits'][-1]['litres'] == state.result.litres
    assert tuple(name for grade, name in state.record_updates if grade == '金') == ('fastest', 'economy', 'cheapest')
    run.sample(FuelState(litres=1.), 3000., 120., passed=3)
    assert run.snapshot == state


def test_retry_does_not_replace_a_newer_best(tmp_path, monkeypatch):
    path = tmp_path/'scores.json'
    scores = ChallengeScores(path, SPEC, 'keyboard', 'physics-v1')
    run = ChallengeRun(SPEC, BuildDraft(), FuelState(), gates=(1000.,), scores=scores)

    def fail(document):
        raise OSError('测试只读')

    with monkeypatch.context() as patch:
        patch.setattr(scores, '_write', fail)
        run.sample(FuelState(litres=.05), 1000., 60., passed=1, finished=True, succeeded=True)
    original = run.snapshot
    assert original.score_pending and not original.record_updates and not path.exists()
    newer = ChallengeScores(path, SPEC, 'keyboard', 'physics-v1')
    assert newer.record(SPEC.evaluate(BuildDraft(), 59., .049))
    saved = path.read_bytes()
    run.retry_score()
    assert not run.snapshot.score_pending and not run.snapshot.record_updates
    assert run.snapshot.result == original.result and run.snapshot.splits == original.splits
    assert path.read_bytes() == saved


def test_trial_and_missing_historical_fuel_can_finish_without_award():
    trial = ChallengeRun(SPEC, BuildDraft(power=1.2), FuelState(), gates=(1000.,))
    trial.sample(FuelState(litres=.06), 1000., 60., passed=1, finished=True, succeeded=True)
    assert not trial.snapshot.result.official
    missing = ChallengeRun(SPEC, BuildDraft(), None, gates=(1000.,))
    missing.sample(None, 1000., 60., passed=1, finished=True, succeeded=True)
    assert missing.snapshot.litres is None and not missing.snapshot.result.medal


def test_pause_reads_and_early_stop_do_not_consume_or_award():
    run = ChallengeRun(SPEC, BuildDraft(), FuelState(litres=.1), gates=(1000.,))
    run.sample(FuelState(litres=.12), 100., 10., passed=0)
    assert run.snapshot == run.snapshot
    run.stop('挑战提前结束')
    assert run.snapshot.result.notice == '挑战提前结束'
    assert not run.snapshot.result.valid
    assert run.snapshot.litres == pytest.approx(.02)


def test_sensor_epoch_model_and_gate_inconsistency_are_rejected():
    run = ChallengeRun(SPEC, BuildDraft(), FuelState(litres=.1), gates=(1000.,))
    with pytest.raises(ValueError, match='倒退'):
        run.sample(FuelState(litres=.05), 10., 1., passed=0)
    with pytest.raises(ValueError, match='版本'):
        run.sample(replace(FuelState(litres=.12), model='other'), 10., 1., passed=0)
    with pytest.raises(ValueError, match='真实赛段进度'):
        run.sample(FuelState(litres=.12), 10., 1., passed=1)


def test_circuit_uses_geometric_crossing_time_for_both_time_and_fuel():
    run = ChallengeRun(SPEC, BuildDraft(), FuelState(litres=.2), gates=(250., 500., 1000.))
    run.sample(FuelState(litres=.212), 200., 10., passed=0, crossing_times=())
    # 环路门线位于当前真实步的内部，投影弧长可因横向位置略低于规定门距。
    run.sample(FuelState(litres=.260), 999.9, 70., passed=3, finished=True, succeeded=True,
               crossing_times=(20., 35., 69.5))
    assert run.snapshot.seconds == 69.5
    assert run.snapshot.litres == pytest.approx(.0596)
    assert run.snapshot.consumption == pytest.approx(5.96)
    assert tuple(row.seconds for row in run.snapshot.splits) == (20., 35., 69.5)


@pytest.mark.parametrize('graded', [False, True])
def test_reference_is_frozen_at_start_and_survives_restart(tmp_path, graded):
    spec = replace(SPEC, provisional=True) if graded else replace(SPEC, targets=())
    path = tmp_path/'scores.json'
    scores = ChallengeScores(path, spec, 'keyboard', 'physics-v1')
    first = ChallengeRun(spec, BuildDraft(), FuelState(), gates=(500., 1000.), scores=scores)
    assert first.snapshot.reference_result is None
    first.sample(FuelState(litres=.03), 500., 30., passed=1)
    first.sample(FuelState(litres=.06), 1000., 60., passed=2, finished=True, succeeded=True)
    assert first.snapshot.result.valid and first.snapshot.result.medal == ('金' if graded else '')
    assert bool(scores.records) == graded
    restored = ChallengeScores(path, spec, 'keyboard', 'physics-v1')
    second = ChallengeRun(spec, BuildDraft(power=1.1), FuelState(), gates=(500., 1000.), scores=restored)
    assert second.snapshot.reference_splits == first.snapshot.splits
    assert second.snapshot.reference_result.seconds == 60.
    assert second.snapshot.reference_result.build == BuildDraft()
    second.sample(FuelState(litres=.07), 1000., 55., passed=2, finished=True, succeeded=True)
    assert restored.completed['fastest']['seconds'] == 55.
    assert second.snapshot.reference_result.seconds == 60.
    assert second.snapshot.reference_splits == first.snapshot.splits
    assert {name for _, name in second.snapshot.record_updates} == {'fastest'}


@pytest.mark.parametrize('seconds,litres,label,field', [
    (59., .074, '金牌最省油', 'economy'),
    (69., .065, '金牌最快', 'fastest'),
    (70., .080, '金牌最省油', 'economy'),
])
def test_promotion_uses_whole_qualified_reference_frozen_at_start(tmp_path, seconds, litres, label, field):
    scores = ChallengeScores(tmp_path/'scores.json', SPEC, 'keyboard', 'physics-v1')
    candidates = {
        'fastest': SPEC.evaluate(BuildDraft(front_tire=1.3), 61., .069),
        'economy': SPEC.evaluate(BuildDraft(mass=.96), 64., .063),
    }
    for result in (*candidates.values(), SPEC.evaluate(BuildDraft(), 55., .075),
                   SPEC.evaluate(BuildDraft(drag=.95), 71., .058)):
        scores.record(result, splits=(EnergySplit(1000., result.seconds, result.litres),))
    run = ChallengeRun(SPEC, BuildDraft(), FuelState(), gates=(1000.,), scores=scores)
    assert run.snapshot.reference_result.seconds == 55.
    scores.record(SPEC.evaluate(BuildDraft(power=1.1), 52., .04))
    run.sample(FuelState(litres=litres), 1000., seconds, passed=1, finished=True, succeeded=True)
    status, selected = run.snapshot, candidates[field]
    assert status.result.medal == '银' and status.reference_label == label
    assert status.reference_result == selected
    assert status.reference_splits == (EnergySplit(1000., selected.seconds, selected.litres),)


def test_missing_next_grade_reference_keeps_existing_fastest(tmp_path):
    scores = ChallengeScores(tmp_path/'scores.json', SPEC, 'keyboard', 'physics-v1')
    prior = SPEC.evaluate(BuildDraft(), 60., .075)
    scores.record(prior)
    run = ChallengeRun(SPEC, BuildDraft(front_tire=1.3), FuelState(), gates=(1000.,), scores=scores)
    run.sample(FuelState(litres=.074), 1000., 59., passed=1, finished=True, succeeded=True)
    assert run.snapshot.result.next_target.medal == '金'
    assert run.snapshot.reference_result == prior and not run.snapshot.reference_label


def test_automatic_completion_on_medal_route_does_not_save_or_display_an_award(tmp_path):
    from challenge_catalog import SPRINT_CHALLENGES
    from race import GameMode

    spec = SPRINT_CHALLENGES[GameMode.BEND_SPRINT]
    scores = ChallengeScores(tmp_path/'scores.json', spec, 'keyboard', 'fixture')
    run = ChallengeRun(spec, BuildDraft(), FuelState(), gates=(spec.distance_m,), scores=scores)
    run.player_driven = False
    run.sample(FuelState(litres=.3), spec.distance_m, 90., passed=1, finished=True, succeeded=True)
    assert spec.evaluate(BuildDraft(), 90., .3).medal == '金'
    assert not run.snapshot.provisional and run.snapshot.result.valid
    assert not run.snapshot.result.official and not run.snapshot.result.medal
    assert '金牌完成' not in run.snapshot.result.notice
    assert not run.snapshot.record_updates
    assert scores.records == scores.completed == {} and not scores.path.exists()
