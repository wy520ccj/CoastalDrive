"""同一轮胎数据与车辆质量解耦，实际轮荷仍进入全部力学特性。"""

import math
from dataclasses import replace

import pytest

from lab_experiment import LabExperiment, LabOptions
from tire_forces import tire_force
from tire_properties import tire_grip, tire_stiffness
from vehicle_config import CAR
from vehicle_designs import GR86_DESIGN
from vehicle_parameters import load_vehicle_config, save_vehicle_config


@pytest.mark.parametrize("load", (800., 2943., 4000., 6000.))
def test_identical_tire_curve_at_same_load_does_not_depend_on_car_mass(load):
    cars = [replace(CAR, mass=mass) for mass in (800., 1200., 1800.)]
    for kappa, alpha in ((0., 0.), (.000001, 0.), (0., .000001), (.15, 0.), (.1, .2)):
        expected = tire_force(kappa, alpha, load, 1.1, cars[0])
        assert all(tire_force(kappa, alpha, load, 1.1, car) == expected for car in cars)


def test_payload_load_preserves_sublinear_grip_and_stiffness_increase():
    ratio = 1.5
    loaded = replace(CAR, mass=CAR.mass * ratio)
    load = loaded.mass * 9.81 / 4
    assert tire_grip(load, 1.1, loaded) == pytest.approx(
        1.1 * CAR.tire_reference_load * ratio ** CAR.tire_peak_load_exponent)
    cx, cy = tire_stiffness(load, loaded)
    assert cx == pytest.approx(CAR.longitudinal_stiffness * ratio ** CAR.longitudinal_load_exponent)
    assert cy == pytest.approx(CAR.lateral_stiffness * ratio ** CAR.lateral_load_exponent)
    assert tire_grip(load, 1.1, loaded) / load < 1.1


@pytest.mark.parametrize("invalid", (0., -10., math.nan, math.inf))
def test_reference_load_boundary_is_explicit(invalid):
    with pytest.raises(ValueError, match="标定轮荷"):
        replace(CAR, tire_reference_load=invalid)


def test_real_profile_preserves_previous_nominal_curve_and_declares_basis():
    assert GR86_DESIGN.tire_reference_load == GR86_DESIGN.mass * 9.81 / 4
    assert tire_stiffness(GR86_DESIGN.tire_reference_load, GR86_DESIGN) == (
        GR86_DESIGN.longitudinal_stiffness, GR86_DESIGN.lateral_stiffness)


def test_fixed_reference_survives_file_round_trip_and_changed_mass(tmp_path):
    config = replace(CAR, mass=1800., tire_reference_load=4100.)
    path = tmp_path / "vehicle.json"
    save_vehicle_config(path, config)
    loaded = load_vehicle_config(path, CAR)
    assert loaded.mass == 1800. and loaded.tire_reference_load == 4100.
    assert tire_force(.12, .2, 3300., 1.1, loaded) == tire_force(.12, .2, 3300., 1.1, config)


def test_lab_override_reaches_actual_tire_solver_and_force_telemetry():
    run = LabExperiment(LabOptions(tire_reference_load=4100., duration=.05))
    try:
        run.paused = False
        run.advance(.001)
        assert run.config.tire_reference_load == 4100.
        for state in run.current.player.wheel_dynamics:
            assert state.normal_load > 0
            assert state.force_grip == pytest.approx(tire_grip(state.normal_load, 1.1, run.config))
    finally:
        run.close()


def test_reference_load_changes_actual_native_vehicle_braking_response():
    speeds = []
    for reference in (2943., 1471.5):
        run = LabExperiment(LabOptions(tire_reference_load=reference, friction=.6, duration=.6))
        try:
            run.paused = False
            while not run.done:
                run.advance(.005)
            speeds.append(run.current.player.speed)
        finally:
            run.close()
    assert speeds[1] > speeds[0]
