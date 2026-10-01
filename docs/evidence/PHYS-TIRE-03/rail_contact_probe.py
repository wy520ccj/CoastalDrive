"""真实护栏接触/音频候选逐tick诊断；保持原音频阈值与测试门槛。"""

import argparse
import gzip
import hashlib
import json
import sys
from dataclasses import asdict, replace
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))

from panda3d.core import Vec3
from physics.reference_ab import _source_hashes
from test_soundscape import FakeBase, phase

from simulation import Simulation
from soundscape import Soundscape
from vehicle_config import CAR
from vehicle_state import FIXED_DT, VehicleCommand

TRIALS = ((False, 2), (True, 2), (True, 4), (True, 6))
TICKS = 840


def source_hashes():
    hashes = _source_hashes()
    for path in (Path(__file__), ROOT / "tests/test_soundscape.py", ROOT / "tests/test_impact_integration.py"):
        hashes[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def raw_contacts(simulation):
    records = []
    for manifold in simulation._world.getManifolds():
        node0, node1 = manifold.getNode0(), manifold.getNode1()
        if node0 != simulation._chassis and node1 != simulation._chassis:
            continue
        other = node1 if node0 == simulation._chassis else node0
        material, side = simulation._contact_material(other.getName())
        records.append({"other": other.getName(), "material": material, "side": side,
                        "source": simulation._source_id(other), "points": [{
                            "distance_m": float(point.getDistance()),
                            "impulse_ns": float(point.getAppliedImpulse()),
                            "lifetime": int(point.getLifeTime()),
                            "position_a": tuple(point.getPositionWorldOnA()),
                            "position_b": tuple(point.getPositionWorldOnB()),
                            "normal_b": tuple(point.getNormalWorldOnB())} for point in manifold.getManifoldPoints()]})
    return records


def gaps(flags):
    empty = []
    start = None
    for index, present in enumerate(flags+[True], 1):
        if not present and start is None:
            start = index
        elif present and start is not None:
            empty.append({"first_tick": start, "last_tick": index-1, "ticks": index-start})
            start = None
    occupied = [index+1 for index, present in enumerate(flags) if present]
    between = [entry for entry in empty if occupied and entry["first_tick"] > occupied[0] and entry["last_tick"] < occupied[-1]]
    return {"first_present_tick": occupied[0] if occupied else None,
            "last_present_tick": occupied[-1] if occupied else None,
            "longest_all_ticks": max((entry["ticks"] for entry in empty), default=0),
            "longest_between_first_last_ticks": max((entry["ticks"] for entry in between), default=0),
            "all_gaps": empty}


def run_trial(compliance, steering, output):
    config = replace(CAR, tire_compliance=compliance)
    simulation = Simulation(track="highway", traffic_count=0, config=config)
    sound = Soundscape(FakeBase())
    log = StringIO()
    sound.set_impact_diagnostic(log)
    command = VehicleCommand(throttle=.5, steering=steering, direction=1)
    name = f"{'flexible' if compliance else 'rigid'}-steering-{steering}"
    flags = {"rail_physical": [], "rail_penetrating": [], "contact_state": [], "candidate": [], "rail_candidate": []}
    events = []
    consumed = 0
    try:
        simulation.reset_player((6.9, 30, .55))
        simulation._chassis.setLinearVelocity(Vec3(.5, 8, 0))
        simulation.player.tires.initialize_rolling(8)
        initial = asdict(simulation.snapshot())
        with gzip.open(output / f"{name}.jsonl.gz", "wt", encoding="utf-8") as stream:
            for tick in range(1, TICKS+1):
                simulation.step(command)
                state = simulation.snapshot()
                sound.update(state, phase("driving"), None, FIXED_DT)
                raw = raw_contacts(simulation)
                contacts = [{**asdict(contact), "audio_candidate": contact.tangential_speed >= 1.6 and contact.raw_impulse >= 25}
                            for contact in simulation._contact_states]
                lines = log.getvalue().splitlines()
                fresh = [{**json.loads(line), "observed_tick": tick} for line in lines[consumed:]]
                consumed = len(lines)
                events.extend(fresh)
                rail_points = [point for manifold in raw if manifold["material"] == "metal_barrier" for point in manifold["points"]]
                audio = sound.impact_audio
                row = {"tick": tick, "time_s": tick*FIXED_DT, "command": asdict(command),
                       "snapshot": asdict(state), "contact_states": contacts, "raw_manifolds": raw,
                       "raw_player_manifold_count": len(raw), "raw_rail_manifold_point_count": len(rail_points),
                       "rail_physical_point_count": sum(point["distance_m"] <= 0 or point["impulse_ns"] > 0 for point in rail_points),
                       "rail_nonpositive_distance_point_count": sum(point["distance_m"] <= 0 for point in rail_points),
                       "audio": {"state": audio.scrape_state, "misses": audio.scrape_misses,
                                 "source": audio.scrape_source, "age": audio.scrape_age,
                                 "level": audio.scrape_level, "target": audio.scrape_target,
                                 "sound_present": audio.scrape_sound is not None}, "sound_events": fresh}
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+"\n")
                flags["rail_physical"].append(row["rail_physical_point_count"] > 0)
                flags["rail_penetrating"].append(row["rail_nonpositive_distance_point_count"] > 0)
                flags["contact_state"].append(any(contact["material"] == "metal_barrier" for contact in contacts))
                flags["candidate"].append(any(contact["audio_candidate"] for contact in contacts))
                flags["rail_candidate"].append(any(contact["material"] == "metal_barrier" and contact["audio_candidate"] for contact in contacts))
        with gzip.open(output / f"{name}-sound.jsonl.gz", "wt", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event, ensure_ascii=False)+"\n")
        return {"name": name, "config": asdict(config), "command": asdict(command), "initial_snapshot": initial,
                "ticks": TICKS, "raw_jsonl_gz": f"{name}.jsonl.gz", "sound_jsonl_gz": f"{name}-sound.jsonl.gz",
                "layered_hit_ticks": [event["observed_tick"] for event in events if event["type"] == "decision" and event.get("layers")],
                "scrape_attack_ticks": [event["observed_tick"] for event in events if event["type"] == "scrape" and event.get("state") == "attack"],
                "scrape_off_ticks": [event["observed_tick"] for event in events if event["type"] == "scrape" and event.get("state") == "off"],
                "gaps": {key: gaps(values) for key, values in flags.items()},
                "candidate_missing_while_rail_physical_ticks": sum(physical and not candidate for physical, candidate in zip(flags["rail_physical"], flags["rail_candidate"]))}
    finally:
        sound.close()
        simulation.close()


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    before = source_hashes()
    pending = list(TRIALS)
    report = {"status": "running", "source_before": before, "trials": [], "protocol": {
        "world": "original highway/no traffic, CAR config; FakeBase tests sound decisions, not audible quality",
        "initial": "(6.9,30,.55), velocity (.5,8,0), wheel pure rolling 8m/s once; no runtime state edits",
        "ticks": TICKS, "step_s": FIXED_DT, "candidate": "unchanged tangential_speed>=1.6m/s and raw_impulse>=25Ns",
        "physical_contact": "raw player rail points distance<=0 or positive applied impulse; nonpositive-distance counts separately; cached manifold existence alone does not prove contact",
        "scope": "diagnosis only; original one-hit/one-loop gate and audio thresholds unchanged; no performance or sound quality claim"}}
    try:
        for compliance, steering in TRIALS:
            report["trials"].append(run_trial(compliance, steering, output))
            pending.remove((compliance, steering))
        report["status"] = "completed"
    except Exception as error:
        report.update(status="failed", failed_trial=pending[0], not_run=pending[1:], error=f"{type(error).__name__}: {error}")
        raise
    finally:
        report["source_after"] = source_hashes()
        report["source_unchanged"] = before == report["source_after"]
        (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
