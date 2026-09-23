"""Curved and hilly streamed-road boundary regressions."""

import math

import pytest
from panda3d.core import Vec3

from race import GameMode
from session import Session
from simulation import Control, Simulation


def wheel_clearances(sim, car):
    """Return wheel-center heights above the currently loaded road surface."""
    return tuple(
        wheel.position[2] - sim.ground_height(wheel.position[0], wheel.position[1])
        for wheel in car.wheels
    )


def test_hilly_segment_seam_stays_supported_when_parked():
    sim = Simulation(track="endless", road_shape="hills", traffic_count=0)
    try:
        point = sim.road.sample(200, 1)
        assert abs(point.grade) > 0.5
        sim.reset_player((point.x, point.y, point.z + 0.55), point.heading, point.grade)
        sim.player.reverse_enabled = False

        for _ in range(600):
            sim.step(Control(brake=1))

        car = sim.snapshot().player
        distance, lateral = sim.road.locate(car)
        assert distance == pytest.approx(200, abs=0.5)
        assert abs(lateral) < 0.25
        assert abs(car.speed) < 0.2
        assert abs(car.roll) < 3
        assert all(0.20 < gap < 0.55 for gap in wheel_clearances(sim, car))
        assert sim.collision_count == 0
    finally:
        sim.close()


def test_hilly_reset_after_far_origin_shift_returns_to_spawn():
    sim = Simulation(track="endless", road_shape="hills", traffic_count=0)
    try:
        point = sim.road.sample(2400, 1)
        sim.reset_player((point.x, point.y, point.z + 0.55), point.heading, point.grade)
        sim.step(Control())
        assert sim.snapshot().origin_y == pytest.approx(2200)

        sim.reset_player()
        car = sim.snapshot().player
        distance, lateral = sim.road.locate(car)
        assert distance == pytest.approx(8, abs=0.5)
        assert abs(lateral) < 0.25
        assert all(0.20 < gap < 0.55 for gap in wheel_clearances(sim, car))
    finally:
        sim.close()


def test_hilly_session_restart_after_far_origin_shift_reloads_spawn():
    session = Session(track="endless", road_shape="hills")
    try:
        session.start(countdown=False, mode=GameMode.FREE_DRIVE)
        point = session.simulation.road.sample(2400, 1)
        session.simulation.reset_player((point.x, point.y, point.z + 0.55), point.heading, point.grade)
        session.simulation.step(Control())
        session.sync_snapshots()
        assert session.current.origin_y == pytest.approx(2200)

        session.start(countdown=False, mode=GameMode.FREE_DRIVE)
        car = session.current.player
        distance, lateral = session.simulation.road.locate(car)
        assert session.current.origin_y == pytest.approx(0)
        assert distance == pytest.approx(8, abs=0.5)
        assert abs(lateral) < 0.25
        assert all(0.20 < gap < 0.55 for gap in wheel_clearances(session.simulation, car))
    finally:
        session.close()


def test_high_speed_pedals_cross_hilly_segment_seam_without_jump():
    sim = Simulation(track="endless", road_shape="hills", traffic_count=0)
    try:
        point = sim.road.sample(190, 1)
        sim.reset_player((point.x, point.y, point.z + 0.55), point.heading, point.grade)
        heading, grade = math.radians(point.heading), math.radians(point.grade)
        speed = 32.0
        sim._chassis.setLinearVelocity(
            Vec3(
                -math.sin(heading) * math.cos(grade) * speed,
                math.cos(heading) * math.cos(grade) * speed,
                math.sin(grade) * speed,
            )
        )

        previous = sim.snapshot().player
        seam_samples = []
        max_step = 0.0
        for _ in range(120):
            sim.step(Control(steering=0.03, throttle=0.35))
            car = sim.snapshot().player
            distance, lateral = sim.road.locate(car)
            max_step = max(max_step, math.dist(previous.position, car.position))
            if 195 < distance < 205:
                seam_samples.append((car, lateral))
            previous = car

        assert seam_samples
        assert 30 < seam_samples[0][0].speed < 35
        assert all(abs(lateral) < 1.0 for _, lateral in seam_samples)
        assert all(abs(car.pitch) < 6 and abs(car.roll) < 4 for car, _ in seam_samples)
        assert all(0.20 < gap < 0.55 for car, _ in seam_samples for gap in wheel_clearances(sim, car))
        assert max_step < 0.35
        assert sim.collision_count == 0
    finally:
        sim.close()
