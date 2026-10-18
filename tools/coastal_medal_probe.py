"""测量原车滨海有效圈；所有路径/按键均经过原权威物理与判圈。"""

import argparse
import gzip
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from route_driver import RouteDriver
from slalom_driver import apply_keys

from driving_modes import DrivingMode
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from race import BestTimes, GameMode
from session import Phase, Session
from simulation import Control


def keyboard_request(control):
    return Control(steering=0. if abs(control.steering) < .06 else (1. if control.steering > 0 else -1.),
        throttle=float(control.throttle > .30), brake=float(control.brake > .25))


def probe(output, cases):
    output.mkdir(parents=True, exist_ok=False)
    source_start, runtime_start = model_fingerprint(), runtime_fingerprint()
    summaries = []
    for case in cases:
        name, target = case.split(":")
        speed = float(target)
        session = Session(scores=BestTimes(output/f"{name}-{target}-best.json"), driving_mode=DrivingMode.GAME)
        rows = []
        started = time.perf_counter()
        try:
            session.start(mode=GameMode.TIME_TRIAL, countdown=False, settle_initial=True)
            driver = RouteDriver(speed)
            session.set_controller(driver if name == "analog" else session.keyboard)
            config = session.vehicle_config
            for _ in range(120*150):
                control = driver.sample(session.current, 1/120)
                if name == "keyboard":
                    apply_keys(session.keyboard, keyboard_request(control))
                keys = sorted(session.keyboard.pressed)
                session.tick()
                state, race = session.current, session.race.snapshot
                rows.append({"tick": state.tick, "time": state.time, "position": state.player.position,
                    "speed": state.player.speed, "collisions": state.collisions, "keys": keys,
                    "request": asdict(session.last_control), "race": {**asdict(race), "mode": race.mode.value}})
                if session.phase == Phase.RESULTS:
                    break
            race = session.race.snapshot
            summary = {"case": case, "config": asdict(config), "input": asdict(session.keyboard.input_config),
                "score_id": session.race.score_id, "race": {**asdict(race), "mode": race.mode.value},
                "collisions": session.current.collisions, "ticks": len(rows), "compute_wall_seconds": time.perf_counter()-started,
                "controller": "连续Control" if name == "analog" else "实际KeyboardController二值请求；非人工驾驶"}
            summaries.append(summary)
            with gzip.open(output/f"{name}-{target}.json.gz", "wt", encoding="utf-8") as stream:
                json.dump(rows, stream, ensure_ascii=False)
            print(json.dumps({"case": case, "finished": race.finished, "invalidated": race.invalidated,
                "reason": race.invalid_reason, "seconds": race.last_lap, "collisions": session.current.collisions}), flush=True)
        finally:
            session.close()
    source_end, runtime_end = model_fingerprint(), runtime_fingerprint()
    assert source_start == source_end and runtime_start == runtime_end
    (output/"summary.json").write_text(json.dumps({"cases": summaries, "source_start": source_start,
        "source_end": source_end, "runtime_start": runtime_start, "runtime_end": runtime_end,
        "human_gate": "pending"}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=("analog:90", "keyboard:90", "keyboard:60"))
    args = parser.parse_args()
    probe(args.output.resolve(), args.cases)
