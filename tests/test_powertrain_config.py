from dataclasses import replace

from powertrain import Powertrain, engine_torque
from vehicle_config import CAR
from vehicle_steering import SteeringRack, wheel_angles

REFERENCE_TORQUE_CURVE = (
    (900, 110),
    (1800, 165),
    (3200, 200),
    (4500, 190),
    (6000, 150),
    (6500, 0),
)


def run_reverse(powertrain, speed, ticks=240):
    torque = 0.0
    for _ in range(ticks):
        torque, _ = powertrain.advance(speed, 0.0, 1.0, -1, False, 1 / 120)
    return torque


def test_powertrain_instances_use_their_own_curves_and_dynamics():
    game = replace(CAR, torque_response=0.08)
    reference = replace(CAR, torque_curve=REFERENCE_TORQUE_CURVE, torque_response=0.4)
    game_a = Powertrain(game)
    game_b = Powertrain(game)
    reference_train = Powertrain(reference)

    game_trace = []
    twin_trace = []
    for speed, omega, pedal in ((0, 0, 1), (4, 30, .8), (12, 70, .5), (20, 90, .2)):
        game_trace.append(game_a.advance(speed, omega, pedal, 1, False, 1 / 120))
        twin_trace.append(game_b.advance(speed, omega, pedal, 1, False, 1 / 120))
        reference_train.advance(speed, omega, pedal, 1, False, 1 / 120)

    assert game_trace == twin_trace
    assert game_a.config is game
    assert reference_train.config is reference
    assert engine_torque(3200, game) == 211
    assert engine_torque(3200, reference) == 200
    assert game_a.drive_torque != reference_train.drive_torque


def test_default_construction_matches_explicit_default_config():
    implicit = Powertrain()
    explicit = Powertrain(CAR)
    inputs = ((0, 0, 1, 1), (3, 25, .7, 1), (11, 65, .4, 1), (8, 40, .2, -1))

    for speed, omega, pedal, direction in inputs:
        assert implicit.advance(speed, omega, pedal, direction, False, 1 / 120) == (
            explicit.advance(speed, omega, pedal, direction, False, 1 / 120)
        )
        assert (implicit.rpm, implicit.gear, implicit.shift_remaining) == (
            explicit.rpm, explicit.gear, explicit.shift_remaining
        )
    assert engine_torque(3200) == engine_torque(3200, CAR)


def test_reference_curve_drives_past_game_speed_limit():
    game = replace(CAR, game_speed_limits=True)
    reference = replace(
        CAR, torque_curve=REFERENCE_TORQUE_CURVE, game_speed_limits=False
    )
    game_train = Powertrain(game)
    reference_train = Powertrain(reference)
    speed = CAR.max_speed

    for _ in range(240):
        game_torque, _ = game_train.advance(speed, 10, 1, 1, False, 1 / 120)
        reference_torque, _ = reference_train.advance(speed, 10, 1, 1, False, 1 / 120)

    assert game_torque == 0
    assert reference_torque > 0


def test_reverse_force_limit_applies_only_to_game_profile():
    game = replace(CAR, game_speed_limits=True)
    reference = replace(CAR, torque_curve=REFERENCE_TORQUE_CURVE, game_speed_limits=False)

    game_torque = run_reverse(Powertrain(game), 0)
    reference_torque = run_reverse(Powertrain(reference), 0)

    game_cap = game.reverse_force * game.wheel_radius
    assert abs(game_torque) <= game_cap + 1e-9
    assert abs(reference_torque) > game_cap

    game_train = Powertrain(game)
    reference_train = Powertrain(reference)
    reverse_limit_speed = game.reverse_speed + 1
    for _ in range(240):
        game_torque, _ = game_train.advance(
            reverse_limit_speed, 0, 1, -1, False, 1 / 120
        )
        reference_torque, _ = reference_train.advance(
            reverse_limit_speed, 0, 1, -1, False, 1 / 120
        )
    assert game_torque == 0
    assert abs(reference_torque) > 0


def test_steering_racks_are_configured_per_instance():
    narrow = replace(CAR, steering_degrees=8, steering_rate=20, track_width=1.5)
    rack_a = SteeringRack(narrow)
    rack_b = SteeringRack(narrow)
    default_rack = SteeringRack(CAR)

    trace_a = [rack_a.advance(20, 1 / 120) for _ in range(120)]
    trace_b = [rack_b.advance(20, 1 / 120) for _ in range(120)]
    default_angle = default_rack.advance(20, 1 / 120)

    assert trace_a == trace_b
    assert rack_a.config is narrow
    assert rack_a.angle <= narrow.steering_degrees
    assert default_angle > trace_a[0]
    assert wheel_angles(15, narrow) != wheel_angles(15, CAR)
