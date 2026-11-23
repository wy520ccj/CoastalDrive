"""每关草稿跨重启恢复、条件变化隔离与保存失败保护。"""

from dataclasses import replace
from pathlib import Path

from challenge_build import BuildDraft
from challenge_catalog import CAREER_CHALLENGES, ROAD_CHALLENGES, SPRINT_CHALLENGES
from challenge_plans import ChallengePlans
from race import GameMode


def test_per_event_builds_restore_and_free_trial_budget_is_not_a_purchase(tmp_path):
    path = tmp_path/'plans.json'
    first, second = tuple(SPRINT_CHALLENGES.values())[:2]
    book = ChallengePlans(path)
    assert book.load(first) == BuildDraft()
    expensive = BuildDraft(power=1.2, mass=.96, brake_share=.7)
    assert expensive.cost > first.budget
    assert book.save(first, expensive)
    assert book.save(second, BuildDraft(front_tire=1.15))
    assert ChallengePlans(path).load(first) == expensive
    assert ChallengePlans(path).load(second) == BuildDraft(front_tire=1.15)
    assert ChallengePlans(path).load(replace(first, version='next-version')) == BuildDraft()


def test_bad_file_is_preserved_and_cannot_be_overwritten_by_save(tmp_path):
    path = tmp_path/'plans.json'
    path.write_text('{bad', encoding='utf-8')
    book, spec = ChallengePlans(path), next(iter(SPRINT_CHALLENGES.values()))
    assert book.load(spec) == BuildDraft() and book.notice
    assert not book.save(spec, BuildDraft(power=1.1))
    assert path.read_text(encoding='utf-8') == '{bad'


def test_rating_upgrade_restores_previous_draft_until_a_new_draft_is_saved(tmp_path):
    path = tmp_path/'plans.json'
    book = ChallengePlans(path)
    spec = CAREER_CHALLENGES['first-drive']
    previous = replace(spec, version='budget-energy-v1', targets=())
    draft = BuildDraft(final_drive=1.075)
    assert book.save(previous, draft)
    old = path.read_bytes()
    assert book.load(spec) == draft and path.read_bytes() == old
    assert book.save(spec, BuildDraft())
    restored = ChallengePlans(path)
    assert restored.load(spec) == BuildDraft()
    assert restored.load(previous) == draft


def test_ridge_rating_upgrade_keeps_drafts_separate_across_road_versions(tmp_path):
    book = ChallengePlans(tmp_path/'plans.json')
    spec = SPRINT_CHALLENGES[GameMode.RIDGE_SPRINT]
    v4 = replace(spec, version='budget-route-v4', road_shape='budget-ridge-suspension', targets=())
    v5 = replace(spec, version='budget-route-v5', road_shape='budget-ridge-long-waves', targets=())
    assert book.save(v4, BuildDraft(springs=.75))
    assert book.load(replace(v4, version='budget-route-v4-medals-v1')).springs == .75
    assert book.load(replace(v5, version='budget-route-v5-medals-v1')) == BuildDraft()


def test_distance_road_rule_upgrade_restores_previous_draft(tmp_path):
    book = ChallengePlans(tmp_path/'plans.json')
    spec = ROAD_CHALLENGES[GameMode.DISTANCE_CHALLENGE]
    previous = replace(spec, version='budget-energy-v1')
    draft = BuildDraft(mass=.96, drag=.95)
    assert book.save(previous, draft)
    assert book.load(spec) == draft


def test_failed_replace_preserves_previous_plan_then_can_retry(tmp_path, monkeypatch):
    path = tmp_path/'plans.json'
    book, spec = ChallengePlans(path), next(iter(SPRINT_CHALLENGES.values()))
    assert book.save(spec, BuildDraft())
    old = path.read_bytes()
    original = Path.replace

    def fail(source, target):
        if target == path:
            raise OSError('写入失败')
        return original(source, target)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'replace', fail)
        assert not book.save(spec, BuildDraft(power=1.1))
    assert path.read_bytes() == old
    assert book.save(spec, BuildDraft(power=1.1))
