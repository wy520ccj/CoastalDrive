"""保存可恢复的隔离SDK与实际执行证据，不改共享Python环境。"""

import argparse
import hashlib
import json
import sys
import zipfile
from importlib.metadata import distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint


def package(refresh=False):
    output = ROOT/"docs/evidence/SIM-UNSPRUNG-01/double-runtime"
    output.mkdir(parents=True,exist_ok=True)
    build = ROOT/"build/sim-double-runtime"
    sdk = build/"panda-source/built-double"
    source,runtime = model_fingerprint(),runtime_fingerprint()
    assert runtime["math_scalar_bits"]==64
    members = {}
    if not refresh:
        with zipfile.ZipFile(output/"runtime.zip","w",zipfile.ZIP_DEFLATED) as archive:
            for directory in ("bin","panda3d","direct","etc","models","pandac","Pmw","simplepbr","panda3d.dist-info"):
                for file in (sdk/directory).rglob("*"):
                    if not file.is_file() or "__pycache__" in file.parts or file.suffix in (".pdb",".pyc",".lib",".exp",".exe"):continue
                    if directory=="bin" and file.suffix!=".dll":continue
                    relative = file.relative_to(sdk).as_posix()
                    members[relative] = hashlib.sha256(file.read_bytes()).hexdigest()
                    archive.write(file,relative)
            archive.write(build/"panda-source/LICENSE","licenses/Panda3D-LICENSE.txt")
            archive.write(build/"bullet-source/LICENSE.txt","licenses/Bullet-LICENSE.txt")
            dist = distribution("panda3d-simplepbr")
            for entry in dist.files:
                if "license" in str(entry).lower() and dist.locate_file(entry).is_file():
                    archive.write(dist.locate_file(entry),"licenses/simplepbr-"+entry.name)
    if refresh:
        members = json.loads((output/"runtime-members.json").read_text(encoding="utf-8"))
        for relative,digest in members.items():assert hashlib.sha256((sdk/relative).read_bytes()).hexdigest()==digest
    else:(output/"runtime-members.json").write_text(json.dumps(members,indent=2),encoding="utf-8")
    (output/"runtime-fingerprint.json").write_text(json.dumps(runtime,indent=2),encoding="utf-8")
    (output/"source.json").write_text(json.dumps(source,indent=2),encoding="utf-8")
    results = {}
    for n in (2,4,8):
        value = json.loads((ROOT/f"logs/SIM-UNSPRUNG-01/sim-double-ride-{n}-r1/result.json").read_text(encoding="utf-8"))
        assert value["source"]==source and value["runtime"]==runtime
        results[str(n)] = {key:value[key] for key in ("summary","sum","max_abs")}
    (output/"convergence.json").write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
    logs = ROOT/"logs/SIM-UNSPRUNG-01"
    files = [file for directory in logs.iterdir() if directory.is_dir() and directory.name.startswith(("sim-double-","sim-normal-"))
             for file in directory.rglob("*") if file.is_file()]
    files += [file for file in logs.glob("sim-double-*.log") if file.is_file()]
    files += [build/name for name in ("double-configuration.json","render-configuration.json","makepanda-original.py")]
    files += [ROOT/"tools/physics"/name for name in ("configure_sim_double_panda.py","configure_sim_double_rendering.py",
        "build_sim_double_runtime.py","run_sim_double.py","restore_sim_double_runtime.py","vehicle_lab_double_preview.py",
        "sim_double_acceptance.py","lab_energy_check.py","lab_ride_braking_check.py","lab_momentum_energy_check.py",
        "native_force_rounding_check.py",Path(__file__).name)]
    files += [ROOT/"tools"/name for name in ("lab_ride_braking_ui_check.py","lab_radial_formula_check.py")]
    with zipfile.ZipFile(output/"raw-evidence.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for file in files:archive.write(file,file.relative_to(ROOT))
    with zipfile.ZipFile(output/"executed-model.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for relative,digest in source.items():
            file = ROOT/relative
            assert hashlib.sha256(file.read_bytes()).hexdigest()==digest
            archive.write(file,relative)
        for file in (ROOT/"src/ui").rglob("*.py"):archive.write(file,file.relative_to(ROOT))
    manifest = {"baseline":"7c65e65","runtime_target":"build/sim-double-runtime/panda-source/built-double",
        "files":{str(file.relative_to(ROOT)):hashlib.sha256(file.read_bytes()).hexdigest() for file in files},
        "archives":{file.name:hashlib.sha256(file.read_bytes()).hexdigest() for file in output.glob("*.zip")},
        "shared_environment_changed":False,"game_checkout_changed":False,"default_physics_changed":False}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"runtime_files":len(members),"runtime_zip_MiB":round((output/"runtime.zip").stat().st_size/1048576,2),"evidence_files":len(files)}))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-evidence",action="store_true")
    package(parser.parse_args().refresh_evidence)
