"""从保存的真实完成步复核两课题和0→3→6成长；不重跑物理。"""

import argparse
import gzip
import hashlib
import json
import math
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--evidence", action="store_true")
args = parser.parse_args()
root = Path.cwd()
sys.path.insert(0, str(root/"src"))
from braking_lesson import BrakingLesson, BrakingScores
from driving_journey import read_driving_journey
from driving_modes import DrivingMode
from slalom_lesson import SlalomLesson, SlalomScores
from vehicle_config import VehicleConfig

checks = []
for sdk in ("normal", "double"):
    base = (root/"docs/evidence/DRIVING-JOURNEY-01"/sdk if args.evidence else
            root/"logs/validation"/f"DRIVING-JOURNEY-01-{sdk}-drive")
    document = json.loads((base/"summary.json").read_text(encoding="utf-8"))
    config = VehicleConfig(**document["vehicle_config"])
    canonical = json.dumps(document["vehicle_config"], sort_keys=True, separators=(",", ":"), allow_nan=False)
    variant = DrivingMode.GAME.score_variant(config.braking["abs_enabled"], config.traction["tcs_enabled"], config.stability["esc_enabled"])
    variant += ":splits-v1:hardware-"+hashlib.sha256(canonical.encode()).hexdigest()
    assert variant == document["score_variant"]
    assert document["source_start"] == document["source_end"]
    assert document["runtime_start"] == document["runtime_end"]
    counts, stages = [], []
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory)
        def data():
            return read_driving_journey(BrakingScores(temporary/"braking-best.json", "braking-v1:"+variant),
                                        SlalomScores(temporary/"slalom-best.json", "slalom-v1:"+variant))
        stages.append(data())
        for topic in ("braking", "slalom"):
            rows = json.loads(gzip.decompress((base/(topic+"-drive.json.gz")).read_bytes()))
            start = rows[0]["result"]["start_progress"]
            lesson = (BrakingLesson(start, BrakingScores(temporary/"braking-best.json", "braking-v1:"+variant)) if topic == "braking" else
                      SlalomLesson(start, SlalomScores(temporary/"slalom-best.json", "slalom-v1:"+variant), config))
            elapsed = 0.
            for index, row in enumerate(rows):
                if index:
                    assert row["tick"] == rows[index-1]["tick"]+1
                    assert abs(row["time"]-rows[index-1]["time"]-1/120) < 1e-9
                elapsed += 1/120
                common = {"lateral": row["position"][0], "collisions": row["collisions"]}
                result = (lesson.update(row["position"][1], row["velocity"][1], math.hypot(*row["velocity"][:2]), elapsed, 1/120, **common)
                          if topic == "braking" else lesson.update(row["position"][1], row["velocity"][1], elapsed,
                                                                  heading=row["heading"], **common))
                assert json.loads(json.dumps(asdict(result))) == row["result"], (sdk, topic, index)
            assert result.succeeded and result.medal == "金"
            counts.append(len(rows))
            stages.append(data())
            assert json.loads((temporary/(topic+"-best.json")).read_text(encoding="utf-8")) == json.loads((base/(topic+"-best.json")).read_text(encoding="utf-8"))
        assert json.loads(json.dumps(stages)) == document["stages"]
    restored = json.loads((base/"restore-summary.json").read_text(encoding="utf-8"))
    assert restored["passed"] and restored["data"] == document["stages"][-1] and restored["score_files_unchanged"]
    checks.append({"sdk": sdk, "ticks": counts, "all_step_rules_match": True, "stages": [item["steps"] for item in stages],
                   "saved_scores_and_restart_match": True, "physics_rerun": False})
print(json.dumps(checks, ensure_ascii=False))
