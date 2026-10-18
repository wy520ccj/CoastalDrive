"""固定种子复现滨海失败并保存诊断快照；快照尚非等价独立重放。"""

import argparse
import hashlib
import json
import pickle
import sys
from dataclasses import fields, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))
sys.path.insert(0, str(ROOT/"tools"))

from coastal_medals_check import check

from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from physics_workers import FrozenWorldSurface
from suspension_geometry import CylinderSurface
from tire_drivetrain import DrivetrainInput


def freeze(inputs):
    system = inputs.parameters["suspension"]
    planes, groups = [], None
    for plane in system.kinematics:
        if plane is None:
            planes.append(None)
            continue
        surface = plane.surface
        if groups is None:
            groups = tuple((index, supported, tuple((None, *part[1:]) for part in parts))
                           for index, (_body, supported, parts) in enumerate(surface.static_shapes))
        frozen = FrozenWorldSurface(**{field.name: getattr(surface, field.name) for field in fields(CylinderSurface)})
        planes.append(replace(plane, surface=frozen))
    return replace(inputs, parameters={**inputs.parameters, "suspension": replace(system, kinematics=tuple(planes))}), groups


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    original, calls = DrivetrainInput.solve, 0
    def solve(inputs, **kwargs):
        nonlocal calls
        calls += 1
        try:
            return original(inputs, **kwargs)
        except ArithmeticError:
            frozen, groups = freeze(inputs)
            (output/"failed-input.pkl").write_bytes(pickle.dumps((frozen, groups, kwargs), protocol=5))
            raise
    DrivetrainInput.solve = solve
    try:
        result = check(output/"drive", (1024, 768))
        summary = {"reproduced": False, "result": result, "calls": calls}
    except ArithmeticError as error:
        summary = {"reproduced": True, "error": str(error), "calls": calls,
            "sha256": hashlib.sha256((output/"failed-input.pkl").read_bytes()).hexdigest()}
    finally:
        DrivetrainInput.solve = original
    summary.update(source=model_fingerprint(), runtime=runtime_fingerprint())
    (output/"summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return {key: value for key, value in summary.items() if key not in ("source", "runtime")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.output.resolve()), ensure_ascii=False))
