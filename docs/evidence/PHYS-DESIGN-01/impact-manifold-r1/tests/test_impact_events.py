import io
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from panda3d.core import Vec3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from impact_events import (
    ContactSample,
    ImpactDetectionConfig,
    ImpactTracker,
    aggregate_contacts,
)
from simulation import Control, Simulation
from vehicle_config import CAR
from vehicle_state import VehicleCommand


def sample(source=1, *, impulse=100, vn=2, vt=0, side="right", x=0.0,
           normal=(-1.0, 0.0, 0.0), material="metal_barrier"):
    return ContactSample((source,), material, side if material == "metal_barrier" else None, impulse, -0.01, 1,
                         vn, vt, (x, 0.0, 0.0), normal, "left")


@pytest.mark.parametrize("centered", [False, True])
def test_bullet_post_solve_rail_manifold_is_one_real_event(centered):
    simulation = Simulation(track="highway", traffic_count=0,
                            config=replace(CAR, centered_collision_support=centered))
    diagnostic = io.StringIO()
    simulation.set_impact_diagnostic(diagnostic, scenario="test-rail")
    native_points = {}
    original_read = simulation._read_impact_contacts

    def observe_native(before, *, accumulated=None, publish=True):
        points = native_points.setdefault(simulation._tick + 1, [])
        for manifold in simulation._world.getManifolds():
            node0, node1 = manifold.getNode0(), manifold.getNode1()
            if not ((node0 == simulation.player._chassis and "rail" in node1.getName())
                    or (node1 == simulation.player._chassis and "rail" in node0.getName())):
                continue
            points.extend((max(0., point.getAppliedImpulse()), point.getLifeTime())
                          for point in manifold.getManifoldPoints()
                          if point.getDistance() <= 0 or point.getAppliedImpulse() > 0)
        return original_read(before, accumulated=accumulated, publish=publish)

    simulation._read_impact_contacts = observe_native
    try:
        simulation.reset_player((5.8, 30, 0.55))
        simulation.player._chassis.setLinearVelocity(Vec3(8, 12, 0))
        simulation.player.tires.initialize_rolling(12)
        first_native_tick = None
        for _ in range(30):
            simulation.step(Control())
            # 时间戳对应真实求解后冲量；轮胎/传动模型变化不应把旧到达拍写成事件合同。
            rail_points = [point for manifold in simulation._world.getManifolds()
                           if ((manifold.getNode0() == simulation.player._chassis
                                and "rail" in manifold.getNode1().getName())
                               or (manifold.getNode1() == simulation.player._chassis
                                   and "rail" in manifold.getNode0().getName()))
                           for point in manifold.getManifoldPoints() if point.getAppliedImpulse() > 0]
            if rail_points and first_native_tick is None:
                first_native_tick = simulation.snapshot().tick
            if simulation.snapshot().impacts:
                break
        snapshot = simulation.snapshot()
        assert len(snapshot.impacts) == 1
        impact = snapshot.impacts[0]
        assert impact.tick == snapshot.tick == first_native_tick
        assert impact.material == "metal_barrier"
        points = native_points[impact.tick]
        assert impact.raw_impulse == sum(impulse for impulse, _lifetime in points) > 0
        assert impact.normal_speed > 6
        assert impact.tangential_speed > 10
        assert impact.zone == "right"
        assert impact.event_id == f"{snapshot.contact_epoch}:{first_native_tick}:0"
        row = json.loads(diagnostic.getvalue().splitlines()[-1])
        assert row["type"] == "pulse"
        assert row["new_impact"] is True
        assert row["continuing_contact"] is False
        # 两种布局首个角接触的点数由实际姿态决定，完整聚合每个子步的真实manifold。
        assert row["point_count"] == len(points)
        assert row["raw_impulse_ns"] == impact.raw_impulse
        assert row["max_bullet_lifetime"] == 1
    finally:
        simulation.close()


def test_contact_zone_matches_actual_chassis_face():
    assert Simulation._contact_zone((0, 2.05, .42), (0, -1, 0)) == "front"
    assert Simulation._contact_zone((0, -2.05, .42), (0, 1, 0)) == "rear"
    assert Simulation._contact_zone((.78, 0, .42), (-1, 0, 0)) == "right"
    assert Simulation._contact_zone((-.78, 0, .42), (1, 0, 0)) == "left"
    assert Simulation._contact_zone((0, 0, .84), (0, 0, -1)) == "roof"
    assert Simulation._contact_zone((0, 0, 0), (0, 0, 1)) == "underbody"


def test_moving_npc_contact_emits_audio_events_without_changing_episode_count():
    simulation = Simulation(track="test", traffic_count=1)
    try:
        simulation.reset_player((0, -8, 0.55), heading=0)
        simulation.player._chassis.setLinearVelocity(Vec3(0, 8, 0))
        simulation.player.tires.initialize_rolling(8)
        # 斜向来车先撞角再旋转重撞，两个真实音频脉冲属于同一事故窗口。
        simulation.npcs[0].reset((.5, 0, 0.55), heading=165, speed=2)
        simulation._tick = 1
        vehicle_impacts = []
        for _ in range(110):
            simulation.step(Control(throttle=1))
            vehicle_impacts.extend(
                impact for impact in simulation.snapshot().impacts
                if impact.material == "vehicle"
            )
        assert len(vehicle_impacts) >= 2
        assert vehicle_impacts[0].tick < vehicle_impacts[1].tick
        assert vehicle_impacts[0].sources != ()
        assert simulation.player_collisions == 1
    finally:
        simulation.close()


