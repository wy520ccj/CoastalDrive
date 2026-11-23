"""同次联合达标、预算资格和固定路线油耗边界。"""

from dataclasses import replace

import pytest

from challenge_build import BuildDraft
from challenge_rules import ChallengeSpec, EnergyWindow, MedalTarget
from vehicle_designs import GAME_DESIGN

SPEC = ChallengeSpec('sample', '测试路线', GAME_DESIGN, 1000., 5000,
                     targets=(MedalTarget('铜', 90., 10.), MedalTarget('银', 75., 8.2),
                              MedalTarget('金', 65., 7.)))


@pytest.mark.parametrize('seconds,litres,medal,gaps', [
    (60., .074, '银', (0., .4)), (72., .065, '银', (7., 0.)),
    (64., .069, '金', None), (65., .07, '金', None),
    (65.00001, .07, '银', (.00001, 0.)), (100., .06, '', (10., 0.)),
])
def test_joint_medal_and_feedback_never_trade_one_metric_for_another(seconds, litres, medal, gaps):
    result = SPEC.evaluate(BuildDraft(), seconds, litres)
    assert result.medal == medal and result.official
    assert result.gaps == (pytest.approx(gaps) if gaps is not None else None)


def test_overbudget_trial_missing_sensor_and_invalid_run_never_award():
    trial = SPEC.evaluate(BuildDraft(power=1.2), 50., .05)
    assert trial.valid and not trial.official and not trial.medal
    assert '试验' in trial.notice
    missing = SPEC.evaluate(BuildDraft(), 50., None)
    assert not missing.official and missing.consumption is None and not missing.medal
    failed = SPEC.evaluate(BuildDraft(), 50., .05, valid=False, reason='漏门')
    assert failed.notice == '漏门' and not failed.official and not failed.medal


def test_fixed_distance_ignores_extra_driving_and_freezes_at_actual_finish_fraction():
    window = EnergyWindow(.1, 1000.)
    window.sample(.11, 40.)
    assert window.consumption is None
    window.sample(.12, 500.)
    assert window.consumption == pytest.approx(4.)
    window.sample(.13, 400.)
    assert window.consumption == pytest.approx(6.)
    window.sample(.17, 1000., finish_fraction=.5)
    assert window.litres == pytest.approx(.05)
    assert window.consumption == pytest.approx(5.)
    window.sample(.3, 3000.)
    assert window.litres == pytest.approx(.05)
    assert window.remaining_allowance(SPEC.targets[-1]) == pytest.approx(.02)


def test_illegal_telemetry_and_cross_world_reset_are_not_silent_zero_consumption():
    window = EnergyWindow(.1, 1000.)
    window.sample(.2, 500.)
    with pytest.raises(ValueError, match='倒退'):
        window.sample(0., 0.)
    with pytest.raises(ValueError):
        SPEC.evaluate(BuildDraft(), 60., float('nan'))
    with pytest.raises(ValueError):
        SPEC.evaluate(BuildDraft(), 0., .1)
    with pytest.raises(ValueError, match='不能放宽'):
        replace(SPEC, targets=(*SPEC.targets[:2], MedalTarget('金', 100., 7.)))


def test_unmeasured_targets_do_not_manufacture_medals():
    result = replace(SPEC, targets=()).evaluate(BuildDraft(), 50., .05)
    assert result.official and not result.medal and '标定中' in result.notice


def test_bend_targets_are_joint_and_award_current_medals():
    from challenge_catalog import SPRINT_CHALLENGES
    from race import GameMode

    spec = SPRINT_CHALLENGES[GameMode.BEND_SPRINT]
    result = spec.evaluate(BuildDraft(front_tire=1.3), 95.6, 20.1*spec.distance_m/100_000)
    assert result.medal == '金' and result.official and result.notice == '金牌完成'
    slow = spec.evaluate(BuildDraft(), 95.7, 19.*spec.distance_m/100_000)
    thirsty = spec.evaluate(BuildDraft(), 90., 20.2*spec.distance_m/100_000)
    assert slow.medal == thirsty.medal == '银'
    assert not spec.evaluate(BuildDraft(power=1.2), 90., .3).official
    with pytest.raises(ValueError, match='试行标记'):
        replace(spec, targets=(), provisional=True)
