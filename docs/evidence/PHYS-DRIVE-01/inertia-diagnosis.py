"""新惯量设计值同输入扫描；保留原起步/转弯/坡道指标，不自动改生产参数。"""

import gzip
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from simulation import Control, Simulation
from test_track import SPAWN, TEST_SPAWN
from vehicle_config import CAR

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=False)
hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for folder in ("src", "tests", "tools") for p in sorted((ROOT / folder).rglob("*.py"))}
before = hashes()
report = {"source_before": before, "results": [], "status": "running"}


def save():
    (output / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")


save()
for inertia in (tuple(float(v) for v in sys.argv[2:]) or (.2, .1, .05)):
    config = replace(CAR, engine_inertia=inertia)
    for case, seconds, control, spawn in (
            ("launch", 3., Control(throttle=1.), TEST_SPAWN),
            ("turn", 3., Control(throttle=.5, steering=1.), TEST_SPAWN),
            ("ramp", 9., Control(throttle=.4), (70, 25, SPAWN[2]))):
        sim = Simulation(17, track="test", config=config)
        sim.reset_player(spawn)
        try:
            for _ in range(240):
                sim.step(Control())
            records = []
            with gzip.open(output / f"{inertia:g}-{case}.jsonl.gz", "wt", encoding="utf-8") as stream:
                for tick in range(1, round(seconds * 120) + 1):
                    sim.step(control)
                    car = sim.snapshot().player
                    records.append(car)
                    stream.write(json.dumps({"tick": tick, "state": asdict(car)}, allow_nan=False) + "\n")
            result = {"engine_inertia": inertia, "case": case, "config": asdict(config),
                "input": asdict(control), "speed": car.speed, "position": car.position,
                "heading": car.heading, "max_height": max(c.position[2] for c in records),
                "max_pitch": max(c.pitch for c in records), "max_abs_roll": max(abs(c.roll) for c in records),
                "maximum_force_residual": max(w.force_residual for c in records for w in c.wheel_dynamics)}
            report["results"].append(result)
            save()
            print(json.dumps({k: result[k] for k in ("engine_inertia", "case", "speed", "position", "heading")}), flush=True)
        except (ArithmeticError, AssertionError, OSError, ValueError) as error:
            report.update(status="failed", error=repr(error), failed_case=case, failed_inertia=inertia)
            save()
            raise
        finally:
            sim.close()
after = hashes()
report.update(status="completed", source_after=after, source_stable=before == after)
save()
assert before == after
