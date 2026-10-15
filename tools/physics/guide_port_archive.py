"""归档实际推进节点的已执行源和证据；后续数学展示修订单独保存。"""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from lab_records import model_fingerprint


def archive():
    output = ROOT/"docs/evidence/SIM-UNSPRUNG-01/guide-ports"
    output.mkdir(parents=True,exist_ok=True)
    source = model_fingerprint()
    results = {}
    for name in ("guide-port-ride-2-r1","guide-port-ride-4-r1","guide-port-ride-8-r1","guide-port-manual-2-r2"):
        value = json.loads((ROOT/"logs/SIM-UNSPRUNG-01"/name/"result.json").read_text(encoding="utf-8"))
        assert value["source"]==source
        results[name] = {"steps":value["summary"]["ticks"]*value["substeps"],
            "sum":value["sum"],"max_abs":value["max_abs"],"summary":value["summary"]}
    record = ROOT/"logs/SIM-UNSPRUNG-01/guide-port-record-r1/mass-40/experiment.json"
    metadata = json.loads(record.read_text(encoding="utf-8"))
    assert metadata["source_start"]==metadata["source_end"]==source
    for relative,digest in source.items():
        assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest
    results["ride_braking_record"] = json.loads((record.parents[1]/"result.json").read_text(encoding="utf-8"))
    results["baseline"] = {str(n):json.loads((ROOT/f"logs/SIM-UNSPRUNG-01/lab-origin-edge-energy-{n}-r1/result.json").read_text(encoding="utf-8"))
                           for n in (2,4,8)}
    (output/"comparison.json").write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
    (output/"source.json").write_text(json.dumps(source,indent=2),encoding="utf-8")
    assets = [p for folder in (ROOT/"src/ui",ROOT/"assets/game/ui/formulas") for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    with zipfile.ZipFile(output/"executed-model.zip","w",zipfile.ZIP_DEFLATED) as package:
        for path in [*(ROOT/relative for relative in source),*assets]:package.write(path,path.relative_to(ROOT))
    folders = [p for p in (ROOT/"logs/SIM-UNSPRUNG-01").iterdir()
               if p.is_dir() and (p.name.startswith("guide-port-") or p.name.startswith("guide-momentum-"))]
    files = [p for folder in folders for p in folder.rglob("*") if p.is_file()]
    files += [ROOT/"tools/physics/guide_port_archive.py",ROOT/"tools/physics/unsprung_guide_momentum_check.py"]
    with zipfile.ZipFile(output/"raw-evidence.zip","w",zipfile.ZIP_DEFLATED) as package:
        for path in files:package.write(path,path.relative_to(ROOT))
    manifest = {"baseline":"54c913e","files":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                "archives":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.zip")},
                "source_current_at_archive":True,"record_source_start_end_equal":True,
                "note":"Actual physics and full record source archived before subsequent presentation-only formula revision."}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"files":len(files),"model_files":len(source),"records_recalculated":1}))


def presentation():
    """只追加展示版，不覆写已运行的源摘要或完整记录。"""
    output = ROOT/"docs/evidence/SIM-UNSPRUNG-01/guide-ports"
    saved = json.loads((output/"source.json").read_text(encoding="utf-8"))
    current = model_fingerprint()
    changes = sorted(k for k in saved.keys()|current.keys() if saved.get(k)!=current.get(k))
    assert changes==[str(Path("src/parameter_formulas.py"))]
    files = [ROOT/"src/parameter_formulas.py",ROOT/"tools/lab_radial_formula_check.py"]
    files += [p for p in (ROOT/"assets/game/ui/formulas").iterdir() if p.is_file()]
    files += [p for suffix in ("T0","720","1080") for p in
              (ROOT/f"logs/SIM-UNSPRUNG-01/guide-port-formulas-{suffix}-r1").rglob("*") if p.is_file()]
    with zipfile.ZipFile(output/"final-formulas.zip","w",zipfile.ZIP_DEFLATED) as package:
        for path in files:package.write(path,path.relative_to(ROOT))
    manifest = json.loads((output/"manifest.json").read_text(encoding="utf-8"))
    manifest["presentation_source_changes"] = changes
    manifest["final_formula_sources"] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest["archives"]["final-formulas.zip"] = hashlib.sha256((output/"final-formulas.zip").read_bytes()).hexdigest()
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"presentation_files":len(files),"changed_model_fields":changes,"physics_bytes_unchanged":True}))


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--presentation",action="store_true")
    if parser.parse_args().presentation:presentation()
    else:archive()
