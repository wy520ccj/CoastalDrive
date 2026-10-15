"""归档实际末悬架本构、数值功和既有基线峰样本；不重跑旧基线。"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from unsprung_contact import suspension_potential
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import config_from_document


def archive():
    output = ROOT/"docs/evidence/SIM-UNSPRUNG-01/finite-suspension"
    output.mkdir(parents=True,exist_ok=True)
    source,runtime = model_fingerprint(),runtime_fingerprint()
    result = {"baseline":"c058cc4","baseline_peak_scope":"one previously saved maximum elastic-geometry sample per substep, not full-run force maxima","runs":{},"baseline_peaks":{}}
    with zipfile.ZipFile(ROOT/"docs/evidence/SIM-UNSPRUNG-01/double-runtime/raw-evidence.zip") as baseline:
        for n in (2,4,8):
            current = json.loads((ROOT/f"logs/SIM-UNSPRUNG-01/finite-suspension-ride-{n}-r1/result.json").read_text(encoding="utf-8"))
            assert current["source"]==source and current["runtime"]==runtime
            old = json.loads(baseline.read(f"logs/SIM-UNSPRUNG-01/sim-double-ride-{n}-r1/result.json"))
            assert current["config"]==old["config"]
            config = config_from_document(old["config"],REFERENCE_DESIGN)
            result["runs"][str(n)] = {key:current[key] for key in ("summary","sum","max_abs")}
            peak = json.loads(baseline.read(f"logs/SIM-UNSPRUNG-01/sim-double-ride-{n}-r1/peak-input.json"))
            state = peak["actual_after"]
            z = np.asarray(peak["predicted_velocity"])
            arms = np.asarray(state["centers"])-state["position"]
            guide = np.asarray(state["rotation"])[:,2]
            actual_u = (np.asarray(state["wheel_velocity"])-state["velocity"]-np.cross(state["angular"],arms))@guide
            def force(q,u,c=config):
                return suspension_potential(q,c)[1]+np.where(u>=0,c.suspension_compression_damping,c.suspension_extension_damping)*u
            error = force(peak["predicted_compression"],z[6:10])-force(state["compression"],actual_u)
            result["baseline_peaks"][str(n)] = {"force_error_N":error.tolist(),"max_abs_force_error_N":float(np.max(np.abs(error))),"input":peak}
    record = json.loads((ROOT/"logs/SIM-UNSPRUNG-01/finite-suspension-record-r1/mass-40/experiment.json").read_text(encoding="utf-8"))
    assert record["source_start"]==record["source_end"]==source
    assert record["runtime_start"]==record["runtime_end"]==runtime
    result["braking"] = json.loads((ROOT/"logs/SIM-UNSPRUNG-01/finite-suspension-record-r1/result.json").read_text(encoding="utf-8"))
    for name,value in (("comparison",result),("source",source),("runtime",runtime)):
        (output/(name+".json")).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding="utf-8")
    folders = [p for p in (ROOT/"logs/SIM-UNSPRUNG-01").iterdir() if p.is_dir() and p.name.startswith("finite-suspension-")]
    files = [file for folder in folders for file in folder.rglob("*") if file.is_file()]
    files += [ROOT/"tools/physics"/name for name in (Path(__file__).name,"lab_energy_check.py","lab_ride_braking_check.py")]
    files += [ROOT/"tools/lab_radial_formula_check.py"]
    with zipfile.ZipFile(output/"raw-evidence.zip","w",zipfile.ZIP_DEFLATED) as package:
        for file in files:package.write(file,file.relative_to(ROOT))
    with zipfile.ZipFile(output/"executed-model.zip","w",zipfile.ZIP_DEFLATED) as package:
        for relative,digest in source.items():
            file = ROOT/relative
            assert hashlib.sha256(file.read_bytes()).hexdigest()==digest
            package.write(file,relative)
        for directory in ("src/ui","assets/game/ui/formulas"):
            for file in (ROOT/directory).rglob("*"):
                if file.is_file() and "__pycache__" not in file.parts:package.write(file,file.relative_to(ROOT))
    manifest = {"baseline":"c058cc4","files":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                "archives":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.zip")},
                "record_source_runtime_start_end_equal":True,"game_checkout_changed":False,"default_changed":False}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"files":len(files),"model_files":len(source),"full_record_recalculate_exact":result["braking"][0]["recalculate_exact"]}))


if __name__=="__main__":archive()
