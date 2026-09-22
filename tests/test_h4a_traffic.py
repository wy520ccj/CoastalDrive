import time
from dataclasses import replace
from itertools import pairwise

from panda3d.bullet import BulletVehicle

from simulation import Simulation, Snapshot, interpolate
from vehicle_state import CarState, Control


def test_npcs_are_four_wheel_bullet_vehicles():
    sim = Simulation(7, track="coastal", traffic_count=8)
    try:
        assert len(sim.npcs) == 8
        assert all(isinstance(car._vehicle, BulletVehicle) for car in sim.npcs)
        assert all(len(car._vehicle.getWheels()) == 4 for car in sim.npcs)
    finally:
        sim.close()


def test_eight_coastal_npcs_accumulate_route_progress():
    sim = Simulation(11, track="coastal", traffic_count=8)
    try:
        previous = [sim.road.locate(car.snapshot())[0] for car in sim.npcs]
        progress = [0.0] * len(sim.npcs)
        max_lateral_error = [0.0] * len(sim.npcs)
        for _ in range(2400):
            sim.step(Control())
            for index, car in enumerate(sim.npcs):
                state = car.snapshot()
                distance, lateral = sim.road.locate(state)
                progress[index] += sim.road.delta(distance, previous[index])
                previous[index] = distance
                max_lateral_error[index] = max(
                    max_lateral_error[index], abs(lateral - sim.road.lanes[sim.drivers[index].lane])
                )
        assert all(value > 100 for value in progress), progress
        assert max(max_lateral_error) < 3.0, max_lateral_error
    finally:
        sim.close()


def test_eight_and_sixteen_npc_physics_have_bounded_cost():
    elapsed = {}
    for count in (8, 16):
        sim = Simulation(13, track="coastal", traffic_count=count)
        try:
            started = time.perf_counter()
            for _ in range(360):
                sim.step(Control())
            elapsed[count] = time.perf_counter() - started
        finally:
            sim.close()
    assert elapsed[8] > 0 and elapsed[16] > 0
    assert elapsed[16] < elapsed[8] * 5.0, elapsed


def test_static_player_front_queue_keeps_two_metre_net_gaps():
    sim = Simulation(3, track="highway", traffic_count=4)
    try:
        sim.reset_player((0, 300, 0.55), 0)
        sim.player.reverse_enabled = False
        for index, car in enumerate(sim.npcs):
            sim.drivers[index].lane = 1
            car.reset((0, 280 - index * 40, 0.55), 0)
        for _ in range(3600):
            sim.step(Control())
        states = [car.snapshot() for car in sim.npcs]
        ordered = sorted(states, key=lambda state: state.position[1], reverse=True)
        gaps = [(a.position[1] - b.position[1]) - 2 * 2.05 for a, b in pairwise(ordered)]
        player_gap = sim.player.snapshot().position[1] - ordered[0].position[1] - 2 * 2.05
        assert min([player_gap, *gaps]) >= 2.0, [player_gap, *gaps]
        assert all(state.speed < 0.2 for state in states), [state.speed for state in states]
        assert sim.collision_count == 0
    finally:
        sim.close()


def test_position_clear_uses_rotated_width_and_high_speed_stopping_distance():
    sim = Simulation(5, track="highway", traffic_count=1)
    try:
        sim.npcs[0].reset((0, 200, 0.55), 0)
        assert sim._position_clear((2.5, 200, 0.55), 0, speed=0)
        assert not sim._position_clear((2.5, 200, 0.55), 45, speed=0)
        assert sim._position_clear((0, 180, 0.55), 0, speed=0)
        sim.npcs[0].reset((0, 160, 0.55), 0)
        sim.npcs[0]._chassis.setLinearVelocity((0, 30, 0))
        sim.step(Control())
        assert not sim._position_clear((0, 180, 0.55), 0, speed=0)
    finally:
        sim.close()


def test_interpolate_does_not_fly_across_active_or_generation_change():
    old = CarState((1, 2, 0.5), active=True, generation=2)
    recycled = CarState((900, 1000, 0.5), active=True, generation=3)
    retired = replace(recycled, active=False)
    previous = Snapshot(1, 1 / 120, old, (old,))
    next_generation = Snapshot(2, 2 / 120, recycled, (recycled,))
    inactive = Snapshot(2, 2 / 120, retired, (retired,))
    assert interpolate(previous, next_generation, 0.5).traffic[0] is recycled
    assert interpolate(previous, inactive, 0.5).traffic[0] is retired
