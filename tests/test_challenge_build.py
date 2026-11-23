"""正式方案边界、预算释放和关联硬件的一致性。"""

from dataclasses import asdict, replace

import pytest

from challenge_build import ALL_PARAMETERS, HARDWARE, BuildDraft
from vehicle_designs import DESIGN_VEHICLES, REFERENCE_DESIGN


def test_prices_and_combined_budget_match_final_absolute_changes():
    draft = BuildDraft(power=1.1, front_tire=1.15, rear_tire=1.15,
                       final_drive=1.075, springs=1.125)
    assert draft.costs() == {'power': 2250, 'mass': 0, 'drag': 0, 'front_tire': 750,
                            'rear_tire': 750, 'brakes': 0, 'springs': 570, 'dampers': 0, 'final_drive': 680}
    assert draft.cost == 5000
    assert replace(draft, power=1.).cost == 2750
    assert BuildDraft().cost == 0
    assert BuildDraft(brake_share=.7, antiroll_share=.3).cost == 0


@pytest.mark.parametrize('item', HARDWARE, ids=lambda item: item.key)
def test_cost_is_monotone_reversible_and_does_not_round_an_exact_ceiling_up(item):
    endpoint = item.minimum if item.minimum < 1. and item.maximum == 1. else item.maximum
    values = [1+(endpoint-1)*n/20 for n in range(21)]
    prices = [BuildDraft(**{item.key: round(value, 8)}).cost for value in values]
    assert prices == sorted(prices)
    assert prices[-1] == item.maximum_cost
    assert BuildDraft(**{item.key: 1.}).cost == 0


@pytest.mark.parametrize('key,value', [('power', True), ('power', float('nan')),
    ('mass', float('inf')), ('power', 1.201), ('front_tire', .69),
    ('brake_share', .81), ('antiroll_share', 0.)])
def test_invalid_parameters_fail_at_input_boundary(key, value):
    with pytest.raises(ValueError):
        BuildDraft(**{key: value})


def test_fixed_original_regeneration_preserves_physics_and_prevents_stacking():
    for design in DESIGN_VEHICLES:
        base = design.config
        original = asdict(base)
        assert BuildDraft().build(base) is base
        draft = BuildDraft(power=1.1, mass=.96, front_tire=1.15, rear_tire=.85, drag=.94)
        first = draft.build(base)
        assert first == draft.build(base) and asdict(base) == original
        assert first.mass == base.mass*.96
        assert first.body_inertia == tuple(value*.96 for value in base.body_inertia)
        assert first.wheel_inertia == base.wheel_inertia
        assert first.downstream_inertias == base.downstream_inertias
        assert first.road_friction == base.road_friction
        assert first.rolling_coefficient == base.rolling_coefficient
        assert first.max_speed == base.max_speed
        assert first.collision_half_width == base.collision_half_width
        assert first.torque_curve == tuple((rpm, torque*1.1) for rpm, torque in base.torque_curve)


def test_free_setup_and_nonlinear_suspension_preserve_real_component_relationships():
    curves = (((-.5, -1500.), (-.2, -900.), (-.05, -250.), (0., 0.),
               (.05, 400.), (.2, 1300.), (.5, 2400.)),)*4
    base = replace(REFERENCE_DESIGN, unsprung_enabled=True, suspension_coil_enabled=True,
                   suspension_damper_curves=curves,
                   suspension_spring_preloads=(100., 200., 300., 400.))
    result = BuildDraft(springs=1.1, dampers=.9, brake_share=.65, antiroll_share=.3).build(base)
    assert result.suspension_spring_preloads == pytest.approx((110., 220., 330., 440.))
    assert result.suspension_damper_curves[0][-2] == pytest.approx((.2, 1170.))
    assert result.suspension_installation_curves == base.suspension_installation_curves
    assert sum(result.suspension_antiroll_rates) == pytest.approx(sum(base.suspension_antiroll_rates))
    assert result.front_brake_share == .65


def test_allowed_parameters_are_enforced_even_for_free_setup():
    assert BuildDraft(power=1.1).build(REFERENCE_DESIGN, allowed=('power',)).torque_curve
    with pytest.raises(ValueError, match='本关不可修改'):
        BuildDraft(brake_share=.65).build(REFERENCE_DESIGN, allowed=('power',))
    with pytest.raises(ValueError, match='未知'):
        BuildDraft().build(REFERENCE_DESIGN, allowed=(*ALL_PARAMETERS, 'road_friction'))

