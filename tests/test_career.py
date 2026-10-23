"""规则/成长/经济的确定性测试；合成判定输入不充当真实驾驶证据。"""

from dataclasses import replace
from pathlib import Path

from career import EVENT_BY_ID, PARTS, CareerProgress
from career_run import CareerResult, CareerRun
from vehicle_designs import vehicle_design


def finished(event='first-drive', stars=3, seconds=25.):
    return CareerResult(event, 8., elapsed=seconds, finished=True, succeeded=True, stars=stars)


def test_unlock_and_reward_only_improved_stars_survive_reload(tmp_path):
    store = CareerProgress(tmp_path/'career.json')
    assert not store.available(EVENT_BY_ID['slalom'])
    assert store.record(finished(stars=1))['credits'] == 100
    assert store.record(finished(stars=1))['credits'] == 0
    award = store.record(finished())
    assert award['credits'] == 200
    assert 'club-coupe' in award['vehicles']
    assert '新车：BMW 1M Coupé' in award['unlocked']
    assert '零件：运动前轮' in award['unlocked']
    assert store.record(finished())['vehicles'] == ()
    assert store.available(EVENT_BY_ID['slalom'])
    restored = CareerProgress(store.path)
    assert restored.stars == 3 and restored.credits == 300
    assert restored.recommended().id == 'parking'


def test_purchase_once_ownership_and_money_preserved_on_write_failure(tmp_path, monkeypatch):
    store = CareerProgress(tmp_path/'career.json')
    store.record(finished())
    store.record(finished('parking', 3))
    assert store.buy(PARTS[0]) and store.credits == 250
    assert store.buy(PARTS[0]) and store.credits == 250
    before = store.path.read_bytes()

    def fail(self, target):
        raise OSError('测试只读')

    monkeypatch.setattr(Path, 'replace', fail)
    assert not store.buy(PARTS[1])
    assert store.credits == 250 and PARTS[1].id not in store.owned
    assert store.path.read_bytes() == before


def test_all_parts_unlock_in_steps_and_full_career_can_afford_them_once(tmp_path):
    store = CareerProgress(tmp_path/'career.json')
    awards = []
    for event in EVENT_BY_ID.values():
        awards.append(store.record(finished(event.id)))
    assert store.stars == 18 and store.credits == 2460
    assert {name for award in awards for name in award['unlocked'] if name.startswith('零件：')} == {
        '零件：'+part.name for part in PARTS}
    for part in PARTS:
        assert store.buy(part)
    credits = store.credits
    assert credits == 1010
    for part in PARTS:
        assert store.buy(part) and store.credits == credits
    reloaded = CareerProgress(store.path)
    assert reloaded.owned == {part.id for part in PARTS} and reloaded.credits == credits


def test_corrupt_save_and_locked_or_incomplete_results_cannot_overwrite(tmp_path):
    path = tmp_path/'career.json'
    path.write_text('old-invalid-file', encoding='utf-8')
    store = CareerProgress(path)
    assert not store.record(finished())['saved']
    assert path.read_text() == 'old-invalid-file'
    normal = CareerProgress(tmp_path/'new.json')
    assert normal.record(finished('coastal-cup'))['credits'] == 0
    assert normal.record(replace(finished(), finished=False))['credits'] == 0
    assert not normal.path.exists()


def test_recommendation_stays_available_if_further_chapters_locked(tmp_path):
    store = CareerProgress(tmp_path/'career.json')
    for event in ('first-drive', 'parking', 'slalom'):
        store.record(finished(event, 1))
    assert store.available(store.recommended())
    assert store.recommended().chapter == 0


def test_new_course_keeps_earned_unlocks_and_legacy_time_but_records_new_medals(tmp_path):
    store = CareerProgress(tmp_path/'career.json')
    for event in EVENT_BY_ID.values():
        store.record(finished(event.id))
    legacy = {'stars': 3, 'seconds': 23.}
    records = dict(store.records, **{'coast-sprint': legacy})
    assert store.save(records, store.owned, store.credits)
    before, credits = store.path.read_bytes(), store.credits
    event = EVENT_BY_ID['coast-sprint']
    assert store.course_record(event) is None and store.stars == 18
    assert store.path.read_bytes() == before
    award = store.record(replace(finished(event.id, 1), elapsed=80.))
    assert award['credits'] == 0 and store.credits == credits and store.stars == 18
    assert store.records[event.id]['previous_course'] == legacy
    assert store.course_record(event) == {'stars': 1, 'seconds': 80.}
    store.record(replace(finished(event.id, 3), elapsed=54.))
    assert store.course_record(event) == {'stars': 3, 'seconds': 54.}
    restored = CareerProgress(store.path)
    assert restored.course_record(event) == store.course_record(event)
    assert restored.records[event.id]['previous_course'] == legacy


def test_first_drive_has_no_entry_speed_failure_and_parking_requires_rest():
    config = vehicle_design('reference-rwd').config
    run = CareerRun('first-drive', 8., config)
    result = run.update(408., 25., lateral=0., heading=0., speed=30., collisions=0, reset=False)
    assert result.succeeded and result.stars == 3
    parking = CareerRun('parking', 8., config)
    for tick in range(59):
        result = parking.update(208., 20.+tick/120, lateral=0., heading=0., speed=0., collisions=0, reset=False)
        assert not result.finished
    result = parking.update(208., 20.5, lateral=0., heading=0., speed=0., collisions=0, reset=False)
    assert result.succeeded and result.stars == 3


def test_missed_slalom_gate_continues_and_reset_never_awards():
    config = vehicle_design('reference-rwd').config
    run = CareerRun('slalom', 8., config)
    first = run.update(149., 15., lateral=0., heading=0., speed=10., collisions=0, reset=False)
    assert first.passed == (False,) and not first.finished
    result = run.update(150., 15.1, lateral=0., heading=0., speed=0., collisions=0, reset=True)
    assert result.finished and not result.succeeded and result.stars == 0
