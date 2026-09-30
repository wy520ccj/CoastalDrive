import csv
import json

import pytest
from physics.testbed import CASES, _run_case, _wheel_surface_types, _world, compare, run

from vehicle import Vehicle
from vehicle_state import FIXED_DT, Control


def test_same_case_reproduces_summary_and_samples(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = _run_case("steering_step", first_dir)
    second = _run_case("steering_step", second_dir)
    assert first == second
    assert (first_dir / "steering_step.csv").read_bytes() == (second_dir / "steering_step.csv").read_bytes()


def test_steering_step_produces_yaw(tmp_path):
    result = _run_case("steering_step", tmp_path)
    assert abs(result["yaw_change_deg"]) > 0.1


def test_split_mu_assigns_different_surfaces_to_each_side():
    world = _world()
    vehicle = Vehicle(world, lambda x, y: x < 0, (0, 0, 0.55), reverse_enabled=False)
    try:
        for _ in range(240):
            previous = vehicle._chassis.getLinearVelocity()
            vehicle.apply_control(Control())
            world.doPhysics(FIXED_DT, 4, FIXED_DT)
            vehicle.after_step(previous)
        surfaces = _wheel_surface_types(vehicle)
        assert surfaces.count("asphalt") == 2
        assert surfaces.count("grass") == 2
        for wheel in vehicle._vehicle.getWheels():
            x = wheel.getRaycastInfo().getContactPointWs().x
            assert wheel.getFrictionSlip() == pytest.approx(1.4 if x < 0 else 0.8)
    finally:
        vehicle.close()


def test_report_records_exact_tick_rate_inputs_and_split_mu(tmp_path):
    report = run(tmp_path / "trial", CASES)
    assert report["physics_hz"] == 120
    assert report["fixed_dt_s"] == 1 / 120
    assert report["commands"]["steering_step"].startswith("40 km/h initial; coast 0.5 s")
    assert report["environment"]["split_mu_boundary_x_m"] == 0
    assert len(report["summaries"]) == 7
    saved = json.loads((tmp_path / "trial" / "summary.json").read_text(encoding="utf-8"))
    assert saved["physics_hz"] == 120
    for summary in saved["summaries"]:
        assert summary["ticks"] == round(summary["duration_s"] / FIXED_DT)
        assert summary["sample_stride_ticks"] == 6
    with (tmp_path / "trial" / "steering_step.csv").open(encoding="utf-8", newline="") as stream:
        samples = list(csv.DictReader(stream))
    assert float(samples[0]["time_s"]) == 6 * FIXED_DT
    assert int(samples[0]["tick"]) == 6
    assert float(samples[0]["time_s"]) == int(samples[0]["tick"]) * FIXED_DT
    assert "wheel0.position.0" in samples[0]
    assert "state.dynamics.yaw_rate" in samples[0]
    assert "input.steering" in samples[0]


def test_compare_allows_parameter_changes_and_rejects_condition_changes(tmp_path):
    run(tmp_path / "base", ("steering_step",), label="A")
    baseline = json.loads((tmp_path / "base" / "summary.json").read_text(encoding="utf-8"))
    candidate = json.loads(json.dumps(baseline))
    candidate["source_version"] = "B"
    candidate["config"]["road_grip"] += 0.1
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    result = compare(tmp_path / "base" / "summary.json", candidate_path)
    assert result["config_delta_candidate_minus_baseline"]["road_grip"] == pytest.approx(0.1)

    candidate["environment"]["gravity_mps2"][2] = -9.8
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    with pytest.raises(ValueError, match="environment"):
        compare(tmp_path / "base" / "summary.json", candidate_path)
