"""H3: adversarial race rules, physical roadside objects and road-load behavior."""

import json
import math
from dataclasses import replace
from types import SimpleNamespace

import pytest
from panda3d.core import BitMask32, Vec3
from route_driver import RouteDriver

from coastal_map import map_length, nearest_point, offset_point, point_at
from highway_map import HIGHWAY_LENGTH, lane_x
from race import BestTimes, GameMode, RaceTracker
from session import Phase, Session
from simulation import Control, Simulation
from tracks import COASTAL_CIRCUIT
from vehicle_config import CAR
from vehicle_dynamics import aerodynamic_force, axle_loads


def state_at(distance, offset=0, height=0.42, speed=20):
    return SimpleNamespace(
        player=SimpleNamespace(
            position=offset_point(point_at(distance), offset, height), speed=speed
        )
    )


def tracker(tmp_path):
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(tmp_path / "scores.json"))
    race.begin()
    return race


def test_slow_forward_backward_motion_cannot_farm_a_lap(tmp_path):
    race = tracker(tmp_path)
    for i in range(20000):
        race.update(state_at(0.04 if i % 2 else 0, speed=0.2), 1 / 120)
    assert not race.snapshot.finished
    assert race.snapshot.checkpoints == 0
    assert not (tmp_path / "scores.json").exists()


def test_gates_must_be_crossed_on_road_and_in_order(tmp_path):
    race = tracker(tmp_path)
    for i in range(1, 1002):
        distance = map_length() * i / 1000
        offset = 5.1 if 0.17 < i / 1000 < 0.23 else 0
        race.update(state_at(distance, offset), 0.1)
    assert race.snapshot.finished and race.snapshot.invalidated
    assert not (tmp_path / "scores.json").exists()


def test_airborne_shortcut_is_invalid(tmp_path):
    race = tracker(tmp_path)
    for i in range(1, 1002):
        race.update(state_at(map_length() * i / 1000, height=10), 0.1)
    assert race.snapshot.invalidated
    assert not (tmp_path / "scores.json").exists()


def test_reversing_to_adjust_position_keeps_attempt_valid(tmp_path):
    race = tracker(tmp_path)
    for i in range(1, 121):
        race.update(state_at(i * 0.04, speed=4.8), 1 / 120)
    for i in range(1, 20):
        race.update(state_at(4.8 - i * 0.04, speed=-4.8), 1 / 120)
    assert not race.snapshot.invalidated
    for i in range(20, 100):
        race.update(state_at(4.8 - i * 0.04, speed=-4.8), 1 / 120)
    assert not race.snapshot.invalidated


def test_pause_reset_invalid_finish_and_restart(tmp_path):
    session = Session(scores=BestTimes(tmp_path / "scores.json"))
    try:
        session.start(mode=GameMode.TIME_TRIAL, countdown=False)
        session.set_controller(RouteDriver())
        for _ in range(1200):
            session.tick()
        before = session.race.snapshot
        session.pause()
        for _ in range(1200):
            session.tick()
        assert session.race.snapshot == before
        session.resume()
        session.reset_player()
        for _ in range(9000):
            session.tick()
        assert session.phase == Phase.RESULTS
        assert session.race.snapshot.invalidated
        assert not (tmp_path / "scores.json").exists()
        session.start(mode=GameMode.TIME_TRIAL, countdown=False)
        assert session.race.snapshot.elapsed == 0 and not session.race.snapshot.invalidated
    finally:
        session.close()


def test_actual_physics_lap_records_and_reloads(tmp_path):
    path = tmp_path / "scores.json"
    session = Session(scores=BestTimes(path))
    try:
        session.start(mode=GameMode.TIME_TRIAL, countdown=False)
        session.set_controller(RouteDriver())
        for _ in range(9000):
            session.tick()
        assert session.phase == Phase.RESULTS
        result = session.race.snapshot
        assert not result.invalidated and result.checkpoints == 4
        assert 45 < result.last_lap < 65
        assert BestTimes(path).get(GameMode.TIME_TRIAL) == result.last_lap
        frozen = session.current
        for _ in range(100):
            session.tick()
        assert session.current == frozen
    finally:
        session.close()


