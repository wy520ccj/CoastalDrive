"""游戏键盘响应与完整研究执行器的边界；验证实际松键与反打风险。"""

import pytest

from driver_assist import GAME_INPUT, steering_limit
from lab_experiment import LabExperiment, LabOptions
from simulation import FIXED_DT, Control, Simulation
from vehicle_designs import GR86_DESIGN
from vehicle_state import VehicleCommand
from vehicle_steering import SteeringRack


@pytest.mark.parametrize('speed', (0., 30 / 3.6, 100 / 3.6, 150 / 3.6))
def test_assisted_release_and_reversal_stop_adding_old_direction_immediately(speed):
    rack = SteeringRack(GR86_DESIGN)
    limit = steering_limit(speed, GR86_DESIGN)
    for _ in range(36):
        rack.advance_assisted(limit, FIXED_DT, GAME_INPUT.steering_response_time,
                             GAME_INPUT.steering_return_time)
    release = rack.angle
    for _ in range(120 if speed < 50 / 3.6 else 36):
        before = rack.angle
        rack.advance_assisted(0., FIXED_DT, GAME_INPUT.steering_response_time,
                             GAME_INPUT.steering_return_time)
        assert 0 <= rack.angle < before
        assert abs(rack.velocity) <= GR86_DESIGN.steering_rate
    assert rack.angle < release * .01
    rack.advance_assisted(-limit, FIXED_DT, GAME_INPUT.steering_response_time,
                         GAME_INPUT.steering_return_time)
    assert rack.velocity < 0
    for _ in range(120):
        before = rack.angle
        rack.advance_assisted(-limit, FIXED_DT, GAME_INPUT.steering_response_time,
                             GAME_INPUT.steering_return_time)
        assert -limit <= rack.angle < before


def test_vehicle_control_uses_game_response_but_command_preserves_research_actuator():
    sim = Simulation(track='lab', traffic_count=0, config=GR86_DESIGN)
    try:
        expected = SteeringRack(GR86_DESIGN)
        for _ in range(12):
            sim.player.prepare_control(Control(steering=1.))
        release = sim.player.steering.angle
        sim.player.prepare_control(Control())
        assert sim.player.steering.angle < release
        sim.player.steering = SteeringRack(GR86_DESIGN)
        for _ in range(12):
            expected.advance(2., FIXED_DT)
            sim.player.prepare_command(VehicleCommand(steering=2.))
            assert sim.player.steering.angle == expected.angle
            assert sim.player.steering.velocity == expected.velocity
    finally:
        sim.close()


def test_actual_100kph_vehicle_reverses_rack_and_recovers_after_release():
    run = LabExperiment(LabOptions(vehicle_id='gr86-2022-premium-6mt', speed_kph=100))
    sim = run.experiment.simulation
    sim.player.assist.input_config = GAME_INPUT
    try:
        for _ in range(36):
            sim.step(Control(steering=1.))
        right = sim.snapshot().player.steering
        reverse_angles = []
        for _ in range(36):
            sim.step(Control(steering=-1.))
            reverse_angles.append(sim.snapshot().player.steering)
        assert 0 < reverse_angles[0] < right
        assert reverse_angles[17] < 0
        assert reverse_angles[-1] < -.5
        for _ in range(120):
            before = sim.snapshot().player.steering
            sim.step(Control())
            assert before < sim.snapshot().player.steering <= 0
        state = sim.snapshot().player
        assert abs(state.steering) < .001
        assert abs(state.dynamics.yaw_rate) < .02
        assert sim.collision_count == 0
    finally:
        run.close()
