"""保存当前只读动量诊断、独立原生精度模块及隔离运行时准备证据。"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from panda3d import bullet, core

from lab_records import model_fingerprint


def archive():
    output = ROOT/"docs/evidence/SIM-UNSPRUNG-01/momentum-precision"
    output.mkdir(parents=True,exist_ok=True)
    source = model_fingerprint()
    results = {}
    folders = []
    for n in (2,4,8):
        folder = ROOT/f"logs/SIM-UNSPRUNG-01/momentum-energy-manual-{n}-r1"
        data = json.loads((folder/"result.json").read_text(encoding="utf-8"))
        assert data["source"]==source
        results[str(n)] = {k:data[k] for k in ("summary","max_abs","sum")}
        folders.append(folder)
    folders.append(ROOT/"logs/SIM-UNSPRUNG-01/bullet-precision-probe-r1")
    runtime = {"panda_version":core.PandaSystem.getVersionString(),"bullet_reported_version":bullet.getBulletVersion(),
               "math_scalar_bits":32 if core.LPoint3==core.LPoint3f else 64}
    assert core.LPoint3 in (core.LPoint3f,core.LPoint3d)
    runtime_files = [Path(core.__file__),Path(bullet.__file__),*Path(core.__file__).parent.glob("*.dll")]
    runtime["files"] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime_files}
    (output/"runtime-fingerprint.json").write_text(json.dumps(runtime,indent=2),encoding="utf-8")
    (output/"comparison.json").write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
    (output/"source.json").write_text(json.dumps(source,indent=2),encoding="utf-8")
    files = [p for folder in folders for p in folder.rglob("*") if p.is_file()]
    files += [p for p in (ROOT/"logs/SIM-UNSPRUNG-01").glob("*.log") if p.name.startswith(("bullet-precision-build-","sim-double-prepare-"))]
    files += [ROOT/"build/sim-double-runtime/prepared.json",ROOT/"build/bullet-precision-proof/upstream-r1.json",
              ROOT/"build/bullet-precision-proof/upstream-r2.json",ROOT/"build/sim-double-runtime/prepared-r2.json"]
    files += [ROOT/"tools/physics"/name for name in ("lab_momentum_energy_check.py","bullet_precision_probe.cpp",
              "build_bullet_precision_probe.py","run_bullet_precision_probe.py","prepare_sim_double_runtime.py",Path(__file__).name)]
    with zipfile.ZipFile(output/"raw-evidence.zip","w",zipfile.ZIP_DEFLATED) as package:
        for path in files:package.write(path,path.relative_to(ROOT))
    with zipfile.ZipFile(output/"executed-model.zip","w",zipfile.ZIP_DEFLATED) as package:
        for relative,digest in source.items():
            path=ROOT/relative
            assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
            package.write(path,relative)
    upstream = ROOT/"build/bullet-precision-proof/source"
    descriptor = json.loads((ROOT/"build/bullet-precision-proof/upstream.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(output/"probe-upstream.zip","w",zipfile.ZIP_DEFLATED) as package:
        for relative,digest in descriptor["files"].items():
            path = upstream/relative
            assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
            package.write(path,relative)
    manifest = {"baseline":"d0215ad","files":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        "archives":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.zip")},
        "production_code_changed":False,"shared_environment_changed":False,"double_runtime_integrated":False,
        "official_dependencies_prepared":True,"reuse":"d0215ad 85-test T1, seeds, UI; production source and assets unchanged"}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"files":len(files),"model_files":len(source),"runtime":{k:v for k,v in runtime.items() if k!="files"}}))


if __name__=="__main__":archive()
