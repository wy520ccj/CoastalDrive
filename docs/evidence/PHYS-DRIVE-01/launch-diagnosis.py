"""同输入起步诊断；完整保存实际发动机、离合和轮胎，不改变验收阈值。"""

import gzip
import hashlib
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from simulation import Control, Simulation
from test_track import TEST_SPAWN
from vehicle_config import CAR

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=False)
hashes = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for folder in ("src", "tests", "tools") for p in sorted((ROOT / folder).rglob("*.py"))}
before = hashes()
results = []
for name, config, ticks in (("legacy", replace(CAR, finite_drivetrain=False), 1200),
        ("current", CAR, 1200),
        ("response-010", replace(CAR, clutch_launch_response=.10), 120),
        ("response-030", replace(CAR, clutch_launch_response=.30), 120)):
    sim = Simulation(track="test", config=config)
    sim.reset_player(TEST_SPAWN)
    checkpoints = {}
    changes = []
    last_gear = 1
    try:
        for _ in range(240):
            sim.step(Control())
        with gzip.open(output / f"{name}.jsonl.gz", "wt", encoding="utf-8") as stream:
            for tick in range(1, ticks + 1):
                sim.step(Control(throttle=1.))
                car = sim.snapshot().player
                stream.write(json.dumps({"tick": tick, "car": asdict(car)}, allow_nan=False) + "\n")
                if tick in (18, 30, 60, 120, 360, 600, 1200):
                    checkpoints[tick] = {"kmh": car.speed * 3.6, "rpm": car.rpm,
                        "pedal": car.throttle, "powertrain": asdict(car.powertrain_state) if car.powertrain_state else None}
                if car.gear != last_gear:
                    changes.append([tick, last_gear, car.gear])
                    last_gear = car.gear
        result = {"name": name, "config": asdict(config), "checkpoints": checkpoints, "changes": changes}
        results.append(result)
        print(json.dumps({"name": name, "speeds": {t: r["kmh"] for t, r in checkpoints.items()}, "changes": changes}), flush=True)
    finally:
        sim.close()
after = hashes()
assert before == after
(output / "summary.json").write_text(json.dumps({"source_before": before, "source_after": after,
    "source_stable": before == after, "results": results}, indent=2), encoding="utf-8")
