"""采集固定GR86单车配置的短时cProfile诊断。"""

import cProfile
import hashlib
import json
import pstats
import sys
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent / "profile-port-accurate-r1"
OUTPUT.mkdir(exist_ok=False)
sys.path.insert(0, str(ROOT / "src"))


def source_hashes():
    files = {}
    for path in sorted(p for p in (ROOT / "src").rglob("*") if p.suffix in (".py", ".c", ".h", ".pyd")):
        relative = path.relative_to(ROOT).as_posix()
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    joined = "".join(f"{name} {digest}\n" for name, digest in files.items()).encode("utf-8")
    return files, hashlib.sha256(joined).hexdigest()


def profile_rows(profile_stats, sort_index):
    entries = sorted(
        profile_stats.stats.items(),
        key=lambda item: (-item[1][sort_index], item[0][0], item[0][1], item[0][2]),
    )[:20]
    rows = []
    for (filename, line, function), (primitive_calls, total_calls, self_time, cumulative_time, _callers) in entries:
        try:
            filename = Path(filename).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            filename = Path(filename).name
        rows.append({
            "file": filename,
            "line": line,
            "function": function,
            "primitive_calls": primitive_calls,
            "total_calls": total_calls,
            "self_seconds": self_time,
            "cumulative_seconds": cumulative_time,
        })
    return rows


def main():
    started = time.perf_counter()
    profile = cProfile.Profile(timer=time.perf_counter)
    simulation = None
    profiled_steps = 0
    profile_active = False
    setup_seconds = None
    warmup_seconds = None
    profiled_wall_seconds = None
    cleanup_seconds = None
    source_before = {}
    source_before_tree = None
    source_after = {}
    source_after_tree = None
    error = None

    hash_start = time.perf_counter()
    source_before, source_before_tree = source_hashes()
    source_hash_before_seconds = time.perf_counter() - hash_start

    try:
        from driving_modes import DrivingMode
        from simulation import Control, Simulation
        from vehicle_designs import GR86_DESIGN

        setup_start = time.perf_counter()
        simulation = Simulation(
            seed=17,
            track="coastal",
            traffic_count=8,
            config=GR86_DESIGN,
            input_config=DrivingMode.GAME.input_config,
        )
        setup_seconds = time.perf_counter() - setup_start

        warmup_start = time.perf_counter()
        for _ in range(8):
            simulation.step(Control(throttle=0.3))
        warmup_seconds = time.perf_counter() - warmup_start

        profile_start = time.perf_counter()
        profile.enable()
        profile_active = True
        try:
            for _ in range(16):
                simulation.step(Control(throttle=0.3))
                profiled_steps += 1
        finally:
            profile.disable()
            profile_active = False
            profiled_wall_seconds = time.perf_counter() - profile_start
    except BaseException as exc:
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        if profile_active:
            profile.disable()
        profile.dump_stats(str(OUTPUT / "gr86-profile.prof"))

        cleanup_start = time.perf_counter()
        if simulation is not None:
            try:
                simulation.close()
            except BaseException as exc:
                if error is None:
                    error = {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "traceback": traceback.format_exc(),
                    }
        cleanup_seconds = time.perf_counter() - cleanup_start

        source_hash_after_start = time.perf_counter()
        source_after, source_after_tree = source_hashes()
        source_hash_after_seconds = time.perf_counter() - source_hash_after_start

    changed = sorted(
        name for name in set(source_before) | set(source_after)
        if source_before.get(name) != source_after.get(name)
    )
    stats = pstats.Stats(profile)
    report = {
        "status": "completed" if error is None and profiled_steps == 16 else "incomplete",
        "head": "dff36ee + accurate port reconstruction",
        "simulation": {
            "seed": 17,
            "track": "coastal",
            "traffic_count": 8,
            "config": "GR86_DESIGN",
            "input_config": "DrivingMode.GAME.input_config",
            "control": "Control(throttle=0.3)",
            "warmup_steps": 8,
            "profiled_steps_requested": 16,
            "profiled_steps_completed": profiled_steps,
            "fixed_step_hz": 120,
            "window": False,
            "sensor_run": False,
        },
        "wall_clock_seconds": {
            "source_hash_before": source_hash_before_seconds,
            "setup": setup_seconds,
            "warmup_8_steps": warmup_seconds,
            "profiled_16_step_window": profiled_wall_seconds,
            "cleanup": cleanup_seconds,
            "source_hash_after": source_hash_after_seconds,
            "total_through_measurement": time.perf_counter() - started,
        },
        "profile_file": "gr86-profile.prof",
        "top_20_by_cumulative_time": profile_rows(stats, 3),
        "top_20_by_self_time": profile_rows(stats, 2),
        "src_sha256": {
            "before_tree": source_before_tree,
            "after_tree": source_after_tree,
            "unchanged": source_before == source_after,
            "changed_files": changed,
            "before_files": source_before,
            "after_files": source_after,
        },
        "error": error,
        "interpretation": "短时离屏诊断数据；墙钟时间不是FPS或前台性能Gate。",
    }
    (OUTPUT / "profile.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "profiled_steps_completed": profiled_steps,
        "profiled_wall_seconds": profiled_wall_seconds,
        "src_unchanged": source_before == source_after,
        "error": error,
    }, ensure_ascii=True))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())



