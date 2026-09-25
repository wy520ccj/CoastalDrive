"""Headless H4A traffic measurements; no Panda3D window is created."""

import argparse
import json
import random
import sys
import time
from pathlib import Path

from panda3d.core import Vec3

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coastal_map import offset_point, point_at
from simulation import Simulation
from traffic import extents
from vehicle_state import FIXED_DT, Control


def run(seconds, count, track, seed):
    sim = Simulation(seed, track=track, traffic_count=count)
    try:
        if track == "coastal":
            point = point_at(0)
            x, y, z = offset_point(point, 4.7, 0.0)
            sim.reset_player((x, y, z + 0.55), point.heading, point.grade)
        else:
            sim.reset_player()
        sim.player.reverse_enabled = False
        sim.set_checkpoint_frames_enabled(False)
        initial = sim.snapshot().traffic
        previous = [sim.road.locate(state)[0] for state in initial]
        previous_generation = [state.generation for state in initial]
        was_active = [state.active for state in initial]
        distance = [0.0] * count
        active_ticks = [0] * count
        laps = [0.0] * count
        route_error = [0.0] * count
        stopped_ticks = [0] * count
        player_collision_steps = 0
        npc_collision_steps = 0
        npc_collision_pairs = []
        failures = []
        failure_keys = set()
        ticks = int(seconds / FIXED_DT)
        started = time.perf_counter()
        for _ in range(ticks):
            player_contacts_before = sim.collision_count
            sim.step(Control(brake=1))
            player_contact = sim.collision_count > player_contacts_before
            player_collision_steps += player_contact
            snapshot = sim.snapshot()
            states = snapshot.traffic
            locations = [sim.road.locate(state) for state in states]
            for i, (state, (along, lateral)) in enumerate(zip(states, locations)):
                if not state.active:
                    was_active[i] = False
                    continue
                if not was_active[i] or state.generation != previous_generation[i]:
                    previous[i] = along
                else:
                    distance[i] += sim.road.delta(along, previous[i])
                previous[i] = along
                previous_generation[i] = state.generation
                was_active[i] = True
                active_ticks[i] += 1
                laps[i] = distance[i] / sim.road.length
                route_error[i] = max(
                    route_error[i], abs(lateral - sim.road.lanes[sim.drivers[i].lane])
                )
                stopped_ticks[i] += state.speed < 0.5
            if player_contact:
                key = ("player_npc_collision",)
                if key not in failure_keys:
                    failure_keys.add(key)
                    failures.append({"kind": key[0], "tick": snapshot.tick})
            for i, first in enumerate(sim.npcs):
                if not states[i].active:
                    continue
                for j, second in enumerate(sim.npcs[i + 1 :], i + 1):
                    if not states[j].active:
                        continue
                    contact = (
                        sim._world.contactTestPair(first._chassis, second._chassis).getNumContacts()
                        > 0
                    )
                    npc_collision_steps += contact
                    if contact:
                        pair = [i, j]
                        pair_key = ("npc_npc_collision", i, j)
                        if pair_key not in failure_keys:
                            failure_keys.add(pair_key)
                            npc_collision_pairs.append({"tick": snapshot.tick, "pair": pair})
                            failures.append(
                                {"kind": pair_key[0], "tick": snapshot.tick, "pair": pair}
                            )
            for i, error in enumerate(route_error):
                if error > 3.0:
                    key = ("route_error", i)
                    if key not in failure_keys:
                        failure_keys.add(key)
                        failures.append(
                            {
                                "kind": key[0],
                                "tick": snapshot.tick,
                                "car": i,
                                "value_m": round(error, 3),
                            }
                        )
        physics_seconds = time.perf_counter() - started
        criteria_failures = list(failures)
        if seconds >= 900 and track == "coastal" and count == 8:
            for i, lap_count in enumerate(laps):
                if lap_count < 3.0:
                    criteria_failures.append(
                        {
                            "kind": "insufficient_laps",
                            "tick": ticks,
                            "car": i,
                            "value": round(lap_count, 3),
                        }
                    )
                if active_ticks[i] and stopped_ticks[i] / active_ticks[i] > 0.2:
                    criteria_failures.append(
                        {
                            "kind": "traffic_stopped",
                            "tick": ticks,
                            "car": i,
                            "value": round(stopped_ticks[i] / active_ticks[i], 3),
                        }
                    )
        elif track == "coastal":
            for i in range(count):
                if active_ticks[i] and stopped_ticks[i] / active_ticks[i] > 0.5:
                    criteria_failures.append(
                        {
                            "kind": "traffic_stopped",
                            "tick": ticks,
                            "car": i,
                            "value": round(stopped_ticks[i] / active_ticks[i], 3),
                        }
                    )
        return {
            "seconds": seconds,
            "ticks": ticks,
            "track": track,
            "seed": seed,
            "traffic_count": count,
            "physics_seconds": round(physics_seconds, 4),
            "player_collision_steps": player_collision_steps,
            "npc_collision_steps": npc_collision_steps,
            "npc_collision_pairs": npc_collision_pairs,
            "traffic_cycles": sim.traffic_cycles,
            "failures": criteria_failures,
            "passed": not criteria_failures,
            "npcs": [
                {
                    "index": i,
                    "active": bool(states[i].active),
                    "generation": states[i].generation,
                    "cumulative_m": round(distance[i], 3),
                    "max_route_error_m": round(route_error[i], 3),
                    "laps": round(laps[i], 3),
                    "stopped": active_ticks[i] > 0 and stopped_ticks[i] == active_ticks[i],
                    "stopped_fraction": round(stopped_ticks[i] / active_ticks[i], 3)
                    if active_ticks[i]
                    else 0.0,
                }
                for i in range(count)
            ],
        }
    finally:
        sim.close()


