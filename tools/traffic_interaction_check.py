"""Small, repeatable physical traffic interaction checks for the endless road."""

import argparse
import json
import sys
import time
from pathlib import Path

from panda3d.core import Vec3

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from simulation import FIXED_DT, Simulation
from traffic import Driver
from vehicle_state import Control

ROOT = Path(__file__).resolve().parents[1]
LANE_X = (-4.5, 0.0, 4.5)


def _place(sim, player_lane, player_y, player_speed, npcs):
    """Warm Bullet for one second, then place cars and give them initial velocity."""
    sim.reset_player((LANE_X[player_lane], player_y, 0.55), 0)
    for car, (lane, y, speed) in zip(sim.npcs, npcs):
        car.reset((LANE_X[lane], y, 0.55), 0)
    for _ in range(120):
        sim.step(Control(brake=1))

    sim.reset_player((LANE_X[player_lane], player_y, 0.55), 0)
    sim.player._chassis.setLinearVelocity(Vec3(0, player_speed, 0))
    for index, (car, (lane, y, speed)) in enumerate(zip(sim.npcs, npcs)):
        car.reset((LANE_X[lane], y, 0.55), 0)
        car._chassis.setLinearVelocity(Vec3(0, speed, 0))
        sim.drivers[index].lane = lane
        sim.drivers[index].target_lane = lane
        sim.drivers[index].recovering = False


def _contact(sim, first, second):
    return sim._world.contactTestPair(first._chassis, second._chassis).getNumContacts() > 0


def _frame(sim, case, frames, rows, contacts):
    snap = sim.snapshot()
    players = {
        "position": [round(value, 4) for value in snap.player.position],
        "speed_mps": round(snap.player.speed, 4),
        "brake": round(snap.player.brake, 4),
        "steering": round(snap.player.steering, 4),
    }
    traffic = []
    for index, state in enumerate(snap.traffic):
        traffic.append(
            {
                "index": index,
                "position": [round(value, 4) for value in state.position],
                "speed_mps": round(state.speed, 4),
                "brake": round(state.brake, 4),
                "steering": round(state.steering, 4),
                "active": state.active,
                "signal": state.signal,
                "reason": sim.drivers[index].reason,
                "hazard_brake": sim.drivers[index].hazard_brake,
            }
        )
        if state.active and _contact(sim, sim.player, sim.npcs[index]):
            contacts.append({"tick": snap.tick, "npc": index})
    rows.append({"tick": snap.tick, "time_s": round(snap.time, 4), "player": players, "traffic": traffic})
    frames.append(snap)


