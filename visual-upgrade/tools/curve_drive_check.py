"""Physical driving over curved segments; no renderer and no position controller."""

import argparse
import json
import math
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from endurance_check import EnduranceDriver, working_set_bytes
from panda3d.core import TransformState

from simulation import FIXED_DT, Simulation


def _nearby_npc_contact(sim, state):
    """Check active NPC pairs, avoiding Bullet queries for distant pairs."""
    active = [(i, car) for i, car in enumerate(state.traffic) if car.active]
    for offset, (i, first) in enumerate(active):
        for j, second in active[offset + 1 :]:
            dx = first.position[0] - second.position[0]
            dy = first.position[1] - second.position[1]
            if dx * dx + dy * dy > 12.0 * 12.0:
                continue
            if sim._world.contactTestPair(sim.npcs[i]._chassis, sim.npcs[j]._chassis).getNumContacts():
                return (i, j)
    return None


def _progress(path, *, seed, state, start_s, started, sim, trace, status):
    current_s = sim.road.locate(state.player)[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "status": status, "seed": seed, "simulation_seconds": state.time,
        "wall_seconds": time.perf_counter() - started,
        "player_distance_m": current_s - start_s,
        "last_sample": trace[-1] if trace else None,
    }, indent=2), encoding="utf-8")


def run(shape, seconds, seed, count, distance=0.0, progress_path=None):
    sim = Simulation(seed, track="endless", road_shape=shape, traffic_count=count)
    controller = EnduranceDriver(sim, seed + 701)
    trace, failures = [], []
    started = time.perf_counter()
    state = sim.snapshot()
    start_s = sim.road.locate(state.player)[0]
    next_progress = 10.0
    max_step = 0.0
    try:
        while True:
            x, y, z = state.player.position
            previous_position = (x, y + state.origin_y, z)
            sim.step(controller.sample(state, FIXED_DT))
            state = sim.snapshot()
            x, y, z = state.player.position
            step = math.dist(previous_position, (x, y + state.origin_y, z))
            max_step = max(max_step, step)
            contact = _nearby_npc_contact(sim, state)
            current_s, lateral = sim.road.locate(state.player)
            player_distance = current_s - start_s
            if step > 1:
                failures.append({"tick": state.tick, "type": "coordinate_jump", "meters": step})
                break
            if contact is not None or sim.collision_count:
                failures.append({"tick": state.tick, "type": "vehicle_collision", "npc_pair": contact,
                                 "player_contacts": sim.collision_count})
                break
            if state.tick % 120 == 0:
                errors = []
                for car in (state.player, *state.traffic):
                    if not car.active:
                        continue
                    cs, cd = sim.road.locate(car)
                    p = sim.road.sample_lateral(cs, cd)
                    height = car.position[2] - p.z
                    if abs(cd) > 6.9 or not 0.25 < height < 0.8 or abs(car.roll) > 15:
                        errors.append({"s": cs, "d": cd, "height": height, "roll": car.roll})
                sample = {
                    "time": state.time, "wall_seconds": time.perf_counter() - started,
                    "sample_period_seconds": 1.0,
                    "player_distance_m": player_distance,
                    "s": current_s, "d": lateral,
                    "rebases": sim.rebases, "origin_y": state.origin_y, "contacts": sim.collision_count,
                    "segments": len(sim.stream.segments), "rigid_bodies": sim._world.getNumRigidBodies(),
                    "transform_states": TransformState.getNumStates(),
                    "working_set_bytes": working_set_bytes(),
                    "changes": sum(x.lane_changes for x in sim.drivers), "errors": errors,
                }
                trace.append(sample)
                if errors or sim.collision_count:
                    failures.append({"tick": state.tick, "type": "player_or_road", "sample": sample})
                    break
                if progress_path is not None and state.time >= next_progress:
                    _progress(progress_path, seed=seed, state=state, start_s=start_s,
                              started=started, sim=sim, trace=trace, status="running")
                    next_progress += 10.0
            if distance > 0 and player_distance >= distance:
                break
            if state.time >= seconds:
                if distance > 0:
                    failures.append({"tick": state.tick, "type": "distance_timeout"})
                break
        result = {
            "shape": shape, "seed": seed, "traffic_count": count,
            "requested_seconds": seconds, "requested_distance_m": distance,
            "simulation_seconds": state.time, "wall_seconds": time.perf_counter() - started,
            "start_s": start_s, "player_distance_m": player_distance,
            "max_step_m": max_step,
            "working_set_bytes": working_set_bytes(),
            "rigid_bodies": sim._world.getNumRigidBodies(),
            "transform_states": TransformState.getNumStates(),
            "passed": not failures and (player_distance >= distance if distance > 0 else state.time >= seconds - FIXED_DT),
            "failures": failures, "trace": trace,
        }
        if failures:
            result["failure_state"] = asdict(state)
            result["drivers"] = [
                {"lane": d.lane, "target_lane": d.target_lane, "phase": d.phase,
                 "reason": d.reason, "recovering": d.recovering}
                for d in sim.drivers
            ]
        if progress_path is not None:
            _progress(progress_path, seed=seed, state=state, start_s=start_s,
                      started=started, sim=sim, trace=trace,
                      status="completed" if result["passed"] else "failed")
        return result
    except BaseException:
        if progress_path is not None:
            _progress(progress_path, seed=seed, state=state, start_s=start_s,
                      started=started, sim=sim, trace=trace, status="interrupted")
        raise
    finally:
        sim.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--shape", choices=("curves", "hills"), default="curves")
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--distance", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--traffic-count", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.seconds <= 0 or args.seeds <= 0 or args.distance < 0:
        parser.error("--seconds and --seeds must be positive; --distance cannot be negative")
    if args.seeds == 1:
        result_path = args.output
        progress_path = args.output.with_name(args.output.stem + ".progress.json")
        if result_path.exists():
            parser.error(f"refusing to overwrite existing result: {result_path}")
        result = run(args.shape, args.seconds, args.seed, args.traffic_count, args.distance, progress_path)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print({k: v for k, v in result.items() if k != "trace"})
        raise SystemExit(0 if result["passed"] else 1)
    args.output.mkdir(parents=True, exist_ok=True)
    for seed in range(args.seed, args.seed + args.seeds):
        result_path = args.output / f"seed-{seed}.json"
        if result_path.exists():
            parser.error(f"refusing to overwrite existing result: {result_path}")
        result = run(args.shape, args.seconds, seed, args.traffic_count, args.distance,
                     args.output / "progress.json")
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print({k: v for k, v in result.items() if k != "trace"}, flush=True)
        if not result["passed"]:
            raise SystemExit(1)
