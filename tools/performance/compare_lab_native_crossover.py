"""冻结真实制动子步，在同一进程交叉使用旧/新wheel函数；仅诊断，不作为整步性能Gate。"""

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import struct
import sys
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def numeric(value):
    if dataclasses.is_dataclass(value):
        return {field.name:numeric(getattr(value,field.name)) for field in dataclasses.fields(value)
                if field.name != "contact_geometry"}
    import numpy as np

    if isinstance(value,np.ndarray):
        return {"dtype":value.dtype.str,"shape":value.shape,"bytes":value.tobytes().hex()}
    if isinstance(value,np.generic):
        return {"scalar_dtype":value.dtype.str,"bytes":value.tobytes().hex()}
    if isinstance(value,float):
        return {"float_bytes":struct.pack("!d",value).hex()}
    if isinstance(value,(tuple,list)):
        return [numeric(item) for item in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(numeric(value),sort_keys=True,separators=(",",":")).encode()).hexdigest()


def main(args):
    sys.path[:0] = [str(ROOT/"src"),str(ROOT/"tools/physics")]
    import numpy as np
    import wheel_contact_kernels as current
    from unsprung_step_checkpoint import load_step, save_step

    from lab_experiment import LabExperiment, LabOptions
    from lab_runtime import runtime_fingerprint
    from vehicle_designs import vehicle_design
    from vehicle_parameters import config_from_document
    from vehicle_unsprung import UnsprungAdvanceInput

    old_path = args.old_extension.resolve()
    if not old_path.is_file():
        raise FileNotFoundError(old_path)
    spec = importlib.util.spec_from_file_location("lab_old.wheel_contact_kernels",old_path)
    if spec is None or spec.loader is None:
        raise ValueError("旧扩展必须为本机可加载的wheel_contact_kernels原生模块")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    assert Path(old.__file__).resolve() == old_path
    args.output.mkdir(parents=True,exist_ok=False)
    inputs = args.output/"inputs"
    inputs.mkdir()
    document = json.loads((ROOT/"docs/evidence/SIM-UNSPRUNG-01/production/engineering-preview.json").read_text(encoding="utf-8"))
    config = config_from_document(document,vehicle_design("reference-rwd").config)
    run = LabExperiment(LabOptions(duration=.2),config=config,parameter_metadata=document["metadata"])
    captured = []
    original = UnsprungAdvanceInput.solve

    def solve(source,**kwargs):
        result = original(source,**kwargs)
        path = inputs/f"{len(captured):03d}.pkl"
        save_step(source,path)
        captured.append({"path":path.name,"input_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                         "reference_sha256":digest(result)})
        return result

    UnsprungAdvanceInput.solve = solve
    try:
        while not run.done:
            run.step()
        assert len(captured)==48 and max(command.brake for command in run.commands)==1.
        experiment = {"options":dataclasses.asdict(run.options),"config":dataclasses.asdict(run.config)}
    finally:
        UnsprungAdvanceInput.solve = original
        run.close()
    sources = [load_step(inputs/row["path"]) for row in captured]
    # 冻结文件只来自本进程实际输入；必须先证明重放不改变任何数值字段。
    for source,row in zip(sources,captured):
        assert digest(source.solve()) == row["reference_sha256"]

    new_functions = {name:value for name,value in vars(current).items() if isinstance(value,types.BuiltinFunctionType)}
    old_functions = {name:vars(old)[name] for name in new_functions if name in vars(old)}
    new_only = new_functions.keys()-old_functions.keys()
    assert new_only == {"box_axis_supports","radial_box_bounds"}
    names_by_identity = {id(value):name for name,value in new_functions.items()}
    bindings = [(current,name,value,name) for name,value in new_functions.items()]
    for module in list(sys.modules.values()):
        if not isinstance(module,types.ModuleType):
            continue
        path = vars(module).get("__file__")
        if path is None or Path(path).resolve().parent != ROOT/"src" or module is current:
            continue
        for attribute,value in list(vars(module).items()):
            if id(value) in names_by_identity:
                bindings.append((module,attribute,value,names_by_identity[id(value)]))
    guard_calls = []

    def unused_box(*values):
        guard_calls.append(True)
        raise AssertionError("该平面制动诊断不应执行新增Box入口")

    def select(label):
        for module,attribute,_original,name in bindings:
            value = unused_box if name in new_only else (old_functions[name] if label=="A" else new_functions[name])
            setattr(module,attribute,value)

    def batch():
        values,timings = [],[]
        start,cpu = time.perf_counter(),time.process_time()
        for source in sources:
            before = time.perf_counter()
            values.append(source.solve())
            timings.append(time.perf_counter()-before)
        elapsed,used = time.perf_counter()-start,time.process_time()-cpu
        hashes = [digest(value) for value in values]
        assert hashes == [row["reference_sha256"] for row in captured]
        return {"wall_seconds":elapsed,"cpu_seconds":used,"substep_seconds":timings,
                "p95_seconds":float(np.percentile(timings,95)),"p99_seconds":float(np.percentile(timings,99)),
                "complete_numeric_fields_exact":True}

    rows = []
    try:
        for label in ("A","B"):
            select(label)
            batch()
        for index,label in enumerate("ABBABAAB"):
            select(label)
            row = {"index":index,"label":label,**batch()}
            rows.append(row)
            print(label,round(row["wall_seconds"],6),flush=True)
    finally:
        for module,attribute,value,_name in bindings:
            setattr(module,attribute,value)
    assert not guard_calls
    measured = {label:{metric:float(np.mean([row[metric] for row in rows if row["label"]==label]))
                       for metric in ("wall_seconds","cpu_seconds")} for label in ("A","B")}
    result = {"scope":"同一进程48个真实冻结共同解；未计世界推进/快照/UI，不作为整步性能Gate",
              "experiment":experiment,"numpy":np.__version__,
              "runtime":runtime_fingerprint(),"native":{label:{"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
              for label,path in (("A",old_path),("B",Path(current.__file__).resolve()))},
              "captured":captured,"rows":rows,"measured":measured,"binding_count":len(bindings),
              "bindings":[{"module":module.__name__,"attribute":attribute,"native_name":name,"new_only_guard":name in new_only}
                          for module,attribute,_value,name in bindings],
              "new_box_paths_executed":len(guard_calls),"wall_reduction_percent":100*(1-measured["B"]["wall_seconds"]/measured["A"]["wall_seconds"]),
              "complete_numeric_fields_exact":True,"order":"ABBABAAB","warmup_batches":2}
    (args.output/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"measured":measured,"wall_reduction_percent":result["wall_reduction_percent"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-extension",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    main(parser.parse_args())
