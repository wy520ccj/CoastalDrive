"""Long-distance streaming and physical traffic checks, without a renderer."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panda3d.core import TransformState

from simulation import Control, Simulation


def run(seed, seconds, distance, traffic_count=12):
    sim = Simulation(seed, track="endless", traffic_count=0 if distance else traffic_count)
    sim.player.reverse_enabled = False
    trace, failures = [], []
    before = sim.snapshot()
    started = time.perf_counter()
    try:
        while True:
            sim.step(Control(throttle=1) if distance else Control(brake=1))
            state = sim.snapshot()
            mileage = state.origin_y + state.player.position[1] - 8
            if sim.collision_count:
                failures.append((state.tick, "player_collision"))
                break
            if not 0.3 < state.player.position[2] < 0.7:
                failures.append((state.tick, "player_height", state.player.position))
                break
            if state.tick % 120 == 0:
                for i, car in enumerate(state.traffic):
                    if car.active and (abs(car.position[0]) > 6.9 or abs(car.roll) > 10):
                        failures.append((state.tick, "off_road", i, car.position))
                trace.append(
                    {
                        "time": state.time,
                        "mileage": mileage,
                        "segments": len(sim.stream.segments),
                        "bodies": sim._world.getNumRigidBodies(),
                        "rebases": sim.rebases,
                        "cycles": sim.traffic_cycles,
                        "lane_changes": sum(d.lane_changes for d in sim.drivers),
                        "transform_states": TransformState.getNumStates(),
                    }
                )
            for i, car in enumerate(sim.npcs):
                if not state.traffic[i].active:
                    continue
                for j in range(i):
                    if (
                        state.traffic[j].active
                        and sim._world.contactTestPair(
                            car._chassis, sim.npcs[j]._chassis
                        ).getNumContacts()
                    ):
                        failures.append((state.tick, "npc_collision", j, i))
            old_y = before.origin_y + before.player.position[1]
            if abs(state.origin_y + state.player.position[1] - old_y) > 0.5:
                failures.append((state.tick, "coordinate_jump"))
            if failures or (mileage >= distance if distance else state.time >= seconds):
                break
            before = state
        return {
            "seed": seed,
            "seconds": state.time,
            "mileage": mileage,
            "wall_seconds": time.perf_counter() - started,
            "passed": not failures,
            "failures": failures,
            "trace": trace,
        }
    finally:
        sim.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--seconds", type=float, default=600)
    parser.add_argument("--distance", type=float, default=0)
    parser.add_argument("--traffic-count", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for seed in range(args.seed, args.seed + args.seeds):
        result = run(seed, args.seconds, args.distance, args.traffic_count)
        (args.output / f"seed-{seed}.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        print({k: v for k, v in result.items() if k != "trace"}, flush=True)
