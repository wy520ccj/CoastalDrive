"""老车和历史解锁保留，新预算奖牌独立，永久积分不能再购买性能。"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from career import EVENT_BY_ID, PARTS, CareerProgress
from challenge_build import BuildDraft
from challenge_catalog import CAREER_CHALLENGES


def legacy_file(path):
    doc = {'version': 1, 'credits': 960, 'owned': ['sport-front', 'street-power'],
           'records': {'first-drive': {'stars': 3, 'seconds': 25.},
                       'parking': {'stars': 3, 'seconds': 30.}}}
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
    return doc


def test_legacy_load_is_read_only_unlocks_preserved_and_purchase_never_mutates(tmp_path):
    path = tmp_path/'career.json'
    old = legacy_file(path)
    before = path.read_bytes()
    progress = CareerProgress(path)
    assert progress.stars == 6 and progress.available(EVENT_BY_ID['ridge-run'])
    assert progress.credits == 960 and progress.owned == set(old['owned'])
    assert progress.budget_records == {}
    assert path.read_bytes() == before
    for part in PARTS:
        assert not progress.buy(part)
        assert path.read_bytes() == before


def test_new_specialist_result_updates_separate_record_without_minting_credits_or_adding_old_stars_twice(tmp_path):
    path = tmp_path/'career.json'
    old = legacy_file(path)
    progress = CareerProgress(path)
    spec = CAREER_CHALLENGES['parking']
    result = spec.evaluate(BuildDraft(brake_share=.7), 30., .05, metric_value=3.)
    award = progress.record_challenge(result)
    assert award['saved'] and award['credits'] == 0
    assert progress.stars == 6 and progress.credits == 960
    assert progress.records == old['records'] and progress.owned == set(old['owned'])
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['version'] == 2 and data['records'] == old['records']
    assert data['challenges']['parking']['metric_value'] == 3.
    restored = CareerProgress(path)
    assert restored.budget_records == progress.budget_records
    assert restored.course_record(EVENT_BY_ID['parking']) == {'stars': 3, 'seconds': 30.}


def test_new_player_can_unlock_from_budget_specialists_and_bad_result_does_not_progress(tmp_path):
    progress = CareerProgress(tmp_path/'career.json')
    spec = CAREER_CHALLENGES['parking']
    result = spec.evaluate(BuildDraft(), 30., .05, metric_value=3.)
    assert progress.record_challenge(result)['saved'] and progress.stars == 3
    assert progress.available(EVENT_BY_ID['slalom'])
    trial = spec.evaluate(BuildDraft(brakes=1.3), 30., .05, metric_value=3.)
    old = progress.path.read_bytes()
    assert not trial.official
    progress.record_challenge(trial)
    assert progress.path.read_bytes() == old
    with pytest.raises(ValueError, match='真实预算结果'):
        progress.record_challenge(replace(result, seconds=20., cost=10))


def test_migration_save_failure_keeps_old_bytes_and_unlocks(tmp_path, monkeypatch):
    path = tmp_path/'career.json'
    legacy_file(path)
    progress = CareerProgress(path)
    before = path.read_bytes()

    def fail(source, target):
        raise OSError('不可写')

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'replace', fail)
        result = CAREER_CHALLENGES['parking'].evaluate(BuildDraft(), 20., .05, metric_value=3.)
        assert not progress.record_challenge(result)['saved']
    assert progress.budget_records == {} and progress.stars == 6
    assert path.read_bytes() == before


def test_budget_career_can_progress_from_fresh_save_to_cup(tmp_path):
    progress = CareerProgress(tmp_path/'career.json')

    def record(event_id, seconds, oil, medal, *, metric=None):
        spec = CAREER_CHALLENGES[event_id]
        result = spec.evaluate(BuildDraft(), seconds, oil*spec.distance_m/100_000, metric_value=metric)
        assert result.medal == medal
        assert progress.record_challenge(result)['saved']

    assert not progress.available(EVENT_BY_ID['coast-sprint'])
    record('first-drive', 17.2, 35.1, '铜')
    record('parking', 25., 30., '银', metric=5.)
    assert progress.stars == 3 and progress.available(EVENT_BY_ID['slalom'])
    record('slalom', 40., 25., '银', metric=5)
    assert progress.stars == 5 and not progress.available(EVENT_BY_ID['coastal-cup'])
    record('coast-sprint', 59.9, 21.2, '金')
    record('ridge-run', 63.4, 21., '金')
    assert progress.recommended().id == 'coastal-cup'
    record('coastal-cup', 111.7, 19.2, '金')
    restored = CareerProgress(progress.path)
    assert restored.stars == 14 and restored.credits == 0
    assert restored.course_record(EVENT_BY_ID['coastal-cup']) == {'stars': 3, 'seconds': 111.7}