def test_invalid_map_mode_does_not_destroy_existing_session(tmp_path):
    session = Session(scores=BestTimes(tmp_path / "scores.json"))
    before = session.current
    with pytest.raises(ValueError):
        session.start(track="highway", mode=GameMode.TIME_TRIAL)
    assert session.phase == Phase.MENU and session.current == before
    assert not session.simulation.closed
    session.close()


def test_course_records_are_separate_and_bad_times_rejected(tmp_path):
    path = tmp_path / "scores.json"
    path.write_text(json.dumps({"coastal-v2:time_trial": True, "other:time_trial": float("inf")}))
    scores = BestTimes(path)
    assert scores.get(GameMode.TIME_TRIAL) is None
    assert scores.get(GameMode.TIME_TRIAL, "other") is None
    scores.record(GameMode.TIME_TRIAL, 50)
    scores.record(GameMode.TIME_TRIAL, 10, "other")
    assert scores.get(GameMode.TIME_TRIAL) == 50
    assert scores.get(GameMode.TIME_TRIAL, "other") == 10
    for value in (True, 0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            scores.record(GameMode.TIME_TRIAL, value)


def test_score_write_failure_keeps_race_alive(tmp_path):
    folder = tmp_path / "folder"
    folder.mkdir()
    scores = BestTimes(folder)
    best, saved = scores.record(GameMode.TIME_TRIAL, 52)
    assert best == 52 and not saved and scores.error


def test_rules_accept_another_course_definition(tmp_path):
    circuit = replace(COASTAL_CIRCUIT, score_id="alternate", checkpoints=(map_length() * 0.5,))
    race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(tmp_path / "scores.json"), circuit)
    race.begin()
    for i in range(1, 1002):
        race.update(state_at(map_length() * i / 1000), 0.1)
    assert race.snapshot.finished and not race.snapshot.invalidated
    assert race.snapshot.checkpoints == 1
    assert race.scores.get(GameMode.TIME_TRIAL, "alternate") is not None


@pytest.mark.parametrize("track", ["coastal", "highway"])
def test_props_have_clearance_and_solid_trunks_posts_and_rocks(track):
    sim = Simulation(track=track)
    try:
        for prop, z in sim.props:
            if prop.kind == "tree":
                if track == "coastal":
                    assert nearest_point(prop.x, prop.y)[1] > 7 + prop.scale * 0.21
                else:
                    assert abs(prop.x) > 8.5 + prop.scale * 0.21
            height = (
                3.35
                if prop.kind == "checkpoint-beam"
                else (
                    0.4
                    if prop.kind == "checkpoint"
                    else (0.3 * prop.scale if prop.kind == "tree" else 0.1 * prop.scale)
                )
            )
            hit = sim._world.rayTestAll(
                Vec3(prop.x - 2, prop.y, z + height),
                Vec3(prop.x + 2, prop.y, z + height),
                BitMask32.bit(0),
            )
            assert any(result.getNode().getName().startswith(prop.kind) for result in hit.getHits())
    finally:
        sim.close()


def test_highway_guardrails_and_end_of_drive(tmp_path):
    session = Session(track="highway", scores=BestTimes(tmp_path / "scores.json"))
    session.start(countdown=False)
    try:
        for y in (0, 650, 1390):
            for side in (-1, 1):
                hit = session.simulation._world.rayTestClosest(
                    Vec3(side * 7, y, 0.4), Vec3(side * 9, y, 0.4), BitMask32.bit(0)
                )
                assert hit.hasHit() and "rail" in hit.getNode().getName()
        session.simulation.reset_player((0, 1401, 0.55))
        session.sync_snapshots()
        session.tick()
        assert session.phase == Phase.RESULTS
        session.simulation.reset_player((0, 1700, 0.55))
        session.simulation.recover_player()
        assert session.simulation.snapshot().player.position[1] <= 1390
    finally:
        session.close()


