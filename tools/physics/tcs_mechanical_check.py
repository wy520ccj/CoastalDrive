"""导出冻结源码并逐tick核对关闭TCS时既有机械状态，新增诊断另列。"""

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = (("test", "straight", 0), ("coastal", "straight", 2), ("endless", "hills", 2))


def capture(source, destination, current):
    sys.path.insert(0, str(source))
    from dataclasses import replace

    from simulation import Control, Simulation
    from vehicle_config import CAR

    config = replace(CAR, traction=replace(CAR.traction, tcs_enabled=False)) if current else CAR
    for track, shape, count in CASES:
        sim = Simulation(23, track=track, road_shape=shape, traffic_count=count, config=config)
        try:
            with gzip.open(destination / f"{track}.jsonl.gz", "wt", encoding="utf-8") as stream:
                for tick in range(1200):
                    control = Control(throttle=1 if tick < 720 else 0,
                                      brake=.7 if tick >= 960 else 0,
                                      steering=.12 if 480 <= tick < 720 else 0)
                    sim.step(control)
                    stream.write(json.dumps(asdict(sim.snapshot()), separators=(",", ":"), allow_nan=False) + "\n")
        finally:
            sim.close()


def run(output, baseline):
    output.mkdir(parents=True, exist_ok=False)
    before = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (ROOT / "src").rglob("*.py")}
    archive = output / "baseline-src.zip"
    subprocess.run(["git", "archive", "--format=zip", "--output", str(archive), baseline, "src"],
                   cwd=ROOT, check=True)
    with zipfile.ZipFile(archive) as package:
        package.extractall(output / "baseline-source")
    for label, source in (("A", output / "baseline-source/src"), ("B", ROOT / "src")):
        folder = output / label
        folder.mkdir()
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--capture", str(source),
                        "--output", str(folder), *( ["--current"] if label == "B" else [])],
                       cwd=ROOT, check=True)
    sys.path.insert(0, str(ROOT / "tools"))
    from driving_mode_check import compare_record
    results = []
    for track, _shape, _count in CASES:
        count = mismatches = 0
        maximum = 0.0
        added = set()
        with gzip.open(output / f"A/{track}.jsonl.gz", "rt") as old, gzip.open(
            output / f"B/{track}.jsonl.gz", "rt"
        ) as new:
            for a, b in zip(old, new, strict=True):
                result = compare_record(json.loads(a), json.loads(b))
                count += result["compared_values"]
                mismatches += result["mismatch_count"]
                maximum = max(maximum, result["max_geometry_abs_delta"], result["max_other_numeric_abs_delta"])
                added.update(result["extra_current_paths"])
        results.append({"track": track, "ticks": 1200, "compared_values": count,
                        "mismatch_count": mismatches, "maximum_numeric_delta": maximum,
                        "added_diagnostics": sorted(added)})
    after = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in (ROOT / "src").rglob("*.py")}
    report = {"baseline_ref": baseline,
              "baseline_commit": subprocess.check_output(["git", "rev-parse", baseline], cwd=ROOT, text=True).strip(),
              "baseline_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "cases": results, "source_before": before, "source_after": after,
              "passed": before == after and all(r["mismatch_count"] == 0 and
                                               r["maximum_numeric_delta"] == 0 for r in results)}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "cases": results}, ensure_ascii=False))
    return report["passed"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", default="bd0f9e4")
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--current", action="store_true")
    args = parser.parse_args()
    if args.capture:
        capture(args.capture, args.output, args.current)
        return 0
    return 0 if run(args.output.resolve(), args.baseline) else 1


if __name__ == "__main__":
    raise SystemExit(main())
