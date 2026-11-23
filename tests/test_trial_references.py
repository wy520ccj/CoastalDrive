"""自动试车跨启动对照、按组隔离及失败保留。"""

import json
from dataclasses import asdict, replace
from pathlib import Path

import pytest

from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES, SPRINT_CHALLENGES, course_gates
from challenge_run import ChallengeStatus, EnergySplit
from race import GameMode
from trial_references import TrialReferences, ValleyTrial

MODE = GameMode.VALLEY_PACE
SPEC = SPRINT_CHALLENGES[MODE]
GATES = course_gates(MODE)


def completed(build, seconds):
    litres = .2
    result = SPEC.evaluate(build, seconds, litres)
    result = replace(result, official=False, medal='', next_target=None,
                     notice='自动试车 · 已完成，不计成绩')
    splits = tuple(EnergySplit(gate, seconds*gate/SPEC.distance_m, litres*gate/SPEC.distance_m)
                   for gate in GATES[:-1])+(EnergySplit(SPEC.distance_m, seconds, litres),)
    return ChallengeStatus(SPEC.id, SPEC.name, SPEC.budget, result.cost, seconds, SPEC.distance_m,
                           litres, result.consumption, splits, result)


def test_trial_keeps_latest_measured_build_even_when_it_exceeds_budget(tmp_path):
    store = TrialReferences(tmp_path)
    group = ('valley', 'game', 'sdk-a')
    old = completed(BuildDraft(), 60.)
    new = completed(BuildDraft(power=1.2), 59.)
    assert new.result.cost > SPEC.budget
    assert store.save(group, SPEC, GATES, old)
    assert store.save(group, SPEC, GATES, new)
    reopened = TrialReferences(tmp_path)
    reference = reopened.load(group, SPEC, GATES)
    assert reference.result == new.result and reference.splits == new.splits
    assert reopened.load(('valley', 'game', 'sdk-b'), SPEC, GATES) is None
    assert reopened.load(('valley', 'direct', 'sdk-a'), SPEC, GATES) is None


def test_trial_migrates_single_run_and_keeps_last_distinct_builds(tmp_path):
    group = ('valley', 'game', 'sdk-a')
    store = TrialReferences(tmp_path)
    stock = completed(BuildDraft(), 60.)
    braking = completed(BuildDraft(brakes=1.25), 59.)
    light = completed(BuildDraft(mass=.96), 58.)
    path = store._path(group)
    old = {'version': 1, 'group': path.stem, 'build': asdict(stock.result.build),
           'splits': [asdict(split) for split in stock.splits]}
    path.write_text(json.dumps(old), encoding='utf-8')
    assert store.load(group, SPEC, GATES, build=BuildDraft()).result == stock.result
    assert json.loads(path.read_text(encoding='utf-8')) == old

    assert store.save(group, SPEC, GATES, braking)
    assert store.save(group, SPEC, GATES, completed(braking.result.build, 58.5))
    reopened = TrialReferences(tmp_path)
    assert reopened.load(group, SPEC, GATES, build=braking.result.build).result == stock.result
    assert reopened.load(group, SPEC, GATES, build=stock.result.build).result.seconds == 58.5

    assert reopened.save(group, SPEC, GATES, light)
    assert reopened.load(group, SPEC, GATES, build=light.result.build).result.seconds == 58.5
    assert len(json.loads(path.read_text(encoding='utf-8'))['runs']) == 2


def test_valley_trial_keeps_measured_braking_with_the_same_run(tmp_path):
    group = ('valley', 'game', 'sdk-a')
    store = TrialReferences(tmp_path)
    old = completed(BuildDraft(), 60.)
    braking = completed(BuildDraft(brakes=1.25), 59.)
    measured = ValleyTrial(83., .72, 45.7)
    assert store.save(group, SPEC, GATES, old)
    assert store.save(group, SPEC, GATES, braking, valley=measured)
    reopened = TrialReferences(tmp_path)
    assert reopened.load(group, SPEC, GATES, build=braking.result.build).valley is None
    assert reopened.save(group, SPEC, GATES, old)
    reference = TrialReferences(tmp_path).load(group, SPEC, GATES, build=old.result.build)
    assert reference.result == braking.result and reference.valley == measured
    with pytest.raises(ValueError, match='制动数据无效'):
        ValleyTrial(83., .72, 50.01)