def _run_case(
    name, seed, player_lane, player_y, player_speed, npcs, seconds, configure=None, control_for=None
):
    sim = Simulation(seed, track="endless", traffic_count=len(npcs))
    rows = []
    contacts = []
    frames = []
    start = time.perf_counter()
    try:
        sim.set_checkpoint_frames_enabled(False)
        _place(sim, player_lane, player_y, player_speed, npcs)
        if configure:
            configure(sim)
        for tick in range(round(seconds / FIXED_DT)):
            control = control_for(sim, tick * FIXED_DT) if control_for else Control()
            sim.step(control)
            _frame(sim, name, frames, rows, contacts)

        first = frames[0]
        last = frames[-1]
        player_x = [frame.player.position[0] for frame in frames]
        player_speeds = [frame.player.speed for frame in frames]
        metrics = {
            "duration_s": seconds,
            "ticks": len(rows),
            "wall_seconds": round(time.perf_counter() - start, 4),
            "player_start_position": first.player.position,
            "player_end_position": last.player.position,
            "player_min_speed_mps": round(min(player_speeds), 4),
            "player_max_brake": round(max(row["player"]["brake"] for row in rows), 4),
            "player_lateral_span_m": round(max(player_x) - min(player_x), 4),
            "contacts": contacts,
            "contact_count": len(contacts),
            "traffic": [],
        }
        for index in range(len(npcs)):
            states = [frame.traffic[index] for frame in frames]
            xs = [state.position[0] for state in states]
            metrics["traffic"].append(
                {
                    "index": index,
                    "start_position": states[0].position,
                    "end_position": states[-1].position,
                    "min_speed_mps": round(min(state.speed for state in states), 4),
                    "max_brake": round(max(state.brake for state in states), 4),
                    "max_steering": round(max(abs(state.steering) for state in states), 4),
                    "lateral_span_m": round(max(xs) - min(xs), 4),
                    "lane_changes": sim.drivers[index].lane_changes,
                    "phase_end": getattr(sim.drivers[index], "phase", "unknown"),
                }
            )

        if name.startswith("rear_"):
            approach_rows = [
                row for row, frame in zip(rows, frames)
                if frame.player.position[1] < frame.traffic[0].position[1]
            ]
            metrics["rear_approach"] = {
                "occurred": bool(approach_rows),
                "ticks": len(approach_rows),
                "max_npc_brake_while_player_behind": round(
                    max((row["traffic"][0]["brake"] for row in approach_rows), default=0), 4
                ),
                "contact_during_approach": any(
                    any(contact["tick"] == row["tick"] for contact in contacts)
                    for row in approach_rows
                ),
            }

        failures = []
        if name in ("stationary_block", "slow_lead", "both_sides_blocked"):
            if metrics["traffic"][0]["max_brake"] < 0.1:
                failures.append("NPC never applied measurable braking")
            if metrics["contact_count"]:
                failures.append("NPC contacted player")
        if name == "both_sides_blocked" and metrics["traffic"][0]["lane_changes"]:
            failures.append("NPC changed lane while adjacent escape lane was blocked")
        if name == "rear_approach" and not metrics["rear_approach"]["occurred"]:
            failures.append("player never reached the NPC from behind")
        if name == "rear_approach":
            if metrics["rear_approach"]["max_npc_brake_while_player_behind"] > 0.1:
                failures.append("NPC slowed for the approaching rear car on an empty road")
            if not metrics["traffic"][0]["lane_changes"] or contacts:
                failures.append("NPC did not yield into the available gap")
        if name == "rear_blocked":
            if metrics["rear_approach"]["max_npc_brake_while_player_behind"] > 0.1:
                failures.append("NPC braked for a rear approach with both sides occupied")
            if metrics["traffic"][0]["lateral_span_m"] > 0.3 or contacts:
                failures.append("NPC moved into its occupied neighbors")
        if name == "rear_too_close" and not contacts:
            failures.append("impossible late approach unexpectedly escaped contact")
        if name == "rear_too_close" and contacts:
            first_contact = min(item["tick"] for item in contacts)
            before_contact = [row for row in rows if row["tick"] < first_contact]
            metrics["brake_before_contact"] = max(row["traffic"][0]["brake"] for row in before_contact)
            if metrics["brake_before_contact"] > 0.1:
                failures.append("NPC braked before an unavoidable rear impact")
        if name == "real_control_cut_in":
            if metrics["player_lateral_span_m"] < 3.5 or abs(last.player.position[0]) > 0.5:
                failures.append("player did not make a physical lateral cut-in")
            if any(abs(x) > 5 for x in player_x):
                failures.append("cut-in fixture left the road")
            if metrics["traffic"][0]["max_brake"] < 0.1:
                failures.append("NPC did not react to the slower cut-in")
            if metrics["contact_count"]:
                failures.append("cut-in contacted player")
        return {"name": name, "seed": seed, "passed": not failures, "failures": failures, "metrics": metrics, "frames": rows}
    finally:
        sim.close()


def run(seed=23):
    player_driver = Driver(1, 18)

    def player_cut_in(sim, elapsed):
        t = min(1, elapsed / 3)
        player_driver.target_lateral = -4.5 + 4.5 * t * t * (3 - 2 * t)
        car = sim.player.snapshot()
        steer = player_driver.control(car, [], sim.road, [sim.road.locate(car)]).steering
        error = 18 - car.speed
        return Control(steering=steer, throttle=max(0, min(1, 0.35 + error * 0.2)))

    def rear_speed_feedback(sim, _elapsed):
        error = 32.0 - sim.player.snapshot().speed
        return Control(throttle=max(0.0, min(1.0, 0.55 + error * 0.08)))

    def set_rear_target(sim):
        for driver in sim.drivers:
            driver.preferred_speed = 25.0
            driver.cruise = 25.0
            driver.target_speed = 25.0
            driver.speed_clock = 100.0

    cases = [
        _run_case("stationary_block", seed, 1, 108, 0, [(1, 8, 20)], 8),
        _run_case("slow_lead", seed, 1, 98, 10, [(1, 58, 25)], 6),
        _run_case("both_sides_blocked", seed, 0, 108, 10, [(0, 58, 25), (1, 78, 10)], 6),
        _run_case("rear_approach", seed, 1, 38, 32, [(1, 98, 20)], 8, set_rear_target, rear_speed_feedback),
        _run_case("rear_blocked", seed, 1, 38, 32, [(1, 98, 20), (0, 98, 20), (2, 98, 20)], 3, set_rear_target, rear_speed_feedback),
        _run_case("rear_too_close", seed, 1, 90, 32, [(1, 98, 20)], 1, set_rear_target, rear_speed_feedback),
    ]

    cases.append(_run_case("real_control_cut_in", seed, 0, 70, 18, [(1, 40, 25)], 8, control_for=player_cut_in))
    return {"seed": seed, "track": "endless", "cases": cases, "passed": all(item["passed"] for item in cases)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--output", type=Path, default=ROOT / "logs/traffic-v2/interactions.json")
    args = parser.parse_args()
    report = run(args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "passed": report["passed"], "cases": [
        {"name": item["name"], "passed": item["passed"], "failures": item["failures"], "metrics": item["metrics"]}
        for item in report["cases"]
    ]}, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
