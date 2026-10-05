"""保留固定护栏摆位的原生轨迹，区分求解收敛与旧事故断言。"""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

from panda3d.core import Vec3

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "src")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--coupled-off", action="store_true")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--vehicle-config", type=Path, help="两输入模式使用同一完整工程硬件")
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    import simulation
    from driving_modes import DrivingMode

    if args.vehicle_config is not None:
        # 工程文件入口来自当前工具；旧外部源码默认工况无需此新模块。
        sys.path.append(str(ROOT/"src"))
        from vehicle_parameters import load_vehicle_config

    assert Path(simulation.__file__).resolve() == source / "simulation.py"
    args.output.mkdir(parents=True, exist_ok=False)
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source.glob("*.py"))}
    results = []
    for mode in DrivingMode:
        for centered in (False, True):
            name = f"{mode.value}-{'partitioned' if centered else 'box'}"
            hardware = mode.vehicle_config if args.vehicle_config is None else load_vehicle_config(args.vehicle_config, mode.vehicle_config)
            config = replace(hardware, centered_collision_support=centered,
                             suspension_coupled_enabled=not args.coupled_off)
            world = simulation.Simulation(track="highway", traffic_count=0, config=config,
                                          input_config=mode.input_config)
            peak_load = peak_residual = 0.
            events = []
            completed, error = 0, None
            try:
                world.reset_player((5.8, 30, .55))
                world.player._chassis.setLinearVelocity(Vec3(8, 12, 0))
                world.player.tires.initialize_rolling(12)
                with (args.output / f"{name}.jsonl").open("w", encoding="utf-8") as stream:
                    for _tick in range(args.steps):
                        world.step(simulation.Control())
                        snapshot = world.snapshot()
                        stream.write(json.dumps(asdict(snapshot), ensure_ascii=False) + "\n")
                        completed += 1
                        events.extend(asdict(event) for event in snapshot.impacts)
                        for contact in snapshot.player.wheel_contacts:
                            peak_load = max(peak_load, contact.normal_load)
                        support = snapshot.player.suspension_state
                        if support is not None:
                            peak_residual = max(peak_residual, *(abs(step.energy_residual) for _dt, step in support.substeps))
                final = world.snapshot().player
            except ArithmeticError as failure:
                error = str(failure)
                final = world.snapshot().player
            finally:
                world.close()
            results.append({"case": name, "completed": completed, "requested": args.steps,
                            "error": error, "peak_load_n": peak_load, "peak_local_energy_residual_j": peak_residual,
                            "final_position": final.position, "final_roll_deg": final.roll, "impacts": events})
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(source.glob("*.py"))}
    passed = all(row["error"] is None and row["completed"] == args.steps for row in results) and hashes == after
    report = {"source": str(source), "coupled_off": args.coupled_off, "passed": passed,
              "vehicle_config_file": None if args.vehicle_config is None else str(args.vehicle_config),
              "source_stable": hashes == after, "source_sha256": hashes, "results": results}
    (args.output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": passed, "cases": results}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
