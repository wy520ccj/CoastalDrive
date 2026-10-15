"""虚功/储能/耗散独立对照、原始边界拒绝与实际工程配置往返。"""

import copy
import json
from dataclasses import asdict

import pytest
from physics.fit_suspension_bench import calibrate
from suspension_bench_reference import document, write_bench

from suspension_bench import fit_bench, record_coverage, source_note, validate_metadata
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import config_from_document, grouped_parameters


def test_distinct_spring_and_damper_ratios_preserve_work_energy_and_heat():
    config, report = fit_bench(document(), REFERENCE_DESIGN)
    assert report["passed"]
    assert config.suspension_spring_rates == pytest.approx((38400., 38400., 40500., 40500.))
    assert config.suspension_compression_damping == pytest.approx((3375., 3375., 3612.5, 3612.5))
    assert config.suspension_extension_damping == pytest.approx((1687.5, 1687.5, 1806.25, 1806.25))
    # 独立从真实部件端口计算虚功，不能只重复平方换算的代码。
    q, dq, rs, rd = .04, 1e-6, .8, .75
    energy = lambda displacement: .5*60000*(rs*displacement)**2
    force = (energy(q+dq)-energy(q-dq))/(2*dq)
    assert force == pytest.approx(config.suspension_spring_rates[0]*q, rel=1e-10)
    assert energy(q) == pytest.approx(.5*config.suspension_spring_rates[0]*q*q)
    for speed, rate, wheel_rate in ((.3, 6000., config.suspension_compression_damping[0]),
                                   (-.3, 3000., config.suspension_extension_damping[0])):
        piston_speed = rd*speed
        component_power = rate*piston_speed*piston_speed
        assert component_power == pytest.approx(wheel_rate*speed*speed)
        assert component_power > 0
    assert config.mass == REFERENCE_DESIGN.mass
    assert config.unsprung_enabled is REFERENCE_DESIGN.unsprung_enabled


def test_validation_cannot_change_fitted_rates_or_export_bad_candidate(tmp_path):
    good_config, _ = fit_bench(document(), REFERENCE_DESIGN)
    bad_config, report = fit_bench(document(bad_validation=True), REFERENCE_DESIGN)
    assert not report["passed"]
    assert bad_config == good_config
    base = {"schema": "vehicle-engineering-v1", "parameters": grouped_parameters(REFERENCE_DESIGN)}
    assert not calibrate(write_bench(tmp_path/"bad.json", bad_validation=True), tmp_path/"rejected", base)
    assert not (tmp_path/"rejected/candidate-vehicle.json").exists()
    assert json.loads((tmp_path/"rejected/fit-report.json").read_text(encoding="utf-8"))["passed"] is False


def test_progressive_or_biased_spring_cannot_be_claimed_as_linear_fit():
    progressive = document()
    for row in progressive["corners"]["FL"]["rows"]:
        if row["kind"] == "spring": row["force_N"] *= (row["input"]/.1)**2
    _, report = fit_bench(progressive, REFERENCE_DESIGN)
    assert report["passed"] is False
    assert report["results"]["FL"]["spring"]["checks"]["train"]["normalized_peak"] > .1
    biased = document()
    for row in biased["corners"]["FL"]["rows"]:
        if row["kind"] == "spring": row["force_N"] += 3000
    assert fit_bench(biased, REFERENCE_DESIGN)[1]["passed"] is False


@pytest.mark.parametrize("mutation", ("units", "ratio", "nan", "series", "sign", "preload", "short", "unknown", "coverage"))
def test_ambiguous_or_invalid_component_data_is_rejected(mutation):
    data = document()
    corner = data["corners"]["FL"]
    if mutation == "units": data["units"]["spring_input"] = "mm"
    elif mutation == "ratio": corner["spring_motion_ratio"] = 0
    elif mutation == "nan": corner["damper_motion_ratio"] = float("nan")
    elif mutation == "series": corner["rows"][-1]["series"] = corner["rows"][-7]["series"]
    elif mutation == "sign": corner["rows"][-1]["force_N"] *= -1
    elif mutation == "preload": data["definition"] = "installed_preloaded_spring"
    elif mutation == "short": corner["rows"] = corner["rows"][:-4]
    elif mutation == "unknown": corner["variable_ratio"] = True
    elif mutation == "coverage":
        for row in corner["rows"]:
            if row["split"] == "validation": row["input"] *= .1
    with pytest.raises((ValueError, TypeError)):
        fit_bench(data, REFERENCE_DESIGN)


def test_report_is_recomputed_and_source_is_released_after_override(tmp_path):
    base = {"schema": "vehicle-engineering-v1", "parameters": grouped_parameters(REFERENCE_DESIGN)}
    assert calibrate(write_bench(tmp_path/"input.json"), tmp_path/"accepted", base)
    output = json.loads((tmp_path/"accepted/candidate-vehicle.json").read_text(encoding="utf-8"))
    config = config_from_document(output, REFERENCE_DESIGN)
    metadata = output["metadata"]
    validate_metadata(metadata)
    field = "suspension_spring_rates"
    assert "非实测" in source_note(metadata, field, config.suspension_spring_rates, asdict(config))
    assert "已覆盖" in source_note(metadata, field, (1, 2, 3, 4), asdict(config))
    assert source_note(metadata, "mass", config.mass, asdict(config)) is None
    tampered = copy.deepcopy(metadata)
    tampered["suspension_calibration"]["parameters"][field][0] *= 1.1
    with pytest.raises(ValueError, match="原始数据"):
        validate_metadata(tampered)
    assert asdict(config)[field] == pytest.approx((38400., 38400., 40500., 40500.))


def test_record_reports_actual_component_domain_without_clipping_or_inventing_missing_values():
    config, report = fit_bench(document(), REFERENCE_DESIGN)
    metadata = {"suspension_calibration": report}
    rows = [{**{f"travel_{wheel}": .04 for wheel in ("fl", "fr", "rl", "rr")},
             **{f"travel_rate_{wheel}": 2. for wheel in ("fl", "fr", "rl", "rr")}}]
    coverage = record_coverage(metadata, asdict(config), rows)
    assert coverage["corners"]["FL"]["spring"]["status"] == "within_sampled_domain"
    assert coverage["corners"]["FL"]["compression"]["status"] == "outside_bench_domain"
    assert coverage["corners"]["FL"]["compression"]["sampled_input_domain"] == [1.5, 1.5]
    assert coverage["corners"]["FL"]["extension"]["status"] == "not_excited"
    assert record_coverage(metadata, asdict(config), [{}])["corners"]["FL"]["spring"]["status"] == "missing_observation"
    changed = asdict(config)
    changed["suspension_spring_rates"] = [1, 2, 3, 4]
    assert record_coverage(metadata, changed, rows)["corners"]["FL"]["spring"]["status"] == "overridden"
    assert record_coverage(None, asdict(config), rows) is None
