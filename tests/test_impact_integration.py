"""真实 Bullet 接触经 Snapshot 到分层播放器的完整路径。"""

import json
from dataclasses import asdict, replace
from io import StringIO
from itertools import pairwise

import pytest
from panda3d.core import Vec3
from test_soundscape import FakeBase, phase

from simulation import Control, Simulation
from soundscape import Soundscape
from vehicle_config import CAR
from vehicle_state import VehicleCommand


def record_frame(log, snapshot, audio):
    """同一轨迹保存完整120Hz接触/事件事实，供失败后核对播放器决策。"""
    log.write(json.dumps({"type": "frame", "tick": snapshot.tick,
                          "velocity": snapshot.player.velocity,
                          "scrape_state": audio.scrape_state,
                          "impacts": [asdict(event) for event in snapshot.impacts],
                          "contacts": [asdict(contact) for contact in snapshot.contacts]})+"\n")


def assert_impacts_match_native_facts(rows):
    """本工况的独立冲击均可听；持续接触不凭空生成撞击。"""
    pulses = {row["event_id"]: row for row in rows if row["type"] == "pulse"}
    decisions = [row for row in rows if row["type"] == "decision"]
    events = {f"{event['epoch']}:{event['tick']}:{event['index']}": event
              for row in rows if row["type"] == "frame" for event in row["impacts"]}
    assert set(pulses) == set(events)
    assert len(decisions) == len(pulses)
    assert {row["event_id"] for row in decisions} == set(pulses)
    for row in decisions:
        pulse = pulses[row["event_id"]]
        event = events[row["event_id"]]
        assert row["layers"]
        assert row["tick"] == event["tick"] == pulse["tick"]
        assert row["sources"] == event["sources"] == pulse["sources"]
        assert row["material"] == event["material"] == pulse["material"]
        assert row["zone"] == event["zone"] == pulse["zone"]
        assert row["raw_impulse"] == pytest.approx(pulse["raw_impulse_ns"])
        assert row["excess_impulse"] == pytest.approx(event["excess_impulse"])
        assert row["normal"] == pytest.approx(event["normal_speed"])
        assert row["tangential"] == pytest.approx(event["tangential_speed"])


def run_wall(speed, output=None):
    simulation = Simulation(track="test", traffic_count=0)
    sound = Soundscape(FakeBase())
    log = StringIO()
    sound.set_impact_diagnostic(log)
    if output is not None:
        simulation.set_impact_diagnostic(log, scenario=f"wall-{speed}")
    try:
        simulation.reset_player((95, 716.8, .55))
        simulation._chassis.setLinearVelocity(Vec3(0, speed, 0))
        simulation.player.tires.initialize_rolling(speed)
        for _ in range(100):
            simulation.step(Control())
            snapshot = simulation.snapshot()
            sound.update(snapshot, phase("driving"), None, 1 / 120)
            if output is not None:
                record_frame(log, snapshot, sound.impact_audio)
        if output is not None:
            output.write_text(log.getvalue(), encoding="utf-8")
        return [json.loads(line) for line in log.getvalue().splitlines()]
    finally:
        sound.close()
        simulation.close()


def test_real_wall_severity_and_layers_increase_without_wrong_contact_zone(tmp_path):
    first = []
    for speed in (2, 8, 20):
        rows = run_wall(speed, tmp_path/f"wall-{speed}.jsonl")
        assert_impacts_match_native_facts(rows)
        decisions = [row for row in rows
                     if row["type"] == "decision" and row.get("layers")]
        assert decisions
        first.append(decisions[0])
        assert decisions[0]["zone"] == "front"
    assert [row["severity"] for row in first] == sorted(row["severity"] for row in first)
    assert first[0]["severity"] < .42
    assert {layer for layer, _ in first[0]["layers"]} == {"transient", "body"}
    assert {layer for layer, _ in first[1]["layers"]} >= {"transient", "body", "crunch"}
    assert first[2]["severity"] > first[1]["severity"]
    # 弱尾部抑制由独立事件合同覆盖；真实墙撞无需人为产生第二个脉冲。


