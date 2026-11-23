"""跨方案比较的完整记录、版本隔离和写入失败保护。"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_challenge_rules import SPEC

from challenge_build import BuildDraft
from challenge_scores import ChallengeScores


def book(path, spec=SPEC, group='keyboard', physics='physics-v1'):
    return ChallengeScores(path, spec, group, physics)


def test_distinct_builds_compete_in_same_context_without_splicing_metrics(tmp_path):
    path = tmp_path/'challenges.json'
    scores = book(path)
    first = SPEC.evaluate(BuildDraft(power=1.1), 60., .069)
    second = SPEC.evaluate(BuildDraft(mass=.96), 64., .060)
    cheap = SPEC.evaluate(BuildDraft(), 65., .070)
    assert len(scores.record(first)) == 12
    scores.record(second)
    scores.record(cheap)
    restored = book(path)
    gold = restored.records['金']
    assert gold['fastest']['seconds'] == 60. and gold['fastest']['litres'] == .069
    assert gold['economy']['seconds'] == 64. and gold['economy']['litres'] == .060
    assert gold['cheapest']['cost'] == 0 and gold['cheapest']['seconds'] == 65.
    assert len({row['run_id'] for row in gold.values()}) == 3
    assert len(json.loads(path.read_text(encoding='utf-8'))['contexts']) == 1


def test_input_rule_and_physics_changes_keep_old_records_without_combining(tmp_path):
    path = tmp_path/'challenges.json'
    scores = book(path)
    scores.record(SPEC.evaluate(BuildDraft(), 65., .07))
    before = path.read_bytes()
    for changed in (book(path, group='gamepad'), book(path, physics='physics-v2'),
                    book(path, spec=replace(SPEC, budget=6500)),
                    book(path, spec=replace(SPEC, provisional=True))):
        assert changed.records == {}
    assert path.read_bytes() == before and book(path).records


def test_corrupt_file_and_failed_replace_do_not_destroy_existing_record(tmp_path, monkeypatch):
    path = tmp_path/'challenges.json'
    scores = book(path)
    scores.record(SPEC.evaluate(BuildDraft(), 65., .07))
    before = path.read_bytes()
    records = dict(scores.records)
    original = Path.replace

    def fail(source, target):
        if target == path:
            raise OSError('写入失败')
        return original(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'replace', fail)
        assert not scores.record(SPEC.evaluate(BuildDraft(), 64., .069))
    assert scores.notice and scores.records == records and path.read_bytes() == before
    path.write_text('{broken', encoding='utf-8')
    broken = book(path)
    assert broken.notice
    assert not broken.record(SPEC.evaluate(BuildDraft(), 60., .06))
    assert path.read_text(encoding='utf-8') == '{broken'


def test_pending_score_survives_reopen_and_recovers_only_in_its_group(tmp_path):
    path = tmp_path/'challenges.json'
    scores = book(path)
    result = SPEC.evaluate(BuildDraft(), 59., .06)
    # 正式文件不可替换，旁边的待保存目录仍可用。
    path.mkdir()
    assert not scores.record(result)
    staged, = scores.pending_folder.glob('*.json')
    original = staged.read_bytes()
    run_id = scores.pending_score['run_id']
    path.rmdir()

    book(path, group='gamepad').recover_pending()
    assert not path.exists() and staged.read_bytes() == original
    reopened = book(path)
    reopened.recover_pending()
    assert reopened.reference['run_id'] == run_id and reopened.reference['seconds'] == result.seconds
    assert not staged.exists()

    # 模拟正式文件已经写入、待保存文件尚未清理便退出。
    recorded = path.read_bytes()
    staged.write_bytes(original)
    book(path).recover_pending()
    assert not staged.exists() and path.read_bytes() == recorded


def test_trials_invalid_and_tampered_results_do_not_create_progress(tmp_path):
    path = tmp_path/'challenges.json'
    scores = book(path)
    assert not scores.record(SPEC.evaluate(BuildDraft(power=1.2), 50., .05))
    assert not scores.record(SPEC.evaluate(BuildDraft(), 50., .05, valid=False))
    with pytest.raises(ValueError, match='不一致'):
        scores.record(replace(SPEC.evaluate(BuildDraft(), 60., .07), cost=0, medal='铜'))
    assert not path.exists()


def test_unrated_finishes_keep_complete_bests_without_awards_and_isolate_new_targets(tmp_path):
    path = tmp_path/'challenges.json'
    spec = replace(SPEC, targets=())
    scores = book(path, spec)
    assert len(scores.record(spec.evaluate(BuildDraft(power=1.1), 60., .069))) == 3
    scores.record(spec.evaluate(BuildDraft(mass=.96), 64., .060))
    scores.record(spec.evaluate(BuildDraft(), 65., .070))
    restored = book(path, spec)
    assert restored.records == {}
    assert restored.completed['fastest']['seconds'] == 60.
    assert restored.completed['fastest']['litres'] == .069
    assert restored.completed['economy']['seconds'] == 64.
    assert restored.completed['economy']['litres'] == .060
    assert restored.completed['cheapest']['cost'] == 0
    assert len({row['run_id'] for row in restored.completed.values()}) == 3
    before = path.read_bytes()
    assert not restored.record(spec.evaluate(BuildDraft(power=1.2), 50., .05))
    assert not restored.record(spec.evaluate(BuildDraft(), 50., .05, valid=False))
    assert path.read_bytes() == before
    assert book(path).completed == {} and book(path).records == {}


def test_old_medal_group_still_loads_without_completed_field(tmp_path):
    path = tmp_path/'challenges.json'
    scores = book(path)
    fastest = SPEC.evaluate(BuildDraft(power=1.1), 60., .075)
    gold = SPEC.evaluate(BuildDraft(), 65., .07)
    scores.record(fastest)
    scores.record(gold)
    data = json.loads(path.read_text(encoding='utf-8'))
    del data['contexts'][scores.key]['completed']
    path.write_text(json.dumps(data), encoding='utf-8')
    before = path.read_bytes()
    restored = book(path)
    assert restored.records['金']['fastest']['seconds'] == 65.
    assert restored.completed['fastest']['seconds'] == fastest.seconds
    assert restored.completed['economy']['litres'] == gold.litres
    assert restored.completed['cheapest']['cost'] == gold.cost
    assert not restored.record(gold) and not restored.notice
    assert path.read_bytes() == before
