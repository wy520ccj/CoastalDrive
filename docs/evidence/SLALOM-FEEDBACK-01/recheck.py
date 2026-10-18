"""只读复核原始驾驶每步规则、完整最佳与重试参考；不重跑物理。"""

import argparse
import gzip
import hashlib
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--evidence", action="store_true")
args = parser.parse_args()
root = Path.cwd()
sys.path.insert(0, str(root/"src"))
from driving_modes import DrivingMode
from slalom_lesson import SlalomLesson, SlalomScores
from vehicle_config import VehicleConfig

checks = []
for sdk in ("normal", "double"):
    base = (root/"docs/evidence/SLALOM-FEEDBACK-01"/sdk if args.evidence else
            root/"logs/validation"/f"SLALOM-FEEDBACK-01-{sdk}-drive")
    summary = json.loads((base/"summary.json").read_text(encoding="utf-8"))
    config = VehicleConfig(**summary["vehicle_config"])
    canonical = json.dumps(summary["vehicle_config"], sort_keys=True, separators=(",", ":"), allow_nan=False)
    variant = DrivingMode.GAME.score_variant(config.braking["abs_enabled"], config.traction["tcs_enabled"],
                                            config.stability["esc_enabled"])
    key = "slalom-v1:"+variant+":splits-v1:hardware-"+hashlib.sha256(canonical.encode()).hexdigest()
    assert key == summary["score_key"]
    assert summary["source_start"] == summary["source_end"]
    assert summary["runtime_start"] == summary["runtime_end"]
    counts = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/"scores.json"
        for attempt in (1, 2):
            rows = json.loads(gzip.decompress((base/f"run-{attempt}.json.gz").read_bytes()))
            lesson = SlalomLesson(rows[0]["lesson"]["start_progress"], SlalomScores(path, key), config)
            elapsed = 0.
            for index, row in enumerate(rows):
                if index:
                    assert row["tick"] == rows[index-1]["tick"]+1
                    assert abs(row["time"]-rows[index-1]["time"]-1/120) < 1e-9
                elapsed += 1/120
                actual = lesson.update(row["position"][1], row["velocity"][1], elapsed,
                    lateral=row["position"][0], heading=row["heading"], collisions=row["collisions"])
                assert json.loads(json.dumps(asdict(actual))) == row["lesson"], (sdk, attempt, index)
            assert rows[-1]["lesson"] == summary["results"][attempt-1]
            counts.append(len(rows))
        stored = json.loads(path.read_text(encoding="utf-8"))
        first = json.loads((base/"best-after-first.json").read_text(encoding="utf-8"))
        assert stored == first
    assert (base/"best-after-first.json").read_bytes() == (base/"best-after-retry.json").read_bytes()
    assert summary["results"][1]["reference_times"] == summary["results"][0]["gate_times"]
    checks.append({"sdk": sdk, "ticks": counts, "all_step_rules_match": True,
                   "whole_best_and_frozen_reference_match": True, "physics_rerun": False})
print(json.dumps(checks, ensure_ascii=False))
