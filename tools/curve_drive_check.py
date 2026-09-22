"""Physical driving over curved segments; no renderer and no position controller."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from endurance_check import EnduranceDriver

from simulation import FIXED_DT, Simulation


def run(shape, seconds, seed, count):
    sim = Simulation(seed, track="endless", road_shape=shape, traffic_count=count)
    controller = EnduranceDriver(sim, seed + 701)
    trace, failures = [], []
    try:
        for _ in range(int(seconds / FIXED_DT)):
            state = sim.snapshot()
            sim.step(controller.sample(state, FIXED_DT))
            state = sim.snapshot()
            if state.tick % 120:
                continue
            s, d = sim.road.locate(state.player)
            errors = []
            for car in (state.player, *state.traffic):
                if not car.active:
                    continue
                cs, cd = sim.road.locate(car)
                p = sim.road.sample_lateral(cs, cd)
                height = car.position[2] - p.z
                if abs(cd) > 6.9 or not 0.25 < height < 0.8 or abs(car.roll) > 15:
                    errors.append((cs, cd, height, car.roll))
            trace.append({"time": state.time, "s": s, "d": d, "rebases": sim.rebases,
                          "contacts": sim.collision_count, "segments": len(sim.stream.segments),
                          "changes": sum(x.lane_changes for x in sim.drivers), "errors": errors})
            if errors or sim.collision_count:
                failures.append(trace[-1])
                break
        result = {"shape": shape, "seed": seed, "traffic_count": count,
                  "passed": not failures and state.time >= seconds - FIXED_DT,
                  "failures": failures, "trace": trace}
        return result
    finally:
        sim.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--shape", choices=("curves", "hills"), default="curves")
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--traffic-count", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.shape, args.seconds, args.seed, args.traffic_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print({k: v for k, v in result.items() if k != "trace"})
    print(result["trace"][-1])
    raise SystemExit(0 if result["passed"] else 1)
