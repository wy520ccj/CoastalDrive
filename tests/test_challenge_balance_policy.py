"""独立试车策略在转向饱和前减速，不修改玩家输入包络。"""

from types import SimpleNamespace

import pytest
from challenge_balance_check import RoadPilot

from driver_assist import GAME_INPUT, SIMULATION_INPUT
from race import GameMode
from vehicle_config import CAR


def state_and_world(speed=25., lateral=3., input_config=GAME_INPUT):
    car = SimpleNamespace(speed=speed, position=(lateral, 0., 0.), heading=0.)
    state = SimpleNamespace(player=car, origin_y=0.)
    road = SimpleNamespace(curve=True, locate=lambda car: (0., lateral),
                           sample_lateral=lambda distance, offset:
                           SimpleNamespace(x=offset, y=distance, heading=0.))
    world = SimpleNamespace(road=road, config=CAR, input_config=input_config,
                            snapshot=lambda: state)
    return state, world


def test_saturated_tracking_brakes_instead_of_accelerating_with_full_steering():
    state, world = state_and_world()
    old = RoadPilot(world, GameMode.BEND_SPRINT, target_kph=105.).road_control(state)
    pilot = RoadPilot(world, GameMode.BEND_SPRINT, target_kph=105., steering_reserve=.9)
    new = pilot.road_control(state)
    assert old.throttle == 1. and old.brake == 0. and abs(old.steering) == 1.
    assert new.throttle == 0. and new.brake > 0. and new.steering == old.steering
    assert pilot.policy['steering_reserve'] == .9


@pytest.mark.parametrize('speed', [0., 25.])
def test_straight_tracking_keeps_launch_and_original_cruise_control(speed):
    state, world = state_and_world(speed=speed, lateral=0.)
    old = RoadPilot(world, GameMode.BEND_SPRINT, target_kph=105.)
    new = RoadPilot(world, GameMode.BEND_SPRINT, target_kph=105., steering_reserve=.9)
    assert old.road_control(state) == new.road_control(state)


def test_steering_demand_uses_actual_input_mode():
    state, world = state_and_world(input_config=SIMULATION_INPUT)
    control = RoadPilot(world, GameMode.BEND_SPRINT, target_kph=105., steering_reserve=.9).road_control(state)
    assert abs(control.steering) < .9 and control.brake == 0. and control.throttle == 1.


@pytest.mark.parametrize('reserve', [0., 1., -1., float('nan')])
def test_invalid_reserve_is_rejected(reserve):
    _, world = state_and_world()
    with pytest.raises(ValueError, match='转向余量'):
        RoadPilot(world, GameMode.BEND_SPRINT, steering_reserve=reserve)