@pytest.mark.parametrize("finite", [False, True])
def test_five_second_rail_scrape_stays_contact_without_repeated_impacts(finite):
    simulation = Simulation(track="highway", traffic_count=0,
                            config=replace(CAR, finite_drivetrain=finite))
    try:
        # 从护栏内侧留2cm起步，先真实撞击，再持续沿栏轻压。
        rail = simulation._world.rayTestClosest(Vec3(0, 30, .55), Vec3(10, 30, .55))
        assert rail.hasHit() and "rail" in rail.getNode().getName()
        start_x = rail.getHitPos().x - CAR.collision_half_width - .02
        simulation.reset_player((start_x, 30, 0.55))
        assert not simulation._world.contactTest(simulation.player._chassis).getNumContacts()
        simulation.player._chassis.setLinearVelocity(
            Vec3(2 * ImpactDetectionConfig().normal_enter, 8, 0))
        simulation.player.tires.initialize_rolling(8)
        contact_ticks = []
        impacts = []
        # 接近和传动/车身收敛也占时间；随后仍须有完整5秒逐拍真实接触。
        for tick in range(1440):
            # 车身转动时修正真实轮角，使前轮始终向栏偏5°；不用改姿态维持接触。
            simulation.step(VehicleCommand(
                throttle=.5, steering=5 + simulation.snapshot().player.heading, direction=1))
            if any(contact.material == "metal_barrier"
                   for contact in simulation.snapshot().contacts):
                contact_ticks.append(tick + 1)
            impacts.extend(simulation.snapshot().impacts)
        longest = 0
        run = 0
        previous = None
        for tick in contact_ticks:
            run = run + 1 if previous == tick - 1 else 1
            longest = max(longest, run)
            previous = tick
        assert longest >= 600
        assert len(impacts) == 1
    finally:
        simulation.close()


def test_rotational_velocity_contributes_at_contact_point():
    body = object()
    saved = {body: (Vec3(1, 0, 0), Vec3(0, 0, 2), Vec3(0, 0, 0))}
    velocity = Simulation._contact_velocity(body, Vec3(0, 3, 0), saved)
    assert tuple(velocity) == (-5.0, 0.0, 0.0)


def test_four_contact_points_and_adjacent_rail_bodies_aggregate_by_real_surface():
    points = [sample(1, impulse=value, x=position) for value, position in
              ((10, -1.5), (20, -0.5), (30, 0.5), (40, 1.5))]
    points += [sample(2, impulse=50, x=1.8)]
    clusters = aggregate_contacts(points)
    assert len(clusters) == 1
    assert clusters[0].sources == (1, 2)
    assert clusters[0].point_count == 5
    assert clusters[0].raw_impulse == 150


def test_sustained_contact_does_not_repeat_but_reimpact_can_fire():
    tracker = ImpactTracker(ImpactDetectionConfig())
    assert len(tracker.update(aggregate_contacts([sample(1, impulse=200)]), 1, 9)[0]) == 1
    for tick in range(2, 9):
        events, contacts = tracker.update(aggregate_contacts([sample(1, impulse=80, vn=0)]), tick, 9)
        assert events == ()
        assert contacts[0].contact_age_ticks == tick
    tracker.update((), 9, 9)
    tracker.update((), 10, 9)
    events, _ = tracker.update(aggregate_contacts([sample(1, impulse=220)]), 11, 9)
    assert len(events) == 1
    assert events[0].tick == 11


def test_large_solved_impulse_rise_can_emit_upgrade_during_same_contact():
    tracker = ImpactTracker()
    first, _ = tracker.update(aggregate_contacts([sample(1, impulse=200)]), 1, 12)
    assert len(first) == 1
    upgraded, _ = tracker.update(aggregate_contacts([sample(1, impulse=700)]), 2, 12)
    assert len(upgraded) == 1
    assert upgraded[0].tick == 2
    unchanged, _ = tracker.update(aggregate_contacts([sample(1, impulse=500)]), 3, 12)
    assert unchanged == ()


def test_barrier_segment_identity_switch_does_not_create_new_impact():
    tracker = ImpactTracker()
    first, _ = tracker.update(aggregate_contacts([sample(1, impulse=200)]), 1, 4)
    assert len(first) == 1
    for tick in range(2, 20):
        source = 1 if tick % 2 else 2
        events, contacts = tracker.update(
            aggregate_contacts([sample(source, impulse=100, vn=0, x=0.1 * (tick % 3))]),
            tick, 4,
        )
        assert events == ()
        assert contacts[0].contact_age_ticks == tick


def test_static_support_load_is_contact_without_impact():
    tracker = ImpactTracker()
    for tick in range(1, 40):
        events, contacts = tracker.update(
            aggregate_contacts([sample(3, impulse=98.1, vn=0)]), tick, 2
        )
        assert events == ()
        assert len(contacts) == 1


def test_other_body_and_opposite_normals_remain_separate_clusters():
    points = [sample(1, normal=(-1, 0, 0), material="vehicle"),
              sample(1, normal=(1, 0, 0), material="vehicle"),
              sample(2, normal=(-1, 0, 0), material="vehicle")]
    clusters = aggregate_contacts(points)
    assert len(clusters) == 3
