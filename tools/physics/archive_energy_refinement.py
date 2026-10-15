"""归档同源细化与独立悬架功展开；复用已归档物理模型，不重写旧节点。"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint


def archive():
    output=ROOT/"docs/evidence/SIM-UNSPRUNG-01/energy-refinement"
    output.mkdir(parents=True,exist_ok=True)
    logs=ROOT/"logs/SIM-UNSPRUNG-01"
    report=json.loads((logs/"energy-refinement-report-r2/result.json").read_text(encoding="utf-8"))
    source,runtime=model_fingerprint(),runtime_fingerprint()
    assert report["source"]==source and report["runtime"]==runtime
    (output/"report.json").write_bytes((logs/"energy-refinement-report-r2/result.json").read_bytes())
    (output/"budget.csv").write_bytes((logs/"energy-refinement-report-r2/budget.csv").read_bytes())
    model=ROOT/"docs/evidence/SIM-UNSPRUNG-01/damper-curve/executed-model.zip"
    with zipfile.ZipFile(model) as package:
        for relative,digest in source.items():
            assert hashlib.sha256(package.read(Path(relative).as_posix())).hexdigest()==digest
    folders=[folder for folder in logs.iterdir() if folder.is_dir() and folder.name.startswith("energy-refinement-")]
    folders += [logs/"damper-curve-energy-r1",logs/"damper-curve-AB-r1/B"]
    files=[file for folder in folders for file in folder.rglob("*") if file.is_file()]
    files += [ROOT/"tools/physics"/name for name in ("lab_energy_check.py","suspension_work.py","energy_refinement_report.py",Path(__file__).name)]
    files += [ROOT/"tests/test_suspension_work.py",ROOT/"tools/design/plot_energy_refinement.py"]
    with zipfile.ZipFile(output/"raw-evidence.zip","w",zipfile.ZIP_DEFLATED) as package:
        for file in files:package.write(file,file.relative_to(ROOT))
    manifest={"baseline":"c967676","files":{str(file.relative_to(ROOT)):hashlib.sha256(file.read_bytes()).hexdigest() for file in files},
        "archives":{"raw-evidence.zip":hashlib.sha256((output/"raw-evidence.zip").read_bytes()).hexdigest()},
        "figures":{file.name:hashlib.sha256(file.read_bytes()).hexdigest() for file in output.iterdir() if file.suffix in (".png",".svg")},
        "reused_model":{"path":str(model.relative_to(ROOT)),"sha256":hashlib.sha256(model.read_bytes()).hexdigest(),
                        "all_current_source_bytes_match":True},
        "production_changed":False,"reused_2_substeps":True,"new_real_substeps":[4,8],
        "scope":"numerical integration audit of one fixed manoeuvre; no energy gate relaxation or whole-stage pass"}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"files":len(files),"reused_model_files":len(source),"production_changed":False}))


if __name__=="__main__":archive()
