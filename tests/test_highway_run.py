import pytest
from panda3d.core import BitMask32, Vec3

from challenge_build import BuildDraft
from challenge_catalog import ROAD_CHALLENGES, distance_challenge_spec
from highway_run import TRAFFIC_DENSITIES, HighwayRun
from race import BestTimes, GameMode
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


def test_budget_distance_checks_whole_body_before_awarding_finish():
    config = ROAD_CHALLENGES[GameMode.DISTANCE_CHALLENGE].base_config
    trip = HighwayRun()
    trip.start(8., challenge=True, vehicle_config=config, record_scores=False)
    trip.update(108., 0, 1., lateral=5.)
    trip.update(58., 0, 1., lateral=5., forward_speed=-3.)
    assert trip.snapshot.running and trip.snapshot.distance == 100.
    # 车身中心还在路内，偏转后的车身已越过车道边线。
    trip.update(5008., 0, 1., lateral=5., heading=30.)
    assert trip.snapshot.finished and not trip.snapshot.succeeded
    assert '越出行车道' in trip.snapshot.reason


@pytest.mark.parametrize('shape', ['straight', 'hills'])
def test_budget_distance_boundary_uses_current_road_frame(tmp_path, shape):
    mode = GameMode.DISTANCE_CHALLENGE
    session = Session(track='test', scores=BestTimes(tmp_path/'best-times.json'))
    try:
        session.road_shape = shape
        session.start(track='endless', mode=mode, countdown=False, challenge_spec=ROAD_CHALLENGES[mode])
        sim = session.simulation
        for lateral in (4.5, 6.1):
            point = sim.road.sample_lateral(350., lateral)
            # 在计时开始前布置边线场景，让正常发车初始化本次燃油记录。
            sim.player.reset((point.x, point.y, point.z+.55), point.heading, point.grade)
            session.begin_driving()
            session.tick()
            assert session.highway.snapshot.collisions == 0
            assert session.phase == (Phase.DRIVING if lateral == 4.5 else Phase.RESULTS)
        result = session.highway.snapshot.engineering.result
        assert not result.valid and not result.official and '越出行车道' in result.notice
        assert not session.engineering.scores.path.exists()
    finally:
        session.close()


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


def test_budget_distance_keeps_best_separate_for_selected_shape_and_traffic(tmp_path):
    session = Session(seed=23, track='test', scores=BestTimes(tmp_path/'best-times.json'))
    mode = GameMode.DISTANCE_CHALLENGE
    spec = ROAD_CHALLENGES[mode]
    try:
        session.start(track='endless', mode=mode, countdown=False, challenge_spec=spec)
        first = session.engineering.scores
        assert session.seed == 0 and first.context['input'].endswith(':road-straight:traffic-12-540')
        assert first.spec == distance_challenge_spec('straight', 'normal')
        # 夹具只验证同路况重开能读取正式奖牌及完赛对照。
        result = first.spec.evaluate(BuildDraft(), 190., .5)
        assert result.medal == '金' and first.record(result)
        keys = {first.key}
        for shape, density in (('hills', 'normal'), ('straight', 'busy'), ('straight', 'normal')):
            session.road_shape, session.traffic_density = shape, density
            session.start(track='endless', mode=mode, countdown=False, challenge_spec=spec)
            scores = session.engineering.scores
            assert session.simulation.road_shape == shape and session.engineering.trace.input_group == scores.context['input']
            assert scores.spec == distance_challenge_spec(shape, density)
            if (shape, density) == ('straight', 'normal'):
                assert scores.key == first.key and session.engineering.reference_result == result
                assert scores.records == first.records
            else:
                assert scores.key not in keys and session.engineering.reference_result is None
                keys.add(scores.key)
        session.start(seed=42, countdown=False)
        assert not session.challenge_spec.targets and session.engineering.reference_result is None
    finally:
        session.close()


def test_contact_episode_counts_traffic_and_guardrail_but_not_floor():
    sim = Simulation(track="endless", traffic_count=1)
    try:
        for _ in range(120):
            sim.step(Control())
        assert sim.snapshot().collisions == 0
        # 持续侧面接触只计一次；原车身中心完全重合会让轮胎起始包络穿入另一车。
        for _ in range(5):
            pose = sim.player._chassis.getTransform()
            hpr = pose.getHpr()
            width = sim.player.config.collision_half_width + sim.npcs[0].config.collision_half_width
            position = pose.getPos() + pose.getQuat().getRight() * (width - .001)
            sim.npcs[0].reset(tuple(position), hpr.x, hpr.y)
            contacts = sim._world.contactTestPair(sim.player._chassis, sim.npcs[0]._chassis).getContacts()
            assert contacts and min(hit.getManifoldPoint().getDistance() for hit in contacts) > -.002
            sim.step(Control())
            assert sim.snapshot().collisions == 1
        assert sim.snapshot().collisions == 1
        sim.npcs[0].reset((0, 200, 0.55))
        sim.reset_player((0, 8, 0.55))
        for _ in range(121):
            sim.step(Control())
        rail = sim._world.rayTestClosest(Vec3(0, 20, .4), Vec3(10, 20, .4), BitMask32.bit(0))
        assert rail.hasHit() and "rail" in rail.getNode().getName()
        x = rail.getHitPos().x - sim.config.collision_half_width - .05
        sim.reset_player((x, 20, .55))
        assert all(hit.getManifoldPoint().getDistance() >= 0 for hit in
                   sim._world.contactTestPair(sim.player._chassis, rail.getNode()).getContacts())
        sim.player._chassis.setLinearVelocity(Vec3(6, 0, 0))
        rail_contact = False
        for _ in range(30):
            sim.step(Control())
            rail_contact |= sim._world.contactTestPair(sim.player._chassis, rail.getNode()).getNumContacts() > 0
        assert rail_contact
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
