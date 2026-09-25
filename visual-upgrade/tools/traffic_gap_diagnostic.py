"""只读采样：记录繁忙弯坡高速的道路相对车流与回收状态。"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from curve_drive_check import _nearby_npc_contact
from endurance_check import EnduranceDriver

from highway_run import TRAFFIC_DENSITIES
from simulation import FIXED_DT, Simulation


def measure(road, state, drivers):
    player_s, player_lateral = road.locate(state.player)
    cars = []
    for index, (car, driver) in enumerate(zip(state.traffic, drivers)):
        car_s, lateral = road.locate(car)
        cars.append({
            "id": index, "active": car.active, "retired": not car.active,
            "generation": car.generation, "lane": driver.lane,
            "delta_s": round(road.delta(car_s, player_s), 3),
            "relative_lateral": round(lateral - player_lateral, 3),
            "speed": round(car.speed, 3), "phase": getattr(driver, "phase", None),
        })
    ahead = [car["delta_s"] for car in cars if car["active"] and car["delta_s"] > 0]
    behind = [-car["delta_s"] for car in cars if car["active"] and car["delta_s"] < 0]
    return {
        "tick": state.tick, "time": round(state.time, 3),
        "player_s": round(player_s, 3), "player_lateral": round(player_lateral, 3),
        "player_speed": round(state.player.speed, 3), "cars": cars,
        "active": len(ahead) + len(behind) + sum(
            car["active"] and car["delta_s"] == 0 for car in cars
        ),
        "retired": sum(car["retired"] for car in cars),
        "ahead": len(ahead), "behind": len(behind),
        "nearest_ahead": min(ahead, default=None),
        "nearest_behind": min(behind, default=None),
        "ahead_150": sum(value <= 150 for value in ahead),
        "ahead_300": sum(value <= 300 for value in ahead),
        "ahead_600": sum(value <= 600 for value in ahead),
        "behind_150": sum(value <= 150 for value in behind),
        "behind_300": sum(value <= 300 for value in behind),
        "behind_600": sum(value <= 600 for value in behind),
    }


def sparse_intervals(samples, events, *, threshold=2):
    intervals = []
    start = None
    for index, sample in enumerate(samples):
        sparse = sample["ahead_150"] + sample["behind_150"] <= threshold
        if sparse and start is None:
            start = index
        if start is not None and (not sparse or index == len(samples) - 1):
            end = index - 1 if not sparse else index
            first, last = samples[start], samples[end]
            intervals.append({
                "start_time": first["time"], "end_time": last["time"],
                "duration_s": round(last["time"] - first["time"], 3),
                "start_s": first["player_s"], "end_s": last["player_s"],
                "start_sample": first, "middle_sample": samples[(start + end) // 2],
                "end_sample": last,
                "events": [event for event in events
                           if first["time"] <= event["time"] <= last["time"]],
            })
            start = None
    return sorted(intervals, key=lambda item: item["duration_s"], reverse=True)


def run(seed, output, distance=5000, sample_ticks=120):
    density = TRAFFIC_DENSITIES["busy"]
    sim = Simulation(seed, track="endless", road_shape="hills",
                     traffic_count=density.cars, traffic_span=density.spawn_span)
    controller = EnduranceDriver(sim, seed + 701)
    output.mkdir(parents=True, exist_ok=True)
    samples_path = output / "samples.jsonl"
    events_path = output / "events.jsonl"
    if samples_path.exists() or events_path.exists():
        raise FileExistsError("诊断目录已有采样文件")
    state = sim.snapshot()
    start_s = sim.road.locate(state.player)[0]
    previous = [(car.active, car.generation) for car in state.traffic]
    samples, events, failures = [], [], []
    started = time.perf_counter()
    last_event = None
    try:
        with samples_path.open("w", encoding="utf-8") as sample_file, events_path.open("w", encoding="utf-8") as event_file:
            initial = measure(sim.road, state, sim.drivers)
            initial["last_event"] = None
            samples.append(initial)
            sample_file.write(json.dumps(initial, ensure_ascii=False) + "\n")
            while sim.road.locate(state.player)[0] - start_s < distance:
                sim.step(controller.sample(state, FIXED_DT))
                state = sim.snapshot()
                for index, car in enumerate(state.traffic):
                    _, old_generation = previous[index]
                    if (car.active, car.generation) != previous[index]:
                        kinds = (["retire", "recycle"] if car.generation - old_generation == 2
                                 else ["recycle" if car.active else "retire"])
                        for offset, kind in enumerate(kinds, start=1):
                            event = {"tick": state.tick, "time": round(state.time, 3),
                                     "id": index, "type": kind,
                                     "generation": old_generation + offset,
                                     "player_s": round(sim.road.locate(state.player)[0], 3),
                                     "delta_s_after_update": round(sim.road.delta(
                                         sim.road.locate(car)[0], sim.road.locate(state.player)[0]), 3)}
                            events.append(event)
                            event_file.write(json.dumps(event, ensure_ascii=False) + "\n")
                            last_event = event
                    previous[index] = (car.active, car.generation)
                if state.tick % sample_ticks == 0:
                    sample = measure(sim.road, state, sim.drivers)
                    sample["last_event"] = last_event
                    samples.append(sample)
                    sample_file.write(json.dumps(sample, ensure_ascii=False) + "\n")
                    sample_file.flush()
                    if state.events and "player_reset" in state.events:
                        failures.append({"tick": state.tick, "type": "player_reset"})
                    if sim.collision_count or _nearby_npc_contact(sim, state):
                        failures.append({"tick": state.tick, "type": "collision"})
                if state.time > 600:
                    failures.append({"tick": state.tick, "type": "timeout_600s"})
                    break
            intervals = sparse_intervals(samples, events)
            summary = {
                "seed": seed, "shape": "hills", "density": "busy",
                "traffic_count": density.cars, "traffic_span": density.spawn_span,
                "sample_ticks": sample_ticks, "target_distance_m": distance,
                "distance_m": round(sim.road.locate(state.player)[0] - start_s, 3),
                "time_s": round(state.time, 3), "wall_seconds": round(time.perf_counter() - started, 3),
                "samples": len(samples), "retire_events": sum(e["type"] == "retire" for e in events),
                "recycle_events": sum(e["type"] == "recycle" for e in events),
                "retired_at_end": samples[-1]["retired"],
                "sparse_definition": f"active vehicles within +/-150 m <= 2 at {sample_ticks}-tick samples",
                "longest_sparse": intervals[0] if intervals else None,
                "sparse_intervals": len(intervals), "failures": failures,
                "completed": sim.road.locate(state.player)[0] - start_s >= distance,
            }
            (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            return summary
    finally:
        sim.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--distance", type=float, default=5000)
    parser.add_argument("--sample-ticks", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.distance <= 0 or args.sample_ticks <= 0:
        parser.error("距离和采样间隔必须大于零")
    result = run(args.seed, args.output, args.distance, args.sample_ticks)
    print(json.dumps({key: value for key, value in result.items()
                      if key != "longest_sparse"}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["completed"] else 1)
