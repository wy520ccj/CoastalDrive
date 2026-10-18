"""只复核归档完成步/规则/指标，不重新运行物理或写玩家成绩。"""
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))
from road_comparison import RoadRecord, TrialScores, path_svg
from slalom_lesson import SlalomLesson
from snapshot_wire import decode_snapshots
from vehicle_config import VehicleConfig

results = []
for sdk in ("normal-ui", "double-ui"):
    folder = ROOT/"logs/VIRTUAL-DRIVER-01"/sdk
    report = Path(json.loads((folder/"summary.json").read_text(encoding="utf-8"))["report"]).parent
    records = []
    for side in ("A", "B"):
        data = json.loads((report/side/"trial.json").read_text(encoding="utf-8"))
        payload = (report/side/"snapshots.bin").read_bytes()
        assert hashlib.sha256(payload).hexdigest() == data["snapshot_sha256"]
        states, _ = decode_snapshots(payload)
        assert len(states) == len(data["controls"])+1 == len(data["rows"])+1
        assert data["source_start"] == data["source_end"] and data["runtime_start"] == data["runtime_end"]
        lesson = SlalomLesson(states[0].player.position[1], TrialScores(), VehicleConfig(**data["actual_config"]))
        for index, (state, row) in enumerate(zip(states[1:], data["rows"], strict=True), 1):
            car = state.player
            assert state.tick == states[0].tick+index and row["tick"] == index
            assert abs(state.time-states[0].time-index/120) < 1e-9
            assert row["time"] == index*(1/120)
            result = lesson.update(car.position[1]+state.origin_y, car.velocity[1], row["time"],
                lateral=car.position[0], heading=car.heading, collisions=state.collisions,
                reset="player_reset" in state.events)
            assert row["gates"] == result.gates and row["position"] == result.position
            assert row["x"] == car.position[0] and row["beta_deg"] == car.dynamics.sideslip
            assert row["roll_deg"] == car.roll and row["esc_active"] == car.stability_state.active
        assert json.loads(json.dumps(asdict(result))) == data["result"]
        metrics = data["metrics"]
        assert metrics["valid_seconds"] == (result.run_seconds if result.succeeded else None)
        assert metrics["minimum_clearance_m"] == min(result.clearances)
        assert metrics["peak_beta_deg"] == max(abs(row["beta_deg"]) for row in data["rows"])
        assert metrics["peak_roll_deg"] == max(abs(row["roll_deg"]) for row in data["rows"])
        assert metrics["esc_seconds"] == sum(row["esc_active"] for row in data["rows"])/120
        records.append(RoadRecord(data, states, tuple(data["controls"]), tuple(data["rows"])))
        results.append({"sdk": sdk, "side": side, "steps": len(states)-1, "metrics": metrics, "passed": True})
    ET.fromstring(path_svg(records))
    assert records[0].metadata["policy"] == records[1].metadata["policy"]
    assert records[0].metadata["environment"] == records[1].metadata["environment"]
(ROOT/"logs/VIRTUAL-DRIVER-01/raw-recheck.json").write_text(json.dumps(
    {"passed": True, "physics_rerun": False, "records": results}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"passed": True, "records": len(results), "steps": sum(item["steps"] for item in results)}))
