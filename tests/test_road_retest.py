"""冻结道路硬件、参考条件分离与取消时唯一世界释放。"""

from dataclasses import asdict

import pytest
from test_brake_road_ab import attempt

from road_retest import RoadRetest, prepare_pair, trial_options


def pair():
    return prepare_pair(attempt(), attempt(2, distance=35.))


def test_pair_is_frozen_and_missing_other_course_rejected():
    a, b = attempt(), attempt(2, distance=35.)
    frozen = prepare_pair(a, b)
    a['config']['mass'] = 999.
    assert frozen['A']['config']['mass'] != 999.
    with pytest.raises(ValueError):
        prepare_pair(a, None)
    with pytest.raises(ValueError):
        prepare_pair(None, b)
    with pytest.raises(ValueError):
        prepare_pair(b, attempt(short=False))


def test_standard_environment_separate_from_saved_hardware_and_electronics():
    source = pair()
    source['A']['config']['road_friction'] = .6
    source['B']['config']['road_friction'] = 1.1
    source['B']['config']['braking']['abs_enabled'] = False
    configs, options = trial_options(source)
    assert configs[0].road_friction == .6 and configs[1].road_friction == 1.1
    assert options[0].friction == options[1].friction == .6
    assert options[0].speed_kph == options[1].speed_kph == 80.
    assert options[0].abs_enabled and not options[1].abs_enabled
    assert options[0] != options[1]
    assert asdict(configs[1])['front_brake_share'] == .7


def test_cancel_preserves_actual_completed_steps_and_restores_without_world(tmp_path):
    result = RoadRetest(pair())
    try:
        result.start()
        run = result.run
        run.step()
        last = run.current
        result.cancel()
        assert run.closed and result.run is None and result.status == 'cancelled'
        assert result.partial.snapshots[-1] == last and len(result.partial.snapshots) == 2
        restored = RoadRetest.restore(result.capture())
        assert restored.run is None and restored.partial.snapshots == result.partial.snapshots
        with pytest.raises(ValueError):
            restored.export(tmp_path/'not-completed')
        assert not (tmp_path/'not-completed').exists()
        result.start()
        assert run.closed and result.run is not run and result.partial is None
    finally:
        result.cancel()
