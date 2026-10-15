"""同条件串行A/B/B/A整步测量；逐拍SHA核对，不把局部耗时当作前台通过。"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def compare(baseline, candidate, output):
    output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
           "LOCALAPPDATA": str(output/"user-data")}
    modes = []
    for mode, workers in (("game", 0), ("simulation", 9)):
        rows, reference = [], None
        for label, source in (("a1", baseline), ("b1", candidate), ("b2", candidate), ("a2", baseline)):
            folder = output/f"{mode}-{label}"
            args = [sys.executable, str(ROOT/"tools/performance/benchmark_physics.py"),
                    "--source", str(source), "--output", str(folder), "--workers", str(workers),
                    "--traffic", "12", "--mode", mode, "--traffic-input-mode", "game",
                    "--track", "endless", "--shape", "hills", "--driver", "endurance",
                    "--seed", "23", "--warmup", "120", "--steps", "480", "--capture-hashes"]
            print("RUN", mode, label, flush=True)
            with (output/f"{mode}-{label}.txt").open("w", encoding="utf-8") as stream:
                subprocess.run(args, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                               timeout=300, check=True)
            report = json.loads((folder/"report.json").read_text(encoding="utf-8"))
            hashes = json.loads((folder/"snapshot-hashes.json").read_text(encoding="utf-8"))
            assert report["measurement_complete"] and report["passed"] and report["source_unchanged"]
            assert len(hashes) == 480
            if reference is None:
                reference = hashes
            assert hashes == reference, f"{mode}/{label}完整快照不一致"
            rows.append({"label": label, "source": str(source), "command": args,
                         "complete_step": report["complete_step"],
                         "main_cpu_seconds": report["main_cpu_seconds"],
                         "total_cpu_seconds": report["total_cpu_seconds"],
                         "worker_solve": report["worker_solve_all_samples"],
                         "physical_substeps": report["physical_substeps"],
                         "source_hashes": report["source_hashes"],
                         "compute_budget_met": report["compute_budget_met"]})
            print(mode, label, f'{report["complete_step"]["mean_ms"]:.3f}ms', flush=True)
        before = (rows[0]["complete_step"]["mean_ms"]+rows[3]["complete_step"]["mean_ms"])/2
        after = (rows[1]["complete_step"]["mean_ms"]+rows[2]["complete_step"]["mean_ms"])/2
        modes.append({"mode": mode, "workers": workers, "traffic": 12, "steps_each": 480,
                      "all_four_snapshot_sequences_equal": True, "baseline_mean_ms": before,
                      "candidate_mean_ms": after, "mean_change_percent": (after/before-1)*100,
                      "runs": rows})
        (output/"comparison.json").write_text(json.dumps({"passed": len(modes) == 2, "modes": modes,
                    "scope": "complete fixed steps; not foreground or human acceptance"},
                    indent=2), encoding="utf-8")
    return modes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, default=ROOT/"src")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    compare(args.baseline.resolve(), args.candidate.resolve(), args.output.resolve())
