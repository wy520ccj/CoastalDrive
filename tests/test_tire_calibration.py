"""标定可辨识性、独立公式参数恢复和留出不通过时禁止候选。"""

import csv
import json
import math

import pytest
from physics.fit_tire_bench import calibrate
from tire_bench_reference import TRUTH, write_bench

from lab_experiment import LabExperiment, LabOptions
from lab_records import LabRecord, recalculate
from tire_calibration import FIELDS, PARAMETERS, fit_tire, load_bench, validate_fit_metadata
from tire_compliance import contact_force
from tire_properties import tire_grip, tire_stiffness
from vehicle_designs import vehicle_design
from vehicle_parameters import config_from_document
from wheel_dynamics import _solve_force


@pytest.mark.parametrize("noise", (0., 3.))
def test_independent_equations_recover_identifiable_parameters(tmp_path, noise):
    paths = write_bench(tmp_path, noise_N=noise)
    config, report = fit_tire(load_bench(*paths), vehicle_design("reference-rwd").config)
    assert report["passed"] and report["rank"] == 6
    for key in PARAMETERS:
        assert report["parameters"][key] == pytest.approx(TRUTH[key], rel=.005)
    assert config.rear_lateral_stiffness == config.lateral_stiffness
    assert config.tire_reference_load == 2943.
    assert report["data_domain"]["train"]["fz_N"] == [2000., 5000.]


def test_whole_series_split_prevents_train_validation_leakage(tmp_path):
    csv_path, conditions = write_bench(tmp_path)
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[1]["split"] = "validation"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="同一试验序列"):
        load_bench(csv_path, conditions)


def test_combined_holdout_failure_is_not_fitted_away_or_exported_as_candidate(tmp_path):
    valid = write_bench(tmp_path/"valid")
    invalid = write_bench(tmp_path/"invalid", invalid_combined=True)
    _, good = fit_tire(load_bench(*valid), vehicle_design("reference-rwd").config)
    _, bad = fit_tire(load_bench(*invalid), vehicle_design("reference-rwd").config)
    assert good["parameters"] == bad["parameters"]
    assert good["passed"] and not bad["passed"]
    assert not calibrate(*invalid, tmp_path/"rejected", "reference-rwd")
    assert not (tmp_path/"rejected/candidate-vehicle.json").exists()
    assert json.loads((tmp_path/"rejected/fit-report.json").read_text())["passed"] is False


def test_trial_conditions_do_not_claim_camber_or_transient_identification(tmp_path):
    csv_path, conditions = write_bench(tmp_path)
    payload = json.loads(conditions.read_text())
    payload["camber_rad"] = .02
    conditions.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="外倾推力"):
        load_bench(csv_path, conditions)


def test_malformed_calibration_scope_is_rejected_at_file_boundary(tmp_path):
    _, report = fit_tire(load_bench(*write_bench(tmp_path)), vehicle_design("reference-rwd").config)
    report["data_domain"]["train"]["fz_N"] = ["invalid load", 5000.]
    with pytest.raises(ValueError, match="数据范围"):
        validate_fit_metadata({"tire_calibration": report})


def test_fitted_engineering_config_enters_actual_solver_and_exact_record_recalculation(tmp_path):
    csv_path, conditions = write_bench(tmp_path/"bench")
    assert calibrate(csv_path, conditions, tmp_path/"accepted", "reference-rwd")
    document = json.loads((tmp_path/"accepted/candidate-vehicle.json").read_text(encoding="utf-8"))
    config = config_from_document(document, vehicle_design("reference-rwd").config)
    run = LabExperiment(LabOptions(speed_kph=60, friction=config.road_friction, duration=.25),
                        config=config, parameter_metadata=document["metadata"])
    try:
        while not run.done:
            run.step()
        record = LabRecord.from_run(run)
        assert record.metadata["vehicle_config"]["longitudinal_stiffness"] == config.longitudinal_stiffness
        assert "合成" in record.metadata["model_basis"]
        repeated = recalculate(record)
        assert repeated.samples == record.samples and repeated.snapshots == record.snapshots
        assert repeated.metadata["parameter_metadata"] == record.metadata["parameter_metadata"]
        document["metadata"]["basis"] = "后来编辑的来源"
        assert "合成" in record.metadata["parameter_metadata"]["basis"]
        wheel = run.current.player.wheel_dynamics[0]
        expected = config.longitudinal_stiffness*(wheel.normal_load/config.tire_reference_load)**config.longitudinal_load_exponent
        assert wheel.force_longitudinal_stiffness == pytest.approx(expected, rel=1e-12)
    finally:
        run.close()


@pytest.mark.parametrize("load,axis", ((2750., 0), (2750., 1), (4500., 0), (4500., 1)))
def test_fitted_stiffness_keeps_analytic_transient_relaxation_in_actual_contact_kernel(tmp_path, load, axis):
    config, report = fit_tire(load_bench(*write_bench(tmp_path)), vehicle_design("reference-rwd").config)
    assert report["passed"]
    coefficient = tire_stiffness(load, config)[axis]
    speed, h, slip = 20., 1/240, [0., 0.]
    slip[axis] = .00002
    prior = (0., 0.)
    tau = (coefficient/speed+config.tire_contact_damping)/config.tire_contact_stiffness
    initial = config.tire_contact_damping*slip[axis]/(1+config.tire_contact_damping*speed/coefficient)
    final = coefficient*slip[axis]/speed
    grip, (cx, cy) = tire_grip(load, config.road_friction, config), tire_stiffness(load, config)
    for tick in range(1, 81):
        def residual(fx, fy, previous=prior):
            target, *_ = contact_force((fx, fy), previous, slip, speed, True, grip, cx, cy, h,
                                       config.tire_contact_stiffness, config.tire_contact_damping,
                                       config.tire_shape, config.tire_curvature)
            return fx-target[0], fy-target[1]
        fx, fy, error = _solve_force(residual)
        _, prior, *_ = contact_force((fx, fy), prior, slip, speed, True, grip, cx, cy, h,
                                     config.tire_contact_stiffness, config.tire_contact_damping,
                                     config.tire_shape, config.tire_curvature)
        expected = final+(initial-final)/(1+h/tau)**tick
        assert (fx, fy)[axis] == pytest.approx(expected, abs=2e-8)
        assert math.isfinite(error) and error < .001
