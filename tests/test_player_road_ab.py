"""玩家对照持久化与完整记录边界；结果为明确规则夹具。"""

import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from player_road_ab import PlayerRoadAB, checked_record, mismatches, record
from slalom_lesson import SlalomResult
from workshop_cornering import build_config


def config(index):
    return replace(build_config(index, False, False), tire_substeps=1)


def attempt(index, *, succeeded=False, seconds=11.4, source='same', mode='fast_slalom'):
    context = {'mode': mode, 'driving_mode': 'game', 'input': {'progressive_pedals': True},
               'world': {'source': source, 'bits': 32}}
    result = SlalomResult(fast=mode == 'fast_slalom', finished=True, succeeded=succeeded,
        gates=6 if succeeded else 2, run_seconds=seconds if succeeded else 6.,
        gate_times=(2., 4., 6., 8., 10., seconds) if succeeded else (2., 4., 6.),
        clearances=(.5,)*6 if succeeded else (.5, .4, -.3), reason='完成' if succeeded else '第3门漏门')
    return record(context, context, config(index), result)


def test_a_fixed_and_b_is_latest_whole_attempt_even_when_slower(tmp_path):
    path = tmp_path/'ab.json'
    ab = PlayerRoadAB(path)
    a = attempt(0)
    assert ab.freeze(a, config(3)) and ab.b is None
    first = attempt(3, succeeded=True)
    assert ab.observe(first) and ab.a == a and ab.b == first
    slower = attempt(3, succeeded=True, seconds=12.2)
    assert ab.observe(slower) and ab.b == slower and ab.a == a
    loaded = PlayerRoadAB(path)
    assert loaded.a == a and loaded.b == slower and not loaded.notice
    assert not mismatches(loaded.a, loaded.b)


def test_wrong_course_or_hardware_never_overwrites_stored_b(tmp_path):
    path = tmp_path/'ab.json'
    ab = PlayerRoadAB(path)
    ab.freeze(attempt(0), config(3))
    ab.observe(attempt(3, succeeded=True))
    old = path.read_bytes()
    assert not ab.observe(attempt(2, succeeded=True))
    assert not ab.observe(attempt(3, mode='slalom_lesson', succeeded=True))
    assert path.read_bytes() == old


def test_source_sdk_or_other_hardware_differences_are_reported():
    a, b = attempt(0), attempt(3, source='different')
    assert mismatches(a, b) == ['题目/种子/输入设置/模型或运行库不同']
    b['config']['road_friction'] = .6
    assert len(mismatches(a, b)) == 2
    b['context'] = a['context']
    assert mismatches(a, b) == ['除前胎外的硬件或路面不同']


@pytest.mark.parametrize('key,bad', [('run_seconds', True), ('run_seconds', float('nan')),
                                   ('gates', 7), ('fast', False), ('gate_times', (2., 1., 3.))])
def test_invalid_results_rejected(key, bad):
    value = attempt(0)
    value['result'][key] = bad
    with pytest.raises((ValueError, TypeError)):
        checked_record(value)


def test_incomplete_success_or_changed_source_cannot_create_reference():
    a = attempt(0)
    a['result']['succeeded'] = True
    with pytest.raises(ValueError):
        checked_record(a)
    with pytest.raises(ValueError, match='条件变化'):
        record({'source': 'one'}, {'source': 'two'}, config(0), SlalomResult())


def test_atomic_a_failure_keeps_previous_pair_and_blocks_wrong_followup(tmp_path):
    path = tmp_path/'ab.json'
    ab = PlayerRoadAB(path)
    first = attempt(0)
    ab.freeze(first, config(3))
    ab.observe(attempt(3, succeeded=True))
    old, pair = path.read_bytes(), (ab.a, ab.b)
    with patch('pathlib.Path.replace', side_effect=OSError('只读')):
        assert not ab.freeze(attempt(2), config(3))
    assert ab.capture_blocked and not ab.observe(attempt(3))
    assert path.read_bytes() == old and (ab.a, ab.b) == pair and ab.notice


def test_atomic_b_failure_keeps_old_pair_and_can_retry(tmp_path):
    path = tmp_path/'ab.json'
    ab = PlayerRoadAB(path)
    ab.freeze(attempt(0), config(3))
    previous = path.read_bytes()
    with patch('pathlib.Path.replace', side_effect=OSError('只读')):
        assert not ab.observe(attempt(3))
    assert path.read_bytes() == previous and ab.b is None
    assert ab.observe(attempt(3, succeeded=True)) and not ab.notice


@pytest.mark.parametrize('payload', ['{', '[]', '{"version":"old"}'])
def test_bad_file_preserved_and_cannot_be_silently_replaced(tmp_path, payload):
    path = tmp_path/'ab.json'
    path.write_text(payload, encoding='utf-8')
    ab = PlayerRoadAB(path)
    assert ab.blocked and ab.notice
    assert not ab.freeze(attempt(0), config(3))
    assert path.read_text(encoding='utf-8') == payload


def test_loaded_b_must_match_target_hardware(tmp_path):
    path = tmp_path/'ab.json'
    ab = PlayerRoadAB(path)
    ab.freeze(attempt(0), config(3))
    ab.observe(attempt(3))
    value = json.loads(path.read_text(encoding='utf-8'))
    value['B']['config']['lateral_stiffness'] = 45000.
    path.write_text(json.dumps(value), encoding='utf-8')
    assert PlayerRoadAB(path).blocked
