"""仅用已归档旧机械模块生成Double数值参考；不创建世界或改写旧归档。"""

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import sys
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/"src"), str(ROOT/"tests"), str(ROOT/"tools")]
PRIOR = ROOT/"docs/evidence/PHYS-SHARED-ROUNDING-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def differences(first, second, path="result"):
    if dataclasses.is_dataclass(first):
        return [item for field in dataclasses.fields(first)
                for item in differences(getattr(first, field.name), getattr(second, field.name), path+"."+field.name)]
    if isinstance(first, (tuple, list)):
        return [item for index, (a, b) in enumerate(zip(first, second, strict=True))
                for item in differences(a, b, path+f"[{index}]")]
    if first == second:
        return []
    return [{"field": path, "normal": first, "double": second,
             "absolute_difference": abs(first-second) if isinstance(first, (int, float)) else None}]


def capture(output, module_path, source_path):
    manifest = {item["path"]: item["sha256"] for item in json.loads((PRIOR/"archive-manifest.json").read_text(encoding="utf-8"))}
    if (sha(module_path) != manifest["production-before-mechanical_kernels.cp314-win_amd64.pyd"]
            or sha(source_path) != manifest["production-before.c"]):
        raise ValueError("只能用已归档修复前模块/源码建立参考，当前模块不能自生成期望值")
    spec = importlib.util.spec_from_file_location("mechanical_kernels", module_path)
    reference = importlib.util.module_from_spec(spec)
    sys.modules["mechanical_kernels"] = reference
    spec.loader.exec_module(reference)

    import test_continuous_solver as fixture

    import physics_workers
    import tire_drivetrain
    from lab_runtime import runtime_fingerprint

    runtime = runtime_fingerprint()
    if runtime["math_scalar_bits"] != 64:
        raise ValueError("仅在实际Double SDK中生成Double参考")
    assert Path(reference.__file__).resolve() == module_path and tire_drivetrain.joint_solve is reference.joint_solve
    output.mkdir(parents=True, exist_ok=False)
    inputs = sorted(fixture.FIXTURE.glob("input-*.bin"))
    hardware = fixture.load_hardware()
    payload = (fixture.FIXTURE/"geometry.pickle").read_bytes()
    memory = SharedMemory(create=True, size=len(payload))
    memory.buf[:] = payload
    geometry = physics_workers.GeometryRef(memory.name, len(payload), 1)
    hashes, delta, examples = {}, {}, []
    source_files = ["hardware.pickle", "geometry.pickle", "fixture.json", *[path.name for path in inputs],
                    *[path.name.replace("input-", "result-") for path in inputs]]
    source_sha = {name: sha(fixture.FIXTURE/name) for name in source_files}
    try:
        for path in inputs:
            identity = path.stem.removeprefix("input-")
            request = dataclasses.replace(fixture.from_bytes(path.read_bytes()), config=hardware)
            result = physics_workers._solve_vehicle(request, geometry)
            data = fixture.result_bytes(result)
            target = output/f"result-{identity}.bin"
            target.write_bytes(data)
            hashes[target.name] = sha(target)
            previous = fixture.from_bytes((fixture.FIXTURE/target.name).read_bytes())
            changed = differences(previous, result)
            delta[identity] = {"different_fields": len(changed),
                "maximum_absolute_difference": max((item["absolute_difference"] for item in changed
                                                    if item["absolute_difference"] is not None), default=0.)}
            if len(examples) < 5:
                examples.extend(changed[:5-len(examples)])
        geometry = dataclasses.replace(geometry, version=2)
        for path in reversed(inputs):
            request = dataclasses.replace(fixture.from_bytes(path.read_bytes()), config=hardware)
            result = physics_workers._solve_vehicle(request, geometry)
            assert fixture.result_bytes(result) == (output/path.name.replace("input-", "result-")).read_bytes()
    finally:
        physics_workers._worker_geometry = None
        physics_workers._worker_candidates.clear()
        physics_workers._worker_meshes.clear()
        physics_workers._worker_version = None
        if physics_workers._worker_memory is not None:
            physics_workers._worker_memory.close()
            physics_workers._worker_memory = None
        memory.close()
        memory.unlink()
    assert all(sha(fixture.FIXTURE/name) == value for name, value in source_sha.items())
    context = {"schema": "continuous-double-reference-v1", "sdk": runtime,
        "reference": {"git_source": "9eb7bf9", "module": str(module_path.relative_to(ROOT)), "module_sha256": sha(module_path),
                      "c_source": str(source_path.relative_to(ROOT)), "c_sha256": sha(source_path)},
        "input_fixture": fixture.FIXTURE.relative_to(ROOT).as_posix(), "input_sha256": source_sha,
        "codec_sha256": hashlib.sha256(fixture.FROZEN_SIGNATURE).hexdigest(),
        "effective_hardware": dataclasses.asdict(hardware), "output_sha256": hashes,
        "normal_differences": delta, "difference_examples": examples, "reverse_repeat_exact": True,
        "kind": "旧模块/当前相同输入适配在实际Double SDK的独立数值参考；非物理重跑或性能基准"}
    (output/"context.json").write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"reference_module_sha256": context["reference"]["module_sha256"], "inputs": len(inputs),
            "different_from_normal": sum(bool(item["different_fields"]) for item in delta.values()), "examples": examples}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference-module", type=Path, required=True)
    parser.add_argument("--reference-source", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.output.resolve(), args.reference_module.resolve(), args.reference_source.resolve()), ensure_ascii=False))
