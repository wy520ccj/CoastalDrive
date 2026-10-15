"""同一可信失败输入：原执行字节与精确端口导数对照，不再推进真实世界。"""

import argparse
import json
import runpy
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))
sys.path.insert(0, str(ROOT/"tools"))

from physics.unsprung_step_checkpoint import load_step

import vehicle_unsprung
from lab_records import model_fingerprint


def check(output):
    output.mkdir(parents=True, exist_ok=False)
    failure = ROOT/"logs/SIM-UNSPRUNG-01/component-bench-init-failure-r1"
    old_source = json.loads((failure/"source.json").read_text(encoding="utf-8"))
    current = model_fingerprint()
    assert {Path(key).as_posix() for key in old_source if old_source[key] != current[key]} <= {"src/unsprung_joint.py", "src/suspension_bench.py"}
    with zipfile.ZipFile(failure/"executed-model.zip") as package:
        old_path = output/"executed-old-unsprung-joint.py"
        old_path.write_bytes(package.read("src/unsprung_joint.py"))
    old_function = runpy.run_path(str(old_path))["solve_unsprung_joint"]
    current_function = vehicle_unsprung.solve_unsprung_joint
    result = {}
    for name, function in (("old", old_function), ("new", current_function)):
        source = load_step(failure/"failed-step.pkl")
        vehicle_unsprung.solve_unsprung_joint = function
        try:
            step = source.solve()
            result[name] = {"passed": True, "iterations": step.iterations, "momentum_Ns": step.momentum_error,
                           "force_N": step.force_error, "port_Nm": step.port_error,
                           "port_torques_Nm": step.port_torques.tolist(), "energy_error_J": step.energy_error}
        except ArithmeticError as error:
            result[name] = {"passed": False, "error": str(error)}
        finally:
            vehicle_unsprung.solve_unsprung_joint = current_function
    assert not result["old"]["passed"] and result["new"]["passed"]
    (output/"result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    check(parser.parse_args().output.resolve())
