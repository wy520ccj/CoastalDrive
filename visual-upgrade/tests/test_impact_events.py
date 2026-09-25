import io
import json
import sys
from pathlib import Path

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


def sample(source=1, *, impulse=100, vn=2, vt=0, side="right", x=0.0,
           normal=(-1.0, 0.0, 0.0), material="metal_barrier"):
    return ContactSample((source,), material, side if material == "metal_barrier" else None, impulse, -0.01, 1,
                         vn, vt, (x, 0.0, 0.0), normal, "left")


def test_bullet_post_solve_four_point_rail_contact_is_one_real_event():
    simulation = Simulation(track="highway", traffic_count=0)
    diagnostic = io.StringIO()
    simulation.set_impact_diagnostic(diagnostic, scenario="test-rail")
    try:
        simulation.reset_player((5.8, 30, 0.55))
        simulation.player._chassis.setLinearVelocity(Vec3(8, 12, 0))
        for _ in range(30):
            simulation.step(Control())
            if simulation.snapshot().impacts:
                break
        snapshot = simulation.snapshot()
        assert len(snapshot.impacts) == 1
        impact = snapshot.impacts[0]
        assert impact.tick == snapshot.tick == 21
        assert impact.material == "metal_barrier"
        assert impact.raw_impulse > 8_000
        assert impact.normal_speed > 6
        assert impact.tangential_speed > 10
        assert impact.zone == "right"
        assert impact.event_id == f"{snapshot.contact_epoch}:21:0"
        row = json.loads(diagnostic.getvalue().splitlines()[-1])
        assert row["type"] == "pulse"
        assert row["new_impact"] is True
        assert row["continuing_contact"] is False
        assert row["point_count"] == 4
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
        simulation.npcs[0].reset((0, 0, 0.55), heading=180)
        simulation.npcs[0]._chassis.setLinearVelocity(Vec3(0, -2, 0))
        simulation._tick = 1
        vehicle_impacts = []
        for _ in range(110):
            simulation.step(Control())
            vehicle_impacts.extend(
                impact for impact in simulation.snapshot().impacts
                if impact.material == "vehicle"
            )
        assert len(vehicle_impacts) >= 2
        assert vehicle_impacts[0].sources != ()
        assert simulation.player_collisions == 1
    finally:
        simulation.close()


def test_five_second_rail_scrape_stays_contact_without_repeated_impacts():
    simulation = Simulation(track="highway", traffic_count=0)
    try:
        simulation.reset_player((7.2, 30, 0.55))
        simulation.player._chassis.setLinearVelocity(Vec3(0, 8, 0))
        contact_ticks = []
        impacts = []
        for tick in range(840):
            simulation.step(Control(throttle=0.15, steering=0.2))
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
