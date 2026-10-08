"""实际共同末状态的解析Jacobian对独立中心差分；不降低求解精度。"""

import gzip
import json
import math
from pathlib import Path

import mechanical_kernels
import pytest
from mechanical_kernels import shared_map_jacobian, shared_map_state

import tire_drivetrain
from driver_assist import GAME_INPUT
from simulation import Simulation
from vehicle_designs import GR86_DESIGN
from vehicle_state import Control


def test_wall_shared_state_converges_at_original_coordinate_precision():
    # 第1145拍撞墙输入：离合与齿轮在输入轴上产生几乎抵消的反力。
    data = json.loads(gzip.decompress((Path(__file__).parent / "data/wall-shared/input.json.gz").read_bytes()))
    constructors = {name: function for name, function in (
        ("mass_coefficients", mechanical_kernels.mass_coefficients),
        ("rotor_coefficients", mechanical_kernels.rotor_coefficients),
        ("shared_map_coefficients", mechanical_kernels.shared_map_coefficients),
    )}

    def restore(value):
        if isinstance(value, dict):
            if "capsule" in value:
                return constructors[value["capsule"]](*restore(value["args"]), **restore(value["kwargs"]))
            if "tuple" in value:
                return tuple(restore(x) for x in value["tuple"])
            return {k: restore(v) for k, v in value.items()}
        if isinstance(value, list):
            return [restore(x) for x in value]
        return value

    data = restore(data)
    solution = mechanical_kernels.shared_solution(data["shared_map"], data["guess"], data["loads"],
        data["wheel_loads"], data["supported"], data["shared_branch"], data["bias_ports"])
    target = shared_map_state(data["shared_map"], solution[0], data["loads"],
                             data["wheel_loads"], data["supported"], solution[5])[0]
    assert all(abs(a-b) <= max(1e-14, math.ulp(a), math.ulp(b)) for a, b in zip(solution[0], target))


def test_native_loaded_axle_jacobian_matches_independent_difference(monkeypatch):
    original = tire_drivetrain.shared_load_solution
    original_coefficients = tire_drivetrain.wheel_map_coefficients
    packets = {}
    errors = []

    def recorded_coefficients(shared, load, *args):
        packet = original_coefficients(shared, load, *args)
        packets[packet] = shared, load
        return packet

    def audited_solve(packet, guess, forces, velocity, normal_forces, normal_responses, gradients,
                      wheel_loads, supported, warm, bias_ports):
        if len(errors) < 16 and all(load > 0. for load in wheel_loads):
            # GR86的真实限滑端口也是未知量；用同一系数包核对实际输入状态。
            coefficients, load = packets[packet]
            loads = tire_drivetrain.wheel_load_prepared(
                load, forces, velocity, normal_forces, normal_responses, gradients, None)
            state = tuple(guess) + tuple(bias_ports)

            def mapped(candidate):
                return shared_map_state(
                    coefficients, candidate, loads, wheel_loads, supported, warm)

            partition = mapped(state)[5:7]
            columns = shared_map_jacobian(
                coefficients, state, wheel_loads, supported, *partition)
            numeric, partitions = [], []
            for j in range(len(state)):
                positive, negative = list(state), list(state)
                positive[j] += .0001
                negative[j] -= .0001
                high, low = mapped(positive), mapped(negative)
                partitions.extend((high[5:7], low[5:7]))
                numeric.append(tuple(float(i == j) - (high[0][i]-low[0][i])/.0002 for i in range(len(state))))
            if all(candidate == partition for candidate in partitions):
                error = max(abs(columns[j][i] - numeric[j][i]) / max(1., abs(columns[j][i]), abs(numeric[j][i]))
                            for i in range(len(state)) for j in range(len(state)))
                assert error < 2e-6
                errors.append(error)
        return original(packet, guess, forces, velocity, normal_forces, normal_responses, gradients,
                        wheel_loads, supported, warm, bias_ports)

    monkeypatch.setattr(tire_drivetrain, "wheel_map_coefficients", recorded_coefficients)
    monkeypatch.setattr(tire_drivetrain, "shared_load_solution", audited_solve)
    sim = Simulation(17, track="coastal", traffic_count=0, config=GR86_DESIGN,
                     input_config=GAME_INPUT)
    try:
        for tick in range(24):
            sim.step(Control(throttle=.3, steering=.02 if tick >= 12 else 0.))
    finally:
        sim.close()
    assert len(errors) == 16
    assert max(errors) == pytest.approx(0., abs=2e-6)