def test_moving_npc_uses_vehicle_recipe_while_gameplay_counts_one_episode():
    simulation = Simulation(track="test", traffic_count=1)
    sound = Soundscape(FakeBase())
    log = StringIO()
    sound.set_impact_diagnostic(log)
    try:
        simulation.reset_player((0, -8, .55))
        simulation._chassis.setLinearVelocity(Vec3(0, 8, 0))
        simulation.player.tires.initialize_rolling(8)
        simulation.npcs[0].reset((.5, 0, .55), heading=165, speed=2)
        simulation._tick = 1
        for _ in range(110):
            simulation.step(Control(throttle=1))
            sound.update(simulation.snapshot(), phase("driving"), None, 1 / 120)
        decisions = [json.loads(line) for line in log.getvalue().splitlines()
                     if '"type": "decision"' in line]
        assert any(row.get("material") == "vehicle" and row.get("layers") for row in decisions)
        assert simulation.player_collisions == 1
    finally:
        sound.close()
        simulation.close()


@pytest.mark.parametrize("centered,speed", [(False, 8), (True, 16)])
def test_real_rail_contact_plays_actual_hits_and_one_scrape_loop(centered, speed, tmp_path):
    simulation = Simulation(track="highway", traffic_count=0,
                            config=replace(CAR, centered_collision_support=centered))
    sound = Soundscape(FakeBase())
    log = StringIO()
    sound.set_impact_diagnostic(log)
    simulation.set_impact_diagnostic(log, scenario=f"rail-{centered}-{speed}")
    try:
        simulation.reset_player((6.9, 30, .55))
        simulation._chassis.setLinearVelocity(Vec3(.5, speed, 0))
        simulation.player.tires.initialize_rolling(speed)
        qualifying_pressure_ticks = []
        loop_handle = None
        for _ in range(840):
            simulation.step(VehicleCommand(throttle=.5, steering=2, direction=1))
            if any(c.material == "metal_barrier" and c.raw_impulse >= 25 and c.tangential_speed >= 1.6
                   for c in simulation.snapshot().contacts):
                qualifying_pressure_ticks.append(simulation.snapshot().tick)
            sound.update(simulation.snapshot(), phase("driving"), None, 1 / 120)
            record_frame(log, simulation.snapshot(), sound.impact_audio)
            handle = sound.impact_audio.scrape_sound
            if handle is not None:
                if loop_handle is None:
                    loop_handle = handle
                assert handle is loop_handle
                assert handle.play_count == 1
        (tmp_path/"rail.jsonl").write_text(log.getvalue(), encoding="utf-8")
        # 启动循环前要求真实压力连续达到原25Ns门槛；两种表示均经过实际受力。
        assert any(b == a+1 for a, b in pairwise(qualifying_pressure_ticks))
        rows = [json.loads(line) for line in log.getvalue().splitlines()]
        assert_impacts_match_native_facts(rows)
        assert sum(row.get("state") == "attack" for row in rows if row["type"] == "scrape") == 1, [r for r in rows if r["type"] == "scrape"]
        assert any(row.get("state") == "sustain" for row in rows)
        frames = {row["tick"]: row for row in rows if row["type"] == "frame"}
        attack = next(row for row in rows if row.get("state") == "attack")
        before = frames[attack["tick"]-1]["contacts"]
        current = frames[attack["tick"]]["contacts"]
        assert any(a["material"] == b["material"] == "metal_barrier"
                   and set(a["sources"]) & set(b["sources"])
                   and min(a["raw_impulse"], b["raw_impulse"]) >= 25
                   and min(a["tangential_speed"], b["tangential_speed"]) >= 1.6
                   for a in before for b in current)
        # 原840tick擦碰结束后只施加真实制动，保持原转角，不改写车辆状态。
        for _ in range(360):
            previous_scrape = sound.impact_audio.scrape_state
            simulation.step(VehicleCommand(brake=1, steering=2, direction=1))
            sound.update(simulation.snapshot(), phase("driving"), None, 1 / 120)
            record_frame(log, simulation.snapshot(), sound.impact_audio)
            if previous_scrape == "sustain" and sound.impact_audio.scrape_state == "release":
                contacts = simulation.snapshot().contacts
                assert not contacts or all(c.tangential_speed < 1.6 for c in contacts)
        stopped = simulation.snapshot()
        assert abs(stopped.player.speed) < 1.6
        assert not stopped.contacts or all(c.tangential_speed < 1.6 for c in stopped.contacts)
        assert sound.impact_audio.scrape_state == "off"
        stop_rows = [json.loads(line) for line in log.getvalue().splitlines()]
        (tmp_path/"rail.jsonl").write_text(log.getvalue(), encoding="utf-8")
        assert any(row.get("state") == "off" for row in stop_rows)
    finally:
        sound.close()
        simulation.close()
