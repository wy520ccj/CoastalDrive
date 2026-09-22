"""Source and packaged entry point; headless runs never import the renderer."""

import argparse
import json
import logging
import traceback
from dataclasses import asdict
from pathlib import Path

from paths import user_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--steps", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--road-shape", choices=("straight", "curves", "hills"), default="straight")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--window-smoke", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--track", choices=("coastal", "highway", "endless", "test"), default="coastal"
    )
    args = parser.parse_args()
    if args.steps <= 0:
        parser.error("--steps must be positive")
    if args.headless:
        from controls import ConstantController
        from simulation import FIXED_DT, Control, Simulation

        simulation = Simulation(args.seed, track=args.track, road_shape=args.road_shape)
        controller = ConstantController(Control(throttle=0.5))
        try:
            for _ in range(args.steps):
                simulation.step(controller.sample(simulation.snapshot(), FIXED_DT))
            print(json.dumps(asdict(simulation.snapshot()), indent=2))
        finally:
            simulation.close()
        return 0
    logging.basicConfig(filename=user_data() / "runtime.log", level=logging.INFO, encoding="utf-8")
    from application import CoastalDrive

    smoke = args.smoke or args.window_smoke
    app = CoastalDrive(
        smoke=smoke,
        onscreen=args.window_smoke,
        output=args.output,
        seed=args.seed,
        track=args.track,
        road_shape=args.road_shape,
    )
    try:
        app.run()
        return 0 if not smoke or getattr(app, "smoke_passed", False) else 1
    finally:
        app.close_game()


if __name__ == "__main__":
    try:
        result = main()
    except Exception:
        # Report entry-point failures; exceptions are not swallowed in the game loop.
        user_data().joinpath("crash.log").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    raise SystemExit(result)
