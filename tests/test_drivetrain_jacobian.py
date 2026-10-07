"""实际共同末状态的解析Jacobian对独立中心差分；不降低求解精度。"""

import inspect

import pytest

import tire_drivetrain
from driver_assist import GAME_INPUT
from simulation import Simulation
from vehicle_designs import GR86_DESIGN
from vehicle_state import Control


def test_native_loaded_axle_jacobian_matches_independent_difference(monkeypatch):
    original = tire_drivetrain._solve
    errors = []

    def audited_solve(matrix, rhs):
        caller = inspect.currentframe().f_back
        if caller.f_code.co_name == "shared" and len(errors) < 16:
            values = caller.f_locals
            state, mapped = values["state"], values["mapped"]
            partition = values["shared_branch"], values["shared_port_index"]
            numeric, partitions = [], []
            for j in range(len(state)):
                positive, negative = list(state), list(state)
                positive[j] += .0001
                negative[j] -= .0001
                high = mapped(positive)[0]
                partitions.append((caller.f_locals["shared_branch"], caller.f_locals["shared_port_index"]))
                low = mapped(negative)[0]
                partitions.append((caller.f_locals["shared_branch"], caller.f_locals["shared_port_index"]))
                numeric.append(tuple(float(i == j) - (high[i]-low[i])/.0002 for i in range(len(state))))
            mapped(state)
            if all(candidate == partition for candidate in partitions):
                error = max(abs(matrix[i][j] - numeric[j][i]) / max(1., abs(matrix[i][j]), abs(numeric[j][i]))
                            for i in range(len(state)) for j in range(len(state)))
                assert error < 2e-6
                errors.append(error)
        return original(matrix, rhs)

    monkeypatch.setattr(tire_drivetrain, "_solve", audited_solve)
    sim = Simulation(17, track="coastal", traffic_count=0, config=GR86_DESIGN,
                     input_config=GAME_INPUT)
    try:
        for tick in range(24):
            sim.step(Control(throttle=.3, steering=.02 if tick >= 12 else 0.))
    finally:
        sim.close()
    assert len(errors) == 16
    assert max(errors) == pytest.approx(0., abs=2e-6)
