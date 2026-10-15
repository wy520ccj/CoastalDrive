"""分段投影导数与真实初始化失败输入复现，保持原物理残差阈值。"""

from pathlib import Path

import numpy as np
import pytest
from physics.unsprung_step_checkpoint import load_step

from unsprung_joint import dry_port_derivative


@pytest.mark.parametrize("torque,speed,capacity,expected_v,expected_t", (
    (.067, 6e-8, .244, -500., 0.),
    (0., 0., 0., 0., 1.),
    (1., .1, .244, 0., 1.),
    (-1., -.1, .244, 0., 1.),
    (0., 0., 1e-12, -500., 0.),
))
def test_exact_stick_slip_derivative(torque, speed, capacity, expected_v, expected_t):
    row = np.zeros(16)
    row[12] = 1.
    derivative, torque_derivative = dry_port_derivative(row, torque, speed, capacity, .002)
    assert derivative[12] == expected_v
    assert torque_derivative == expected_t
    assert np.count_nonzero(derivative[:12]) == 0


def test_actual_soft_spring_init_replay_preserves_capacity_and_zero_slip():
    source = load_step(Path(__file__).parent/"data/unsprung-soft-spring-init.pkl")
    result = source.solve()
    assert result.momentum_error < 1e-9
    assert result.force_error < 1e-5
    assert result.port_error < 1e-9
    assert result.iterations < 30
    assert np.max(np.abs(result.port_torques[3:7])) < np.min(source.brake_capacity)
    ports = source.hardware.brakes
    assert np.max(np.abs(ports@result.velocity)) < 1e-10
    assert result.energy_error == pytest.approx(0., abs=1e-7)
