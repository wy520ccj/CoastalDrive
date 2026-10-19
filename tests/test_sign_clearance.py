"""隔音屏重叠区的牌面布置；原设施数量、里程和非目标横坐标保持。"""

import pytest

from environment import expressway_route
from environment.expressway_route import positions, sign_lateral
from highway_curve import HighwayCurve


def test_reported_seed23_warning_is_in_front_of_soundwall():
    items = positions(10, 23, HighwayCurve(23, hills=True))
    warning = next(item for item in items if item[0] == 'curve-left' and item[2] == 2050)
    assert warning[1] == 8.8
    walls = [item for item in items if item[0] == 'soundwall' and 2048 <= item[2] <= 2052]
    assert len(walls) == 2 and all(item[1] == 10.4 for item in walls)
    assert 10.4-.24-(warning[1]+.98) >= .3


@pytest.mark.parametrize('local,expected', [(518, 10.4), (519, 8.8), (520, 8.8), (980, 8.8), (981, 8.8), (982, 10.4)])
def test_screen_end_and_start_include_panel_thickness(local, expected):
    # seed23的第一屏障区以1120米为局部零点。
    assert sign_lateral('curve-left', 10.4, 1120+local, 23) == expected


def test_only_overlapping_small_sign_offsets_change(monkeypatch):
    changed = 0
    for seed in (0, 17, 23):
        for curve in (None, HighwayCurve(seed), HighwayCurve(seed, hills=True)):
            for index in range(80):
                actual = positions(index, seed, curve)
                with monkeypatch.context() as context:
                    context.setattr(expressway_route, 'sign_lateral', lambda model, lateral, s, seed: lateral)
                    original = positions(index, seed, curve)
                assert len(actual) == len(original)
                for after, before in zip(actual, original, strict=True):
                    assert (after[0], after[2:]) == (before[0], before[2:])
                    if after[1] != before[1]:
                        assert after[0] in ('speed-limit', 'curve-left', 'curve-right', 'hill-warning') and after[1] == 8.8
                        changed += 1
    assert changed > 0
