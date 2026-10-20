"""制动对照使用整次结束记录，独立文件和同指标差值边界。"""

from dataclasses import replace
from unittest.mock import patch

import pytest
from test_player_road_ab import attempt as tire_attempt

from braking_lesson import BrakingResult
from player_road_ab import PlayerRoadAB, checked_record, mismatches, record
from workshop import build_config


def config(index):
    return replace(build_config(index, False), tire_substeps=1)


def attempt(index=0, *, short=True, succeeded=True, distance=39., error=-8., source='same'):
    context = {'mode': 'short_braking' if short else 'braking_lesson', 'driving_mode': 'game',
               'input': {'progressive_pedals': True}, 'world': {'source': source}}
    from braking_lesson import medal_for
    from short_braking import medal_for as short_medal
    result = BrakingResult(short=short, finished=True, succeeded=succeeded, entry_kph=84., hold_seconds=1.,
        position=100+distance if short else 170+error, stopping_m=distance if short else None,
        error_m=None if short else error, medal=(short_medal(distance) if short else medal_for(abs(error))) if succeeded else '',
        reason='完成' if succeeded else '驶离验车带')
    return record(context, context, config(index), result)


@pytest.mark.parametrize('short', [False, True])
def test_brake_a_fixed_latest_b_even_failure_and_independent_tire_file(tmp_path, short):
    tires = PlayerRoadAB(tmp_path/'tire.json')
    tires.freeze(tire_attempt(0), config(0))
    original = tires.path.read_bytes()
    path = tmp_path/'brake.json'
    ab = PlayerRoadAB(path, brakes=True)
    a = attempt(short=short)
    assert ab.freeze(a, config(2))
    b = attempt(2, short=short, distance=35., error=2.)
    assert ab.observe(b) and ab.a == a and not mismatches(a, b)
    failed = attempt(2, short=short, succeeded=False)
    assert ab.observe(failed) and ab.b == failed and ab.a == a
    loaded = PlayerRoadAB(path, brakes=True)
    assert (loaded.a, loaded.b, loaded.target) == (ab.a, ab.b, ab.target)
    old = path.read_bytes()
    assert not ab.observe(attempt(1, short=short))
    assert not ab.observe(attempt(2, short=not short))
    assert path.read_bytes() == old and tires.path.read_bytes() == original
    assert PlayerRoadAB(path).blocked


@pytest.mark.parametrize('field,value', [('short', False), ('hold_seconds', .5), ('entry_kph', 85.1),
    ('entry_kph', None), ('stopping_m', float('nan')), ('stopping_m', 38.), ('position', float('inf')), ('medal', '金')])
def test_invalid_success_cannot_be_loaded_as_road_evidence(field, value):
    a = attempt()
    a['result'][field] = value
    with pytest.raises((ValueError, TypeError)):
        checked_record(a)


def test_braking_conditions_and_other_hardware_checked_separately():
    a, b = attempt(), attempt(2, source='different')
    assert len(mismatches(a, b)) == 1
    b['config']['brake_torque'] += 100
    assert len(mismatches(a, b)) == 2
    b['context'] = a['context']
    assert mismatches(a, b) == ['除制动分配外的硬件或路面不同']


def test_a_write_failure_blocks_old_target_b_and_b_failure_can_retry(tmp_path):
    path = tmp_path/'brake.json'
    ab = PlayerRoadAB(path, brakes=True)
    assert ab.freeze(attempt(), config(2))
    before = path.read_bytes()
    with patch('pathlib.Path.replace', side_effect=OSError('只读')):
        assert not ab.observe(attempt(2))
    assert path.read_bytes() == before and ab.b is None
    assert ab.observe(attempt(2))
    before, pair = path.read_bytes(), (ab.a, ab.b)
    with patch('pathlib.Path.replace', side_effect=OSError('只读')):
        assert not ab.freeze(attempt(1), config(2))
    assert not ab.observe(attempt(2)) and ab.capture_blocked
    assert path.read_bytes() == before and (ab.a, ab.b) == pair


def test_wrong_store_and_bad_original_remain_intact(tmp_path):
    ab = PlayerRoadAB(tmp_path/'brake.json', brakes=True)
    with pytest.raises(ValueError):
        ab.freeze(tire_attempt(0), config(2))
    ab.path.write_text('{', encoding='utf-8')
    ab = PlayerRoadAB(ab.path, brakes=True)
    assert ab.blocked and not ab.freeze(attempt(), config(2))
    assert ab.path.read_text(encoding='utf-8') == '{'
