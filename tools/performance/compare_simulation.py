"""同输入比较物理快照与CPU耗时；不把微测量当作窗口帧率。"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", action="store_true")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.baseline:
        for name in ("vehicle", "simulation"):
            source = subprocess.check_output(
                ["git", "show", f"f9431dd:src/{name}.py"], cwd=ROOT, text=True,
                encoding="utf-8",
            )
            module = ModuleType(name)
            sys.modules[name] = module
            exec(compile(source, name, "exec"), module.__dict__)  # noqa: S102
    from simulation import Control, Simulation

    rows = []
    for shape in ("straight", "curves", "hills"):
        sim = Simulation(seed=23, track="endless", road_shape=shape, traffic_count=12)
        hashes, snapshots = [], []
        started = time.perf_counter()
        try:
            for tick in range(2400):
                throttle = .6 if tick < 1800 else .3
                sim.step(Control(throttle=throttle))
                if tick % 60 == 0 or tick == 2399:
                    state = sim.snapshot()
                    hashes.append(hashlib.sha256(repr(state).encode()).hexdigest())
                    snapshots.append(asdict(state))
            rows.append({"shape": shape, "seconds": time.perf_counter() - started,
                         "ticks": 2400, "hashes": hashes, "snapshots": snapshots})
        finally:
            sim.close()
    args.output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps([{k: v for k, v in row.items() if k not in ("hashes", "snapshots")}
                      for row in rows]))


if __name__ == "__main__":
    main()