def recovery_run(count):
    results = []
    for seed in range(count):
        sim = Simulation(seed, track="highway", traffic_count=22)
        try:
            rng = random.Random(seed * 7919 + 17)
            sim.reset_player((0, 700, 0.55), 0)
            sim.player.reverse_enabled = False
            forced_blocked = seed % 10 == 0
            spacing = 12.0 if forced_blocked else 16.0 + rng.uniform(0.0, 8.0)
            lane_order = list(range(3))
            for i, car in enumerate(sim.npcs):
                if i % 3 == 0:
                    rng.shuffle(lane_order)
                lane = lane_order[i % 3]
                y = 700 + (i // 3 - 3) * spacing + (0 if forced_blocked else rng.uniform(-1.0, 1.0))
                heading = 0 if forced_blocked else rng.uniform(-4.0, 4.0)
                car.reset((sim.road.lanes[lane], y, 0.55), heading)
            rear_index = rng.randrange(3)
            rear_speed = rng.uniform(25, 40)
            sim.npcs[rear_index]._chassis.setLinearVelocity(Vec3(0, rear_speed, 0))
            player = sim.player.snapshot()
            before_position = tuple(player.position)
            player_s, _ = sim.road.locate(player)
            min_gap = min(
                abs(sim.road.delta(sim.road.locate(car.snapshot())[0], player_s))
                - extents(car.snapshot().heading, 0)[1]
                - extents(player.heading, 0)[1]
                for car in sim.npcs
            )
            recovered = sim.recover_player()
            after = sim.player.snapshot()
            contacts = sum(
                sim._world.contactTestPair(sim.player._chassis, car._chassis).getNumContacts() > 0
                for car in sim.npcs
            )
            failures = []
            if not recovered and tuple(after.position) != before_position:
                failures.append({"kind": "blocked_player_moved", "seed": seed})
            if recovered and contacts:
                failures.append({"kind": "post_reset_contact", "seed": seed})
            results.append(
                {
                    "seed": seed,
                    "dense_fixture": True,
                    "forced_blocked_fixture": forced_blocked,
                    "fixture_spacing_m": round(spacing, 3),
                    "high_speed_rear_index": rear_index,
                    "high_speed_rear_mps": round(rear_speed, 3),
                    "min_center_gap_m": round(min_gap, 3),
                    "recovered": recovered,
                    "post_reset_contacts": contacts,
                    "post_reset_position": after.position,
                    "failures": failures,
                }
            )
        finally:
            sim.close()
    failures = [f for item in results for f in item["failures"]]
    return {
        "cases": count,
        "success_count": sum(item["recovered"] for item in results),
        "blocked_count": sum(not item["recovered"] for item in results),
        "results": results,
        "failures": failures,
        "passed": not failures,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--track", choices=("coastal", "highway"), default="coastal")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--recovery-count", type=int)
    args = parser.parse_args()
    report = (
        recovery_run(args.recovery_count)
        if args.recovery_count is not None
        else run(args.seconds, args.count, args.track, args.seed)
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
