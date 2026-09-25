import pytest
from panda3d.core import Vec3

from highway_run import TRAFFIC_DENSITIES, HighwayRun
from race import GameMode
from session import Phase, Session
from simulation import FIXED_DT, Control, Simulation


def test_reverse_adjustment_does_not_fail_or_earn_repeat_distance():
    trip = HighwayRun()
    trip.start(8, challenge=True)
    for position in (108, 58, 108):
        trip.update(position, 0, 1)
    assert trip.snapshot.running
    assert trip.snapshot.distance == 100
    trip.update(5008, 0, 1)
    assert trip.snapshot.succeeded
    assert trip.snapshot.elapsed == 4
    trip.update(5010, 0, 1)
    assert trip.snapshot.elapsed == 4


@pytest.mark.parametrize("collision,reset,reason", [(1, False, "发生碰撞"), (0, True, "车辆复位")])
def test_challenge_failure_takes_priority_over_finish(collision, reset, reason):
    trip = HighwayRun()
    trip.start(8, challenge=True)
    trip.update(5008, collision, 1, reset=reset)
    assert trip.snapshot.finished and not trip.snapshot.succeeded
    assert trip.snapshot.reason == reason


def test_free_drive_continues_after_collision_and_recovery():
    trip = HighwayRun()
    trip.start(8)
    trip.update(108, 1, 1)
    trip.update(200, 1, 0, reset=True)
    assert trip.snapshot.distance == 100
    trip.update(220, 1, 1)
    assert trip.snapshot.running and trip.snapshot.distance == 120
    assert trip.snapshot.collisions == 1


@pytest.mark.parametrize("density", TRAFFIC_DENSITIES)
def test_menu_density_applies_to_new_run_and_restart(density):
    session = Session(track="test")
    try:
        session.traffic_density = density
        session.start(track="endless", mode=GameMode.DISTANCE_CHALLENGE, countdown=False)
        preset = TRAFFIC_DENSITIES[density]
        assert len(session.current.traffic) == preset.cars
        assert session.simulation.traffic_span == preset.spawn_span
        session.tick()
        assert session.highway.snapshot.elapsed == FIXED_DT
        session.pause()
        session.frame(1)
        assert session.highway.snapshot.elapsed == FIXED_DT
        session.start(countdown=False)
        assert len(session.current.traffic) == preset.cars
        assert session.highway.snapshot.elapsed == 0
        session.reset_player()
        assert session.phase == Phase.RESULTS
        assert session.highway.snapshot.reason == "车辆复位"
    finally:
        session.close()


def test_contact_episode_counts_traffic_and_guardrail_but_not_floor():
    sim = Simulation(track="endless", traffic_count=1)
    try:
        for _ in range(120):
            sim.step(Control())
        assert sim.snapshot().collisions == 0
        # Hold an overlapping NPC stationary for several steps: one accident.
        for _ in range(5):
            sim.npcs[0].reset(tuple(sim.player._chassis.getTransform().getPos()))
            sim.step(Control())
        assert sim.snapshot().collisions == 1
        sim.npcs[0].reset((0, 200, 0.55))
        sim.reset_player((0, 8, 0.55))
        for _ in range(121):
            sim.step(Control())
        sim.reset_player((7.15, 20, 0.55))
        sim.player._chassis.setLinearVelocity(Vec3(6, 0, 0))
        for _ in range(30):
            sim.step(Control())
        assert sim.snapshot().collisions == 2
    finally:
        sim.close()


@pytest.mark.parametrize("shape", ["straight", "hills"])
def test_mileage_stays_continuous_when_world_origin_moves(shape):
    session = Session(track="endless", road_shape=shape)
    try:
        session.start(countdown=False, mode=GameMode.DISTANCE_CHALLENGE)
        sim = session.simulation
        point = sim.road.sample(2100, 1)
        sim.reset_player((point.x, point.y, point.z + 0.55), point.heading, point.grade)
        before = session.highway_progress()
        sim._rebase()
        assert sim.rebases == 1
        assert session.highway_progress() == pytest.approx(before, abs=0.001)
    finally:
        session.close()
