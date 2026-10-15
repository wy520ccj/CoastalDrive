"""相同新版工程配置：直接离线求解与实际离屏界面分批计算，分开统计初始化/物理/界面。"""

import argparse
import hashlib
import json
import os
import pickle
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))

from lab_application import VehicleLab
from lab_experiment import LabExperiment
from lab_runtime import runtime_fingerprint


def digest(state):
    normalized = replace(state, contact_epoch=0,
                         impacts=tuple(replace(event, epoch=0) for event in state.impacts))
    return hashlib.sha256(pickle.dumps(normalized, protocol=5)).hexdigest()


def check(output, engineering):
    output.mkdir(parents=True, exist_ok=False)
    os.environ["LOCALAPPDATA"] = str(output/"user-data")
    app = VehicleLab(offscreen=True, output=output/"records")
    try:
        app.import_engineering(engineering)
        app.entries["duration"].enterText("0.2")
        options = app.read_options()
        started = time.perf_counter()
        direct = LabExperiment(options, config=app.engineered_config,
                               parameter_metadata=app.parameter_metadata)
        direct_initialization = time.perf_counter()-started
        try:
            started, started_cpu = time.perf_counter(), time.process_time()
            while not direct.done:
                direct.step()
            direct_wall = time.perf_counter()-started
            direct_cpu = time.process_time()-started_cpu
            expected = [digest(state) for state in direct.snapshots]
            direct_result = {"initialization_seconds": direct_initialization,
                             "wall_seconds": direct_wall, "cpu_seconds": direct_cpu,
                             "physics_and_snapshot_seconds": direct.compute_seconds,
                             "ticks": len(direct.samples)-1}
        finally:
            direct.close()
        started = time.perf_counter()
        app.start_experiment()
        gui_initialization = time.perf_counter()-started
        assert app.run_state is not None
        assert app.run_state.config == app.engineered_config or app.run_state.config == direct.config
        started, started_cpu, frames, chunks = time.perf_counter(), time.process_time(), 0, []
        while not app.run_state.done:
            before = app.run_state.current.tick
            app.taskMgr.step()
            chunks.append(app.run_state.current.tick-before)
            frames += 1
        gui_wall, gui_cpu = time.perf_counter()-started, time.process_time()-started_cpu
        assert [digest(state) for state in app.run_state.snapshots] == expected
        assert app.run_state.samples == direct.samples
        assert app.run_state.commands == direct.commands
        report = {"runtime": runtime_fingerprint(), "engineering": str(engineering),
                  "options": str(options), "simulated_seconds": app.run_state.elapsed,
                  "direct": direct_result,
                  "gui": {"initialization_seconds": gui_initialization,
                          "wall_seconds": gui_wall, "cpu_seconds": gui_cpu,
                          "physics_and_snapshot_seconds": app.run_state.compute_seconds,
                          "other_wall_seconds": gui_wall-app.run_state.compute_seconds,
                          "frames": frames, "ticks_per_frame": chunks},
                  "step_budget_seconds": .006, "full_snapshots_signals_commands_equal": True,
                  "scope": "0.2s default preview configuration, offscreen UI; not a visible performance gate"}
        (output/"result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        print(json.dumps({"simulated_seconds": report["simulated_seconds"], "direct": direct_result,
                          "gui": report["gui"], "identical_results": True}), flush=True)
    finally:
        app.close_game()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--engineering", type=Path,
                        default=ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json")
    args = parser.parse_args()
    check(args.output.resolve(), args.engineering.resolve())
