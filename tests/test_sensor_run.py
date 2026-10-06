"""原生Snapshot采样不改变物理；生命周期与坐标重定位明确处理。"""

from dataclasses import replace

import numpy as np

from estimation_rotation import matrix
from highway_segments import REBASE_DISTANCE
from sensor_run import SensingRun, truth_sample
from simulation import Simulation, interpolate
from vehicle_state import VehicleCommand


def test_sensor_sampling_leaves_native_physics_snapshot_and_rng_identical():
    baseline, measured = Simulation(17, track="test"), Simulation(17, track="test")
    try:
        sensing = SensingRun(measured.snapshot(), measured.config, seed=51)
        gnss = wheels = 0
        for tick in range(120):
            command = VehicleCommand(throttle=.5, steering=1. if tick >= 90 else 0., direction=1)
            baseline.step(command)
            measured.step(command)
            state = sensing.observe(measured.snapshot())
            assert baseline.snapshot() == measured.snapshot()
            assert state.estimate.tick == tick + 1
            wheels += state.measurements.wheels is not None
            gnss += len(state.measurements.gnss)
        assert wheels == 60 and gnss == 9
    finally:
        baseline.close()
        measured.close()


def test_sensor_absolute_coordinates_and_reset_clear_delayed_history():
    sim = Simulation(track="test")
    try:
        initial = sim.snapshot()
        shifted = replace(initial, origin_y=8192., player=replace(initial.player,
                          position=(initial.player.position[0], initial.player.position[1] - 8192., initial.player.position[2])))
        assert truth_sample(shifted).position == truth_sample(initial).position
        sensing = SensingRun(initial, sim.config)
        for _ in range(30):
            sim.step(VehicleCommand())
            sensing.observe(sim.snapshot())
        assert sensing.sensors.pending
        sim.reset(23)
        result = sensing.observe(sim.snapshot())
        assert result.reset and result.measurements is None
        assert not sensing.sensors.pending
        assert tuple(sensing.timeline.history) == (0,)
        assert result.estimate.position == sim.snapshot().player.position
    finally:
        sim.close()


def test_snapshot_orientation_uses_real_body_rotation_and_readonly_interpolation():
    sim = Simulation(track="test")
    try:
        old = sim.snapshot()
        sim.reset_player(old.player.position, heading=30.)
        current = sim.snapshot()
        actual_forward = matrix(current.player.orientation) @ (0., 1., 0.)
        assert np.allclose(actual_forward, (-.5, np.sqrt(3) / 2, 0.), atol=1e-7)
        midpoint = interpolate(old, current, .5)
        assert np.allclose(np.linalg.norm(midpoint.player.orientation), 1.)
        assert sim.snapshot() == current
    finally:
        sim.close()


def test_real_world_rebase_keeps_sensor_history_in_absolute_coordinates():
    sim = Simulation(track="endless", traffic_count=0)
    try:
        position = sim.snapshot().player.position
        sim.reset_player((position[0], REBASE_DISTANCE + .125, position[2]))
        initial = sim.snapshot()
        sensing = SensingRun(initial, sim.config)
        for _ in range(30):
            sim.step(VehicleCommand())
            state = sensing.observe(sim.snapshot())
            assert not state.reset
        assert sim.rebases == 1
        assert state.estimate.position[1] > REBASE_DISTANCE - 5
        assert all(sample.position[1] > REBASE_DISTANCE - 5 for sample in sensing.sensors.pending)
        assert sim.snapshot().origin_y > 0
    finally:
        sim.close()
