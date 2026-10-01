from dataclasses import asdict

from driver_assist import GAME_INPUT, SIMULATION_INPUT, DriverAssist
from driving_modes import REFERENCE_CAR, DrivingMode
from simulation import Simulation
from vehicle_config import CAR
from vehicle_state import Control, VehicleCommand


def test_reference_mode_has_a_coherent_vehicle_profile():
    assert DrivingMode.GAME.vehicle_config is CAR
    assert DrivingMode.SIMULATION.vehicle_config is REFERENCE_CAR
    assert CAR.torque_curve != REFERENCE_CAR.torque_curve
    assert CAR.game_speed_limits
    assert not REFERENCE_CAR.game_speed_limits
    assert CAR.angular_damping != REFERENCE_CAR.angular_damping
    assert REFERENCE_CAR.body_inertia is not None
    assert CAR.road_friction == REFERENCE_CAR.road_friction
    assert GAME_INPUT != SIMULATION_INPUT


def test_game_and_simulation_inputs_have_distinct_mapping():
    game_assist = DriverAssist(CAR, GAME_INPUT)
    simulation_assist = DriverAssist(REFERENCE_CAR, SIMULATION_INPUT)
    control = Control(steering=1, throttle=1, direction=1)

    game_command = game_assist.command(control, 40, 1, True, 1 / 120)
    simulation_command = simulation_assist.command(control, 40, 1, True, 1 / 120)

    assert 0 < game_command.throttle < simulation_command.throttle == 1
    assert 0 < game_command.steering < simulation_command.steering
    assert simulation_command.steering == REFERENCE_CAR.steering_degrees
    assert simulation_command.direction == 1

    for _ in range(47):
        game_command = game_assist.command(Control(brake=1), 0, 1, True, 1 / 120)
    assert game_command.direction != -1
    game_command = game_assist.command(Control(brake=1), 0, 1, True, 1 / 120)
    assert game_command.direction == -1

    reverse_command = simulation_assist.command(
        Control(brake=1, direction=-1), 0, 1, True, 1 / 120
    )
    assert reverse_command.direction == -1
    assert reverse_command.throttle == 0
    assert reverse_command.brake == 1


def test_explicit_vehicle_commands_use_same_physics_in_both_input_modes():
    game = Simulation(
        23, track="test", traffic_count=0, config=CAR,
        input_config=GAME_INPUT, traffic_input_config=GAME_INPUT,
    )
    simulation = Simulation(
        23, track="test", traffic_count=0, config=CAR,
        input_config=SIMULATION_INPUT, traffic_input_config=SIMULATION_INPUT,
    )
    try:
        for tick in range(180):
            command = VehicleCommand(
                steering=2 if tick < 60 else -1,
                throttle=.35 if tick < 120 else 0,
                brake=.2 if tick >= 120 else 0,
                direction=1,
            )
            game.step(command)
            simulation.step(command)
            game_snapshot = game.snapshot()
            simulation_snapshot = simulation.snapshot()
            assert asdict(game_snapshot.player) == asdict(simulation_snapshot.player)
            assert game_snapshot.traffic == simulation_snapshot.traffic
            assert game_snapshot.events == simulation_snapshot.events
    finally:
        game.close()
        simulation.close()


def test_baseline_comparator_only_tolerates_float32_geometry_and_ignores_ids():
    from tools.driving_mode_check import compare_record

    baseline = {
        "tick": 1,
        "input": {"steering": .1, "throttle": .2, "brake": 0},
        "player": {
            "position": [1.0, 0.0, 0.0],
            "speed": 2.0,
            "contact_epoch": 4,
            "wheel_dynamics": [{"omega": 3.0, "sources": [7]}],
        },
        "events": [],
    }
    current = {
        "tick": 1,
        "input": {"steering": .1, "throttle": .2, "brake": 0, "direction": 1},
        "player": {
            "position": [1.0000001, 0.0, 0.0],
            "speed": 2.0,
            "contact_epoch": 99,
            "wheel_dynamics": [{"omega": 3.0, "sources": [108]}],
        },
        "events": [],
    }

    comparison = compare_record(baseline, current)
    assert comparison["mismatch_count"] == 0
    assert comparison["max_geometry_abs_delta"] > 0

    current["player"]["speed"] = 2.0000001
    comparison = compare_record(baseline, current)
    assert comparison["mismatch_count"] == 1
    assert comparison["mismatches"][0]["path"] == "player.speed"
