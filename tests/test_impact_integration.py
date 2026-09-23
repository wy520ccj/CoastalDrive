"""真实 Bullet 接触经 Snapshot 到分层播放器的完整路径。"""

import json
from io import StringIO

from panda3d.core import Vec3
from test_soundscape import FakeBase, phase

from simulation import Control, Simulation
from soundscape import Soundscape


def run_wall(speed):
    simulation = Simulation(track="test", traffic_count=0)
    sound = Soundscape(FakeBase())
    log = StringIO()
    sound.set_impact_diagnostic(log)
    try:
        simulation.reset_player((95, 716.8, .55))
        simulation._chassis.setLinearVelocity(Vec3(0, speed, 0))
        for _ in range(100):
            simulation.step(Control())
            sound.update(simulation.snapshot(), phase("driving"), None, 1 / 120)
        return [json.loads(line) for line in log.getvalue().splitlines()]
    finally:
        sound.close()
        simulation.close()


def test_real_wall_severity_and_layers_increase_without_wrong_contact_zone():
    first = []
    for speed in (2, 8, 20):
        decisions = [row for row in run_wall(speed)
                     if row["type"] == "decision" and row.get("layers")]
        assert decisions
        first.append(decisions[0])
        assert decisions[0]["zone"] == "front"
    assert [row["severity"] for row in first] == sorted(row["severity"] for row in first)
    assert first[0]["severity"] < .42
    assert {layer for layer, _ in first[0]["layers"]} == {"transient", "body"}
    assert {layer for layer, _ in first[1]["layers"]} >= {"transient", "body", "crunch"}
    assert first[2]["severity"] > first[1]["severity"]
    assert any(row.get("suppressed") == "major-impact-tail" for row in run_wall(20))


def test_moving_npc_uses_vehicle_recipe_while_gameplay_counts_one_episode():
    simulation = Simulation(track="test", traffic_count=1)
    sound = Soundscape(FakeBase())
    log = StringIO()
    sound.set_impact_diagnostic(log)
    try:
        simulation.reset_player((0, -8, .55))
        simulation._chassis.setLinearVelocity(Vec3(0, 8, 0))
        simulation.npcs[0].reset((0, 0, .55), heading=180)
        simulation.npcs[0]._chassis.setLinearVelocity(Vec3(0, -2, 0))
        simulation._tick = 1
        for _ in range(110):
            simulation.step(Control())
            sound.update(simulation.snapshot(), phase("driving"), None, 1 / 120)
        decisions = [json.loads(line) for line in log.getvalue().splitlines()
                     if '"type": "decision"' in line]
        assert any(row.get("material") == "vehicle" and row.get("layers") for row in decisions)
        assert simulation.player_collisions == 1
    finally:
        sound.close()
        simulation.close()


def test_sustained_real_rail_contact_plays_one_hit_and_one_scrape_loop():
    simulation = Simulation(track="highway", traffic_count=0)
    sound = Soundscape(FakeBase())
    log = StringIO()
    sound.set_impact_diagnostic(log)
    try:
        simulation.reset_player((7.2, 30, .55))
        simulation._chassis.setLinearVelocity(Vec3(0, 8, 0))
        for _ in range(840):
            simulation.step(Control(throttle=.15, steering=.2))
            sound.update(simulation.snapshot(), phase("driving"), None, 1 / 120)
        rows = [json.loads(line) for line in log.getvalue().splitlines()]
        assert sum(bool(row.get("layers")) for row in rows if row["type"] == "decision") == 1
        assert sum(row.get("state") == "attack" for row in rows if row["type"] == "scrape") == 1
        assert any(row.get("state") == "sustain" for row in rows)
        assert any(row.get("state") == "off" for row in rows)
    finally:
        sound.close()
        simulation.close()
