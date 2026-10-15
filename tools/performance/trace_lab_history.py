"""同工程配置的历史完整试验短测；可选采样分析，不改求解器、初始化或步长。"""

import argparse
import cProfile
import hashlib
import json
import pickle
import pstats
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(args):
    source = args.source.resolve()
    sys.path.insert(0, str(source/"src"))
    from lab_experiment import LabExperiment, LabOptions
    from vehicle_designs import vehicle_design
    from vehicle_parameters import config_from_document

    native_modules = {name: str(Path(sys.modules[name].__file__).resolve())
                      for name in ("physics_packet_kernels", "mechanical_kernels", "wheel_contact_kernels",
                                   "convex_cast_kernels", "radial_contact_kernels") if name in sys.modules}
    assert all(Path(path).parent == source/"src" for path in native_modules.values())
    timings = {}
    iterations = []

    def measured(name, function):
        def call(*values, **keywords):
            before = time.perf_counter()
            result = function(*values, **keywords)
            duration = time.perf_counter()-before
            row = timings.setdefault(name, {"calls": 0, "inclusive_seconds": 0.})
            row["calls"] += 1
            row["inclusive_seconds"] += duration
            if name == "joint":
                iterations.append(result.iterations)
            return result
        return call

    if args.instrument:
        import vehicle_unsprung
        from radial_geometry import RadialRoads
        from unsprung_contact_geometry import FiniteRadialContact
        from unsprung_motion import FiniteSuspensionMotion
        vehicle_unsprung.solve_unsprung_joint = measured("joint", vehicle_unsprung.solve_unsprung_joint)
        for name, cls in (("finite_contact", FiniteRadialContact), ("radial_query", RadialRoads),
                          ("finite_motion", FiniteSuspensionMotion)):
            method = "query" if name == "radial_query" else "evaluate"
            setattr(cls, method, measured(name, getattr(cls, method)))

    document = json.loads(args.engineering.read_text(encoding="utf-8"))
    config = config_from_document(document, vehicle_design("reference-rwd").config)
    if args.unsprung_off:
        config = replace(config, unsprung_enabled=False)
    options = LabOptions(duration=(args.ticks+args.profile_ticks)/120)
    args.output.mkdir(parents=True, exist_ok=False)
    started, cpu = time.perf_counter(), time.process_time()
    experiment = LabExperiment(options, config=config, parameter_metadata=document["metadata"])
    initialization = {"wall_seconds": time.perf_counter()-started,
                      "cpu_seconds": time.process_time()-cpu,
                      "ticks": experiment.current.tick}
    try:
        print(json.dumps({"initialization": initialization}), flush=True)
        timings.clear()
        iterations.clear()
        elapsed = []
        started, cpu = time.perf_counter(), time.process_time()
        for _ in range(args.ticks):
            before = time.perf_counter()
            experiment.step()
            elapsed.append(time.perf_counter()-before)
        measured = {"wall_seconds": time.perf_counter()-started,
                    "cpu_seconds": time.process_time()-cpu,
                    "physics_snapshot_seconds": experiment.compute_seconds,
                    "ticks": args.ticks, "step_seconds": elapsed}
        measured_timings = {name: dict(values) for name, values in timings.items()}
        measured_iterations = list(iterations)
        # 运行实例epoch不属于物理结果，其他完整快照逐字节进入摘要。
        snapshot_hashes = [hashlib.sha256(pickle.dumps(replace(state, contact_epoch=0,
            impacts=tuple(replace(event, epoch=0) for event in state.impacts)), protocol=5)).hexdigest()
            for state in experiment.snapshots]
        if args.profile_ticks:
            profiler = cProfile.Profile()
            profiler.enable()
            for _ in range(args.profile_ticks):
                experiment.step()
            profiler.disable()
            profiler.dump_stats(str(args.output/"step.prof"))
            stats = pstats.Stats(profiler)
            with (args.output/"profile.txt").open("w", encoding="utf-8") as stream:
                stats.stream = stream
                stats.sort_stats("cumulative").print_stats(70)
                stats.sort_stats("tottime").print_stats(40)
            rows = [{"file": path, "line": line, "function": function,
                     "primitive_calls": values[0], "calls": values[1],
                     "self_seconds": values[2], "cumulative_seconds": values[3]}
                    for (path, line, function), values in stats.stats.items()]
            (args.output/"profile.json").write_text(json.dumps(
                {"ticks": args.profile_ticks, "total_seconds": stats.total_tt, "functions": rows},
                ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        from panda3d import bullet, core
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (source/"src").iterdir() if p.suffix in (".py", ".pyd", ".c", ".cpp", ".h")}
        result = {"source": str(source), "engineering": str(args.engineering.resolve()),
                  "runtime": {"panda": core.PandaSystem.getVersionString(),
                              "bullet": bullet.getBulletVersion(),
                              "scalar_bits": 64 if core.LPoint3 is core.LPoint3d else 32,
                              "module": core.__file__},
                  "config": asdict(experiment.config), "options": asdict(options),
                  "initialization": initialization, "measured": measured,
                  "instrumented": args.instrument, "inclusive_timings": measured_timings,
                  "joint_iterations": measured_iterations, "snapshot_hashes": snapshot_hashes,
                  "profile_ticks": args.profile_ticks, "source_hashes": files,
                  "loaded_native_modules": native_modules,
                  "final_tick": experiment.current.tick, "reason": experiment.reason,
                  "scope": "真实初始化后顺序完整步；跨版本状态随模型改变，不宣称数值等价或实时Gate"}
        (args.output/"result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n",
                                             encoding="utf-8")
        print(json.dumps({"measured": measured, "result": str(args.output/"result.json")}), flush=True)
    finally:
        experiment.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--engineering", type=Path,
                        default=ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ticks", type=int, default=24)
    parser.add_argument("--profile-ticks", type=int, default=0)
    parser.add_argument("--unsprung-off", action="store_true")
    parser.add_argument("--instrument", action="store_true")
    run(parser.parse_args())
