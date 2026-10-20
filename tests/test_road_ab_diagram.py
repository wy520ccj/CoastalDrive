"""图解使用结束记录原值，同轴覆盖有效、失败与未建立位置。"""

from ui.player_road_diagram import brake_position, brake_range, gate_focus


def gates(*values):
    return {'result': {'clearances': values}}


def brake(position, maximum):
    return {'result': {'position': position, 'stopping_m': maximum}}


def test_gate_focus_uses_first_failed_gate_then_smallest_observed_margin():
    assert gate_focus(gates(.5, .4, -.2), gates(.4, -.1)) == 1
    assert gate_focus(gates(.7, .4), gates(.5, .2, .8)) == 1
    assert gate_focus(gates(.5, .4, -.2), gates(.4, .2, .7, .6, .3, .4)) == 2
    assert gate_focus(None, None) == 0


def test_short_marker_keeps_maximum_forward_distance_even_after_reversal():
    assert brake_position(brake(135., 37.), True) == 37.
    assert brake_position(brake(60., None), True) is None
    assert brake_position(None, True) is None
    assert brake_position(brake(162., None), False) == 162.


def test_common_axis_covers_both_braking_points_and_original_target_lines():
    low, high = brake_range(brake(139., 39.), brake(143., 43.), True)
    assert low == 0 and high >= 43
    low, high = brake_range(brake(60., None), brake(202., None), False)
    assert low <= 60 and high >= 202
    assert all(low <= line <= high for line in (160., 165., 168., 170., 172., 175., 180.))
    assert brake_range(None, None, True) == (0., 42.)
    assert brake_range(None, None, False) == (150., 190.)
