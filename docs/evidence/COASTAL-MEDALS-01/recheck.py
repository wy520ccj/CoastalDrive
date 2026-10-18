"""只读复核真实三圈、已保存分段/幽灵/重启；不重跑物理或声明新版本兼容。"""

import argparse
import gzip
import hashlib
import json
import struct
import sys
import tempfile
import zlib
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--evidence", action="store_true")
parser.add_argument("--sdk", choices=("normal", "double"), nargs="+", default=("normal", "double"))
args = parser.parse_args()
root = Path.cwd()
sys.path.insert(0, str(root/"src"))
from coastal_medals import result_medal
from driving_modes import DrivingMode
from lap_ghost import load_ghost
from race import BestTimes, GameMode, RaceTracker
from vehicle_config import VehicleConfig

checks = []
for sdk in args.sdk:
    base = (root/"docs/evidence/COASTAL-MEDALS-01"/sdk if args.evidence else
            root/"logs/validation"/f"COASTAL-MEDALS-01-{sdk}-fixed-drive")
    summary = json.loads((base/"summary.json").read_text(encoding="utf-8"))
    config = VehicleConfig(**summary["vehicle_config"])
    canonical = json.dumps(summary["vehicle_config"], sort_keys=True, separators=(",", ":"), allow_nan=False)
    variant = DrivingMode.GAME.score_variant(config.braking["abs_enabled"], config.traction["tcs_enabled"], config.stability["esc_enabled"])
    variant += ":splits-v1:hardware-"+hashlib.sha256(canonical.encode()).hexdigest()
    assert variant == summary["score_variant"]
    assert summary["source_start"] == summary["source_end"] and summary["runtime_start"] == summary["runtime_end"]
    counts, medals = [], []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/"best.json"
        for attempt in (1, 2, 3):
            rows = json.loads(gzip.decompress((base/f"run-{attempt}.json.gz").read_bytes()))
            race = RaceTracker(GameMode.TIME_TRIAL, BestTimes(path))
            race.start(score_variant=variant)
            race.begin(start_time=rows[0]["race"]["start_time"])
            for index, row in enumerate(rows):
                if index:
                    assert row["tick"] == rows[index-1]["tick"]+1
                    assert abs(row["time"]-rows[index-1]["time"]-1/120) < 1e-9
                race.update(SimpleNamespace(player=SimpleNamespace(position=row["position"], speed=row["speed"])), 1/120)
                actual = {**asdict(race.snapshot), "mode": race.snapshot.mode.value}
                notice = "最佳圈幽灵已保存，下次挑战可对照。" if race.snapshot.finished and race.snapshot.new_best else ""
                assert row["race"]["ghost_notice"] == notice
                actual["ghost_notice"] = notice
                assert json.loads(json.dumps(actual)) == row["race"], (sdk, attempt, index)
            assert rows[-1]["race"] == summary["results"][attempt-1]
            saved = base/f"best-after-{attempt}.json"
            source = BestTimes(saved)
            expected = json.loads(saved.read_text(encoding="utf-8"))
            recalculated = json.loads(path.read_text(encoding="utf-8"))
            assert {k: v for k, v in expected.items() if k != "_ghosts_v1"} == {k: v for k, v in recalculated.items() if k != "_ghosts_v1"}
            digest = source.ghost_digest(GameMode.TIME_TRIAL, race.score_id)
            blob = (base/"ghosts"/(digest+".cdg")).read_bytes()
            assert hashlib.sha256(blob).hexdigest() == digest
            raw = zlib.decompress(blob[4:])
            size, = struct.unpack_from("<I", raw)
            header = json.loads(raw[4:4+size])
            # 用归档当时的上下文检验历史文件内部一致性；不冒充当前源码的可播放验收。
            ghost = load_ghost(source, GameMode.TIME_TRIAL, race.score_id, header["context"],
                               race.snapshot.last_lap, race.snapshot.splits)
            assert ghost.frames == len(rows)+1 and ghost.pose_at(ghost.seconds) is not None
            assert header["context"]["bits"] == (32 if sdk == "normal" else 64)
            path.write_bytes(saved.read_bytes())
            counts.append(len(rows))
            medals.append(result_medal(race.snapshot, "coastal"))
    assert medals == ["铜", "银", "金"]
    restored = json.loads((base/"restore-summary.json").read_text(encoding="utf-8"))
    assert restored["passed"] and restored["best"] == summary["results"][-1]["last_lap"]
    assert restored["scores_unchanged"] and restored["ghost_frames"] == counts[-1]+1
    checks.append({"sdk": sdk, "ticks": counts, "medals": medals, "all_step_rules_match": True,
        "saved_best_splits_ghosts_restart_match": True, "physics_rerun": False})
print(json.dumps(checks, ensure_ascii=False))