def test_free_drive_removes_checkpoint_collision_and_time_trial_restores_it():
    session = Session()
    try:
        checkpoint_bodies = lambda: [
            body
            for body in session.simulation._prop_bodies
            if body.getName().startswith("checkpoint")
        ]
        session.start(mode=GameMode.FREE_DRIVE, countdown=False)
        assert all(body.getIntoCollideMask().getWord() == 0 for body in checkpoint_bodies())
        session.start(mode=GameMode.TIME_TRIAL, countdown=False)
        assert all(body.getIntoCollideMask().getWord() == 3 for body in checkpoint_bodies())
        session.menu()
        assert all(body.getIntoCollideMask().getWord() == 0 for body in checkpoint_bodies())
    finally:
        session.close()


def test_highway_recovery_chooses_a_free_lane_when_player_is_in_traffic():
    sim = Simulation(track="highway")
    try:
        target = sim._traffic_bodies[0].getTransform().getPos()
        sim.reset_player((target.x, target.y, 0.55))
        sim.recover_player()
        position = sim._chassis.getTransform().getPos()
        assert all(
            (body.getTransform().getPos() - position).length() > 4.2
            for body in sim._traffic_bodies
            if body not in sim._retired_traffic
        )
    finally:
        sim.close()


def test_traffic_reacts_to_player_and_has_real_collision():
    sim = Simulation(track="highway", traffic_count=1)
    try:
        body = sim._traffic_bodies[0]
        pos = body.getTransform().getPos()
        for _ in range(120):
            sim.step(Control())
        pos = body.getTransform().getPos()
        before = body.getLinearVelocity().y
        sim.reset_player((pos.x, pos.y + 10, 0.55))
        sim.player.reverse_enabled = False
        for _ in range(360):
            sim.step(Control(brake=1))
        assert body.getLinearVelocity().y < before - 1
        assert sim._chassis.getTransform().getPos().y - body.getTransform().getPos().y - 4.1 >= 2
        sim.reset_player((pos.x, body.getTransform().getPos().y - 1, 0.55))
        sim._chassis.setLinearVelocity(Vec3(0, 30, 0))
        collided = False
        for _ in range(60):
            sim.step(Control())
            collided |= sim._world.contactTestPair(sim._chassis, body).getNumContacts() > 0
        assert collided
    finally:
        sim.close()


def test_highway_traffic_stays_grounded_and_retires_beyond_finish():
    sim = Simulation(track="highway")
    generations = [0] * len(sim.npcs)
    born = [0] * len(sim.npcs)
    try:
        for tick in range(18000):
            sim.step(Control())
            if tick % 60:
                continue
            for index, (car, (lane, _, _)) in enumerate(zip(sim.snapshot().traffic, sim._traffic)):
                if car.generation != generations[index]:
                    generations[index], born[index] = car.generation, tick
                assert car.position[1] < HIGHWAY_LENGTH + 6
                if not car.active:
                    continue
                if car.position[1] < HIGHWAY_LENGTH:
                    assert abs(car.roll) < 3 and abs(car.pitch) < 3
                    assert 0.3 < car.position[2] < 0.65
                    assert abs(car.position[0] - lane_x(lane)) < 1.5
                    assert len(car.wheels) == 4
                    if tick - born[index] > 120:
                        assert all(
                            w.getRaycastInfo().isInContact()
                            for w in sim.npcs[index]._vehicle.getWheels()
                        )
                        assert all(abs(wheel.position[2] - 0.33) < 0.03 for wheel in car.wheels)
        assert sim.traffic_cycles > 0
    finally:
        sim.close()


