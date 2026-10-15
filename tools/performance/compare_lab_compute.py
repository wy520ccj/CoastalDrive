"""独立进程对照完整试验台；比较全部快照、信号、输入和每个共同解的能量账。"""

import argparse
import hashlib
import json
import pickle
import subprocess
import sys
import time
from dataclasses import asdict, fields, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def worker(args):
    source = args.source.resolve()
    sys.path.insert(0, str(source/"src"))
    from lab_experiment import LabExperiment, LabOptions
    from vehicle_designs import vehicle_design
    from vehicle_parameters import config_from_document
    from vehicle_unsprung import UnsprungAdvanceInput

    document = json.loads((ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json").read_text(encoding="utf-8"))
    config = config_from_document(document, vehicle_design("reference-rwd").config)
    options = {"braking": LabOptions(duration=.2),
               "turning": LabOptions(maneuver="step_steer", speed_kph=30., duration=.4, onset=0., steering_deg=2.),
               "nonlinear-bump": LabOptions(maneuver="ride_bump", speed_kph=18., duration=1.2,
                                            bump_distance_m=2., bump_length_m=.4)}[args.scenario]
    metadata = document["metadata"]
    if args.scenario == "nonlinear-bump":
        sys.path.insert(0, str(ROOT/"tests"))
        from damper_bench_reference import document as bench_document

        from suspension_bench import fit_bench
        config, report = fit_bench(bench_document(), config)
        assert report["passed"]
        assert config.suspension_coil_enabled
        assert config.suspension_installation_curves is not None and config.suspension_damper_curves is not None
        metadata = {"suspension_calibration": report, "basis": "合成部件数据，优化一致性对照，不代表实车标定"}

    native_modules = {name: Path(sys.modules[name].__file__).resolve()
                      for name in ("physics_packet_kernels", "mechanical_kernels", "wheel_contact_kernels",
                                   "convex_cast_kernels", "radial_contact_kernels") if name in sys.modules}
    assert all(path.parent == source/"src" for path in native_modules.values())
    args.output.mkdir(parents=True, exist_ok=False)
    before, cpu = time.perf_counter(), time.process_time()
    run = LabExperiment(options, config=config, parameter_metadata=metadata)
    initialization = {"wall_seconds": time.perf_counter()-before, "cpu_seconds": time.process_time()-cpu,
                      "ticks": run.current.tick}
    captured = []
    original = UnsprungAdvanceInput.solve

    def solve(value, **kwargs):
        result = original(value, **kwargs)
        captured.append(result)
        return result

    UnsprungAdvanceInput.solve = solve
    try:
        elapsed = []
        before, cpu = time.perf_counter(), time.process_time()
        while not run.done:
            tick = time.perf_counter()
            run.step()
            elapsed.append(time.perf_counter()-tick)
        wall, cpu = time.perf_counter()-before, time.process_time()-cpu
        assert run.reason == "time_limit" and len(elapsed) == round(options.duration*120)
        snapshots = [replace(state, contact_epoch=0,
                             impacts=tuple(replace(event, epoch=0) for event in state.impacts)) for state in run.snapshots]
        joint = [{field.name: getattr(result, field.name) for field in fields(result)
                  if field.name != "contact_geometry"} for result in captured]
        payload = {"snapshots": snapshots, "samples": run.samples, "commands": run.commands, "joint": joint}
        binary = pickle.dumps(payload, protocol=5)
        (args.output/"payload.bin").write_bytes(binary)
        from panda3d import bullet, core
        result = {"source": str(source), "scenario": args.scenario, "options": asdict(options),
                  "config": asdict(run.config), "requested_config": asdict(config), "initialization": initialization,
                  "wall_seconds": wall, "cpu_seconds": cpu, "physics_snapshot_seconds": run.compute_seconds,
                  "step_seconds": elapsed, "ticks": len(elapsed), "substeps": len(captured),
                  "joint_iterations": [r.iterations for r in captured],
                  "payload_sha256": hashlib.sha256(binary).hexdigest(),
                  "runtime": {"panda": core.PandaSystem.getVersionString(), "bullet": bullet.getBulletVersion(),
                              "scalar_bits": 64 if core.LPoint3 is core.LPoint3d else 32, "module": core.__file__},
                  "native": {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                             for name, path in native_modules.items()},
                  "source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in (source/"src").iterdir() if p.suffix in (".py", ".c", ".cpp", ".h")}}
        (args.output/"result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(json.dumps({"scenario": args.scenario, "wall_seconds": wall,
                          "initialization": initialization, "payload_sha256": result["payload_sha256"]}), flush=True)
    finally:
        UnsprungAdvanceInput.solve = original
        run.close()


def compare(args):
    args.output.mkdir(parents=True, exist_ok=False)
    cases = [("braking-A1", "braking", args.baseline), ("braking-B1", "braking", ROOT),
             ("braking-B2", "braking", ROOT), ("braking-A2", "braking", args.baseline),
             ("turning-A", "turning", args.baseline), ("turning-B", "turning", ROOT),
             ("nonlinear-A", "nonlinear-bump", args.baseline), ("nonlinear-B", "nonlinear-bump", ROOT)]
    reference, rows = {}, []
    for name, scenario, source in cases:
        command = [sys.executable, str(ROOT/"tools/physics/run_sim_double.py"), str(Path(__file__).resolve()),
                   "--worker", "--source", str(source.resolve()), "--scenario", scenario,
                   "--output", str((args.output/name).resolve())]
        print("RUN", name, flush=True)
        with (args.output/(name+".txt")).open("w", encoding="utf-8") as stream:
            completed = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=240, check=False)
        assert completed.returncode == 0, name
        result = json.loads((args.output/name/"result.json").read_text(encoding="utf-8"))
        binary = (args.output/name/"payload.bin").read_bytes()
        if scenario in reference:
            assert binary == reference[scenario], f"{name}完整物理结果不同，停止后续对照"
        else:
            reference[scenario] = binary
        row = {"case": name, **result, "complete_payload_equal": True}
        rows.append(row)
        (args.output/"summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print("PASSED", name, round(result["wall_seconds"], 4), "s; exact", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--source", type=Path, default=ROOT)
    parser.add_argument("--baseline", type=Path, default=ROOT/"builds/lab-perf-02/baseline")
    parser.add_argument("--scenario", choices=("braking", "turning", "nonlinear-bump"), default="braking")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    worker(args) if args.worker else compare(args)
