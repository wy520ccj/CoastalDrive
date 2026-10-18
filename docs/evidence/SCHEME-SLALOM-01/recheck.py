"""从保存的实际位置/速度/朝向复核每步判门和玩家成绩；不重跑物理。"""
import argparse
import gzip
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--evidence", action="store_true", help="从项目根读取已提交证据；只读复核")
args = parser.parse_args()
root = Path.cwd()
sys.path.insert(0, str(root/"src"))
from driving_modes import DrivingMode
from road_comparison import TrialScores
from slalom_lesson import SlalomLesson
from vehicle_config import VehicleConfig

results = []
for sdk in ("normal", "double"):
    base = (root/"docs/evidence/SCHEME-SLALOM-01"/sdk if args.evidence
            else root/"logs/SCHEME-SLALOM-01"/(sdk+"-ui"))
    document = json.loads((base/"summary.json").read_text(encoding="utf-8"))
    rows = json.loads(gzip.decompress((base/"actual-player-drive.json.gz").read_bytes()))
    config = VehicleConfig(**document["player_config"])
    lesson = SlalomLesson(document["player_result"]["start_progress"], TrialScores(), config)
    elapsed = 0.
    for index, row in enumerate(rows):
        if index:
            assert row["tick"] == rows[index-1]["tick"]+1
            assert abs(row["time"]-rows[index-1]["time"]-1/120) < 1e-9
        assert row["position"][1]-row["result"]["start_progress"] == row["result"]["position"]
        elapsed += 1/120
        result = lesson.update(row["position"][1], row["velocity"][1], elapsed,
            lateral=row["position"][0], heading=row["heading"], collisions=row["collisions"])
        assert json.loads(json.dumps(asdict(result))) == row["result"], (sdk, index)
    assert rows[-1]["result"] == document["player_result"]
    canonical = json.dumps(document["player_config"], sort_keys=True, separators=(",", ":"), allow_nan=False)
    variant = DrivingMode.GAME.score_variant(config.braking["abs_enabled"],
        config.traction["tcs_enabled"], config.stability["esc_enabled"])
    key = "slalom-v1:"+variant+":splits-v1:hardware-"+hashlib.sha256(canonical.encode()).hexdigest()
    scores = json.loads((base/"slalom-best.json").read_text(encoding="utf-8"))
    assert scores["scores"][key] == result.run_seconds and result.succeeded
    results.append({"sdk": sdk, "steps": len(rows), "all_step_rules_match": True,
        "player_best_matches": True, "run_seconds": result.run_seconds, "medal": result.medal,
        "physics_rerun": False})
if not args.evidence:
    (root/"logs/SCHEME-SLALOM-01/raw-rule-recheck.json").write_text(json.dumps(results, ensure_ascii=False,
        indent=2), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False))
