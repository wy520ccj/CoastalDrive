"""运行短 Bullet 碰撞探针，或打开带 JSONL 诊断的人工驾驶。"""

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from panda3d.core import Vec3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from impact_events import ImpactDetectionConfig
from simulation import Control, Simulation


def git_value(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout.strip()


def write_row(stream, row):
    stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_rail(stream, seed):
    simulation = Simulation(seed, track="highway", traffic_count=0)
    simulation.set_impact_diagnostic(stream, scenario="rail-oblique")
    try:
        simulation.reset_player((5.8, 30, 0.55))
        simulation.player._chassis.setLinearVelocity(Vec3(8, 12, 0))
        for _ in range(90):
            simulation.step(Control())
    finally:
        simulation.close()


def run_wall(stream, speed, seed):
    simulation = Simulation(seed, track="test", traffic_count=0)
    simulation.set_impact_diagnostic(stream, scenario=f"wall-{speed:g}mps")
    try:
        simulation.reset_player((95, 716.8, 0.55))
        simulation.player._chassis.setLinearVelocity(Vec3(0, speed, 0))
        for _ in range(100):
            simulation.step(Control())
    finally:
        simulation.close()


def run_npc(stream, seed):
    simulation = Simulation(seed, track="test", traffic_count=1)
    simulation.set_impact_diagnostic(stream, scenario="moving-npc")
    try:
        simulation.reset_player((0, -8, 0.55), heading=0)
        simulation.player._chassis.setLinearVelocity(Vec3(0, 8, 0))
        simulation.npcs[0].reset((0, 0, 0.55), heading=180)
        simulation.npcs[0]._chassis.setLinearVelocity(Vec3(0, -2, 0))
        simulation._tick = 1
        for _ in range(110):
            simulation.step(Control())
    finally:
        simulation.close()


def run_scrape(stream, seed):
    simulation = Simulation(seed, track="highway", traffic_count=0)
    simulation.set_impact_diagnostic(stream, scenario="sustained-rail-scrape")
    try:
        simulation.reset_player((7.2, 30, 0.55))
        simulation.player._chassis.setLinearVelocity(Vec3(0, 8, 0))
        for _ in range(840):
            simulation.step(Control(throttle=0.15, steering=0.2))
    finally:
        simulation.close()


def run_drive(stream, seed, track, road_shape):
    from application import CoastalDrive

    app = CoastalDrive(seed=seed, track=track, road_shape=road_shape)
    app.session.simulation.set_impact_diagnostic(stream, scenario="manual-drive")
    if app.soundscape is not None:
        app.soundscape.set_impact_diagnostic(stream)
    original_start = app.session.start

    def start_with_diagnostic(*args, **kwargs):
        result = original_start(*args, **kwargs)
        app.session.simulation.set_impact_diagnostic(stream, scenario="manual-drive")
        return result

    app.session.start = start_with_diagnostic
    try:
        app.run()
    finally:
        app.close_game()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true", help="run silent, deterministic Bullet fixtures")
    mode.add_argument("--drive", action="store_true", help="open the game for manual collision collection")
    parser.add_argument("--output", type=Path, required=True, help="new evidence directory")
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--track", choices=("coastal", "highway", "test", "endless"), default="highway")
    parser.add_argument("--road-shape", choices=("straight", "curves", "hills"), default="straight")
    args = parser.parse_args(argv)
    output = (ROOT / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    if output.exists():
        parser.error(f"refusing to overwrite existing output directory: {output}")
    output.mkdir(parents=True)
    logfile = output / "impacts.jsonl"
    started = datetime.now(UTC).isoformat()
    config = ImpactDetectionConfig()
    summary = {
        "started_utc": started,
        "git_head": git_value("rev-parse", "HEAD"),
        "git_status": git_value("status", "--short"),
        "panda3d": __import__("panda3d").__version__,
        "seed": args.seed,
        "mode": "probe" if args.probe else "manual-drive",
        "output": str(logfile),
        "detection_config": vars(config),
        "status": "running",
    }
    with logfile.open("w", encoding="utf-8", buffering=1) as stream:
        write_row(stream, {"type": "header", **summary})
        try:
            if args.probe:
                run_rail(stream, args.seed)
                for speed in (2, 8, 20):
                    run_wall(stream, speed, args.seed)
                run_npc(stream, args.seed)
                run_scrape(stream, args.seed)
            else:
                run_drive(stream, args.seed, args.track, args.road_shape)
            summary["status"] = "complete"
        except BaseException as error:
            summary["status"] = "failed"
            summary["error"] = f"{type(error).__name__}: {error}"
            write_row(stream, {"type": "summary", **summary})
            raise
        else:
            rows = [json.loads(line) for line in logfile.read_text(encoding="utf-8").splitlines()]
            pulses = [row for row in rows if row.get("type") == "pulse"]
            barrier_contacts = [row for row in rows
                                if row.get("type") == "contact"
                                and row.get("material") == "metal_barrier"]
            summary["pulse_count"] = len(pulses)
            summary["pulse_scenarios"] = sorted({row.get("scenario") for row in pulses})
            summary["barrier_contact_samples"] = len(barrier_contacts)
            summary["barrier_contact_scenarios"] = sorted(
                {row.get("scenario") for row in barrier_contacts}
            )
            summary["raw_impulse_range_ns"] = (
                [min(row["raw_impulse_ns"] for row in pulses),
                 max(row["raw_impulse_ns"] for row in pulses)] if pulses else None
            )
            write_row(stream, {"type": "summary", **summary})
            (output / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    print(json.dumps({"status": summary["status"], "jsonl": str(logfile)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