def test_rear_end_crash_transfers_momentum_without_passing_through():
    sim = Simulation(track="highway")
    try:
        target = sim._traffic_bodies[0]
        pos = target.getTransform().getPos()
        sim.reset_player((pos.x, pos.y - 12, 0.55))
        for _ in range(60):
            sim.step(Control())
        sim._chassis.setLinearVelocity(Vec3(0, 30, 0))
        collided = False
        first_contact_gap = None
        for _ in range(480):
            sim.step(Control(throttle=1))
            touching = sim._world.contactTestPair(sim._chassis, target).getNumContacts() > 0
            if touching and first_contact_gap is None:
                first_contact_gap = (
                    target.getTransform().getPos().y - sim._chassis.getTransform().getPos().y
                )
            collided |= touching
            assert abs(sim.snapshot().player.roll) < 10
        state = sim.snapshot()
        assert collided and state.player.speed < 29
        assert first_contact_gap is not None and first_contact_gap > -1
    finally:
        sim.close()


@pytest.mark.parametrize("kind", ["tree", "checkpoint"])
def test_car_hits_solid_roadside_objects(kind):
    sim = Simulation(track="coastal")
    try:
        index, (prop, z) = next((i, p) for i, p in enumerate(sim.props) if p[0].kind == kind)
        target = next(b for b in sim._world.getRigidBodies() if b.getName() == f"{kind}-{index}")
        from simulation import forward

        direction = Vec3(*forward(prop.heading if kind == "checkpoint" else 0))
        heading = prop.heading if kind == "checkpoint" else 0
        sim.reset_player(tuple(Vec3(prop.x, prop.y, z + 0.55) - direction * 6), heading)
        for _ in range(120):
            sim.step(Control())
        sim._chassis.setLinearVelocity(direction * 15)
        collided = False
        for _ in range(150):
            sim.step(Control())
            collided |= sim._world.contactTestPair(sim._chassis, target).getNumContacts() > 0
        assert collided
        assert abs(sim.snapshot().player.speed) < 10
    finally:
        sim.close()


def test_road_load_parameters_have_physical_effects():
    assert aerodynamic_force(20) == pytest.approx(168)
    assert aerodynamic_force(40) == pytest.approx(4 * aerodynamic_force(20))
    assert aerodynamic_force(20, replace(CAR, frontal_area=CAR.frontal_area * 2)) == pytest.approx(
        336
    )
    neutral = axle_loads(0, 0)
    accel = axle_loads(3, 0)
    brake = axle_loads(-5, 0)
    assert sum(neutral) == pytest.approx(CAR.mass * 9.81)
    assert accel[1] > neutral[1] > brake[1]
    assert sum(axle_loads(0, 10)) == pytest.approx(CAR.mass * 9.81 * math.cos(math.radians(10)))


def test_checkpoint_frames_do_not_change_follow_camera():
    from simulation import forward

    sim = Simulation()
    try:
        frames = [b for b in sim._world.getRigidBodies() if b.getName().startswith("checkpoint")]
        queries = []
        for distance in COASTAL_CIRCUIT.checkpoints:
            for step in range(-20, 41):
                p = point_at(distance + step * 0.5)
                anchor = Vec3(p.x, p.y, p.z + 1.82)
                desired = Vec3(p.x, p.y, p.z + 4.62) - Vec3(*forward(p.heading)) * 11
                queries.append((anchor, desired))
        with_frames = [tuple(sim.camera_position(a, b)) for a, b in queries]
        for frame in frames:
            sim._world.removeRigidBody(frame)
        without_frames = [tuple(sim.camera_position(a, b)) for a, b in queries]
        assert with_frames == without_frames
    finally:
        sim.close()


def test_headwind_increases_actual_drag_and_no_thrust_when_airborne():
    a = Simulation(track="test")
    b = Simulation(track="test", wind=(0, -10, 0))
    try:
        for sim in (a, b):
            for _ in range(600):
                sim.step(Control(throttle=1))
        assert a.snapshot().player.speed > b.snapshot().player.speed
        a.reset_player((180, 0, 20))
        for _ in range(30):
            a.step(Control(throttle=1))
        assert all(w.getEngineForce() == 0 for w in a._vehicle.getWheels())
    finally:
        a.close()
        b.close()
