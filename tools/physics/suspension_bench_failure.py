"""只重放候选初始化，保存真实失败输入与共同Newton端口轨迹。"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))
sys.path.insert(0, str(ROOT/"tools"))

from physics.unsprung_step_checkpoint import save_step

from lab_experiment import LabExperiment, LabOptions
from lab_records import model_fingerprint
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import config_from_document
from vehicle_unsprung import UnsprungAdvanceInput


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    source = model_fingerprint()
    (output/"source.json").write_text(json.dumps(source, indent=2), encoding="utf-8")
    with zipfile.ZipFile(output/"executed-model.zip", "w", zipfile.ZIP_DEFLATED) as package:
        for relative in source: package.write(ROOT/relative, relative)
    document = json.loads((ROOT/"logs/SIM-UNSPRUNG-01/component-bench-AB-r1/accepted/candidate-vehicle.json").read_text(encoding="utf-8"))
    config = config_from_document(document, REFERENCE_DESIGN)
    history = []

    def trace(frame, event, arg):
        if frame.f_code.co_name != "solve_unsprung_joint":
            return None
        if frame.f_code.co_name == "solve_unsprung_joint" and event == "line" and "port_error" in frame.f_locals:
            loc = frame.f_locals
            if "if momentum_error<" in lines[frame.f_lineno-1] and len(history) < 6000:
                history.append({"iteration": loc["iteration"], "residual": loc["residual"][24:].tolist(),
                    "torques": loc["values"][24:].tolist(), "speeds": loc["details"][8].tolist(),
                    "brakes": loc["brakes"].tolist(), "clutch_capacity": loc["clutch_capacity"]})
        return trace

    lines = (ROOT/"src/unsprung_joint.py").read_text(encoding="utf-8").splitlines()
    original = UnsprungAdvanceInput.solve

    def solve(inputs, **kwargs):
        history.clear()
        sys.settrace(trace)
        try:
            return original(inputs, **kwargs)
        except ArithmeticError:
            save_step(inputs, output/"failed-step.pkl")
            (output/"trace.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
            raise
        finally:
            sys.settrace(None)

    UnsprungAdvanceInput.solve = solve
    try:
        run = LabExperiment(LabOptions(maneuver="ride_bump", speed_kph=18., duration=2.4), config=config,
                            parameter_metadata=document["metadata"])
        run.close()
    except ArithmeticError as error:
        (output/"failure.txt").write_text(str(error), encoding="utf-8")
        print(json.dumps({"failed_step_saved": True, "last": history[-1]}))
    finally:
        UnsprungAdvanceInput.solve = original


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    check(parser.parse_args().output.resolve())
