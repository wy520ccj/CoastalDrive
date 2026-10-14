"""延迟制动协议、实际制动基准与凸起前后的共用物理链。"""

import math
from dataclasses import replace

import pytest

from lab_experiment import LabExperiment, LabOptions
from lab_metrics import brake_start_index, mfdd
from vehicle_designs import REFERENCE_DESIGN


def test_mfdd_reference_excludes_coast_speed_and_approach_distance():
    rows,positions = [],[]
    for index in range(481):
        t = index/120
        coast = min(t,1.)
        braking = min(max(t-1.,0.),19./6.7)
        rows.append({"time":t,"horizontal_speed":max(0.,20.-coast-6.7*braking),
                     "brake_request":float(t>1.)})
        positions.append((0.,20*coast-.5*coast**2+19*braking-.5*6.7*braking**2,.1*t))
    result = mfdd(rows,positions,"ride_braking","stopped")
    assert brake_start_index(rows,"ride_braking")==120
    assert result["value"]==pytest.approx(6.7,abs=2e-5)
    assert result["window"]["reference_speed_mps"]==19.
    assert result["window"]["reference_time_s"]==1.
    assert mfdd(rows[:120],positions[:120],"ride_braking","time_limit")["value"] is None


def test_delayed_bump_brake_uses_actual_pressure_and_cg_reference():
    config = replace(REFERENCE_DESIGN,unsprung_enabled=True)
    run = LabExperiment(LabOptions(maneuver="ride_braking",speed_kph=10.,duration=.075,onset=.025),config=config)
    try:
        assert run.command_at(.024).brake==0.
        assert run.command_at(.025).brake==1.
        assert run.command_at(.025).steering==0.
        assert any(body.getName()=="lab-left-bump" for body in run.experiment.simulation._world.getRigidBodies())
        while not run.done:run.step()
        first = next(i for i,r in enumerate(run.samples) if r["brake_request"]>0.)
        assert 0.<run.samples[first]["pressure_fl"]<1.
        summary = run.summary()
        state = run.snapshots[first-1].player.unsprung_state
        assert summary["braking_reference"]["time_s"]==pytest.approx(.025)
        assert summary["braking_reference"]["speed_mps"]==math.hypot(*state.total_center_velocity[:2])
        assert summary["stopping_distance_m"] is None
    finally:run.close()


def test_bump_brake_requires_real_unsprung_model():
    with pytest.raises(ValueError,match="独立轮心"):
        LabExperiment(LabOptions(maneuver="ride_braking"))
