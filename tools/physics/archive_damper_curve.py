"""归档非线性减振器的原始台架/原生整车/末本构/历史来源与F1。"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from suspension_bench import validate_metadata


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def archive():
    output=ROOT/"docs/evidence/SIM-UNSPRUNG-01/damper-curve"
    output.mkdir(parents=True,exist_ok=True)
    logs=ROOT/"logs/SIM-UNSPRUNG-01"
    source,runtime=model_fingerprint(),runtime_fingerprint()
    ab=read(logs/"damper-curve-AB-r1/result.json")
    energy=read(logs/"damper-curve-energy-r1/result.json")
    assert energy["source"]==source and energy["runtime"]==runtime
    for label in ("A","B"):
        record=read(logs/f"damper-curve-AB-r1/{label}/experiment.json")
        assert record["source_start"]==record["source_end"]==source
        assert record["runtime_start"]==record["runtime_end"]==runtime
        validate_metadata(record["parameter_metadata"])
    assert ab["results"][1]["recalculate_exact"] is True
    assert energy["config"]==read(logs/"damper-curve-AB-r1/B/vehicle.json")
    assert all(energy["summary"][key]==ab["results"][1]["summary"][key] for key in energy["summary"] if key!="compute_seconds")
    legacy=[]
    for folder,member,metadata_key in (
        ("component-bench","logs/SIM-UNSPRUNG-01/component-bench-AB-r2/accepted/candidate-vehicle.json","metadata"),
        ("preload","logs/SIM-UNSPRUNG-01/preload-AB-r1/B/experiment.json","parameter_metadata"),
        ("motion-curve","logs/SIM-UNSPRUNG-01/motion-curve-AB-r1/B/experiment.json","parameter_metadata")):
        with zipfile.ZipFile(ROOT/f"docs/evidence/SIM-UNSPRUNG-01/{folder}/raw-evidence.zip") as package:
            value=json.loads(package.read(member))
        metadata=value[metadata_key]
        validate_metadata(metadata)
        legacy.append(metadata["suspension_calibration"]["schema"])
    for name,value in (("source",source),("runtime",runtime),("AB",ab),("energy",energy),("legacy-recomputed",legacy)):
        (output/(name+".json")).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    (output/"example-synthetic.json").write_bytes((logs/"damper-curve-AB-r1/input.json").read_bytes())
    files=[file for folder in logs.iterdir() if folder.is_dir() and folder.name.startswith("damper-curve-")
           for file in folder.rglob("*") if file.is_file()]
    files += [ROOT/"tests"/name for name in ("test_suspension_damper.py","damper_bench_reference.py")]
    files += [ROOT/"tools/physics"/name for name in ("damper_curve_check.py","lab_energy_check.py",Path(__file__).name)]
    files += [ROOT/"tools/damper_curve_ui_check.py",ROOT/"tools/design/plot_damper_curve.py"]
    with zipfile.ZipFile(output/"raw-evidence.zip","w",zipfile.ZIP_DEFLATED) as package:
        for file in files:package.write(file,file.relative_to(ROOT))
    with zipfile.ZipFile(output/"executed-model.zip","w",zipfile.ZIP_DEFLATED) as package:
        for relative,digest in source.items():
            file=ROOT/relative
            assert hashlib.sha256(file.read_bytes()).hexdigest()==digest
            package.write(file,relative)
        for directory in ("src/ui","assets/game/ui/formulas"):
            for file in (ROOT/directory).rglob("*"):
                if file.is_file() and "__pycache__" not in file.parts:package.write(file,file.relative_to(ROOT))
    manifest={"baseline":"d8b892e","files":{str(file.relative_to(ROOT)):hashlib.sha256(file.read_bytes()).hexdigest() for file in files},
        "archives":{file.name:hashlib.sha256(file.read_bytes()).hexdigest() for file in output.glob("*.zip")},
        "figures":{file.name:hashlib.sha256(file.read_bytes()).hexdigest() for file in output.iterdir() if file.suffix in (".png",".svg")},
        "candidate_full_recalculate_exact":True,"source_runtime_checked":True,"legacy_reports_recomputed":legacy,
        "scope":"synthetic memoryless passive damper; actual native world; hysteresis, temperature, full K&C and real calibration open"}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"files":len(files),"source_files":len(source),"legacy_reports_recomputed":legacy,
                      "full_candidate_recalculate_exact":True}))


if __name__=="__main__":archive()