def test_short_brake_trial_restores_actual_stop_before_final_distance_gate(tmp_path):
    mode = GameMode.SHORT_BRAKING
    spec, gates = ROAD_CHALLENGES[mode], course_gates(mode)
    draft = BuildDraft(brakes=1.25, brake_share=.65)
    result = spec.evaluate(draft, 9., .03, metric_value=27.25)
    result = replace(result, official=False, medal='', notice='自动试车 · 已完成，不计成绩')
    splits = tuple(EnergySplit(gate, seconds, litres)
                   for gate, seconds, litres in zip(gates[:3], (3., 5., 7.), (.01, .02, .025), strict=True))
    status = ChallengeStatus(spec.id, spec.name, spec.budget, result.cost, result.seconds, 127.25,
                             result.litres, result.consumption, splits, result, assessment=spec.assessment)
    group = (spec.id, 'game', 'sdk-a')
    assert TrialReferences(tmp_path).save(group, spec, gates, status)
    reopened = TrialReferences(tmp_path).load(group, spec, gates)
    assert reopened.result == result and reopened.splits == splits


def test_fast_slalom_trial_preserves_all_gate_clearances_and_rejects_a_missed_gate(tmp_path):
    mode = GameMode.FAST_SLALOM
    spec, gates = ROAD_CHALLENGES[mode], course_gates(mode)
    result = spec.evaluate(BuildDraft(front_tire=1.3), 18., .08, metric_value=11.4)
    result = replace(result, official=False, medal='', notice='自动试车 · 已完成，不计成绩')
    splits = tuple(EnergySplit(gate, seconds, litres)
                   for gate, seconds, litres in zip(gates, (6.6, 10.4, 14.2, 18.), (.02, .04, .06, .08), strict=True))
    status = ChallengeStatus(spec.id, spec.name, spec.budget, result.cost, result.seconds, spec.distance_m,
                             result.litres, result.consumption, splits, result, assessment=spec.assessment)
    store = TrialReferences(tmp_path)
    group = (spec.id, 'game', 'sdk-a')
    clearances = (.3, .4, .55, .57, .45, .6)
    assert store.save(group, spec, gates, status, clearances=clearances)
    path = next(tmp_path.glob('*.json'))
    before = path.read_bytes()
    with pytest.raises(ValueError, match='六道有效门'):
        store.save(group, spec, gates, status, clearances=(*clearances[:-1], -.1))
    restored = TrialReferences(tmp_path).load(group, spec, gates)
    assert restored.result == result and restored.clearances == clearances
    assert path.read_bytes() == before


def test_failed_trial_save_keeps_old_file_and_supports_current_session(tmp_path, monkeypatch):
    store = TrialReferences(tmp_path)
    group = ('valley', 'game', 'sdk-a')
    old = completed(BuildDraft(), 60.)
    new = completed(BuildDraft(front_tire=1.3), 59.)
    assert store.save(group, SPEC, GATES, old)
    path = next(tmp_path.glob('*.json'))
    before = path.read_bytes()

    def fail(source, target):
        raise PermissionError('写入失败')

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'replace', fail)
        assert not store.save(group, SPEC, GATES, new)
    assert '未保存' in store.notice and path.read_bytes() == before
    assert store.load(group, SPEC, GATES).result == new.result
    assert store.load(group, SPEC, GATES, build=new.result.build).result == old.result
    assert TrialReferences(tmp_path).load(group, SPEC, GATES).result == old.result
    assert store.save(group, SPEC, GATES, new)
    assert TrialReferences(tmp_path).load(group, SPEC, GATES).result == new.result
