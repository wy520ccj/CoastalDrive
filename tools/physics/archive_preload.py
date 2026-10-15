"""归档安装预压实际输入/世界/静载/能量/F1；不覆盖原始执行记录。"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from driving_modes import DrivingMode
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import config_from_document


def archive():
    output=ROOT/"docs/evidence/SIM-UNSPRUNG-01/preload"
    output.mkdir(parents=True,exist_ok=True)
    source,runtime=model_fingerprint(),runtime_fingerprint()
    logs=ROOT/"logs/SIM-UNSPRUNG-01"
    ab=json.loads((logs/"preload-AB-r1/result.json").read_text(encoding="utf-8"))
    release=json.loads((logs/"preload-release-r2/result.json").read_text(encoding="utf-8"))
    energy=json.loads((logs/"preload-energy-r1/result.json").read_text(encoding="utf-8"))
    assert release["source"]==energy["source"]==source
    assert release["runtime"]==energy["runtime"]==runtime
    for label in ("A","B"):
        record=json.loads((logs/f"preload-AB-r1/{label}/experiment.json").read_text(encoding="utf-8"))
        assert record["source_start"]==record["source_end"]==source
        assert record["runtime_start"]==record["runtime_end"]==runtime
    assert ab["results"][1]["recalculate_exact"] is True
    assert all(energy["summary"][key]==ab["results"][1]["summary"][key] for key in energy["summary"] if key!="compute_seconds")
    # 该次旧工具config记录输入而非Lab配置，保留原文件；用真实保存选项/同工况B配置核对覆盖。
    options=energy["summary"]["options"]
    assert options["cg_height"] is None and options["tire_reference_load"] is None
    requested=config_from_document(energy["config"],REFERENCE_DESIGN)
    effective=DrivingMode.SIMULATION.configured_vehicle(options["abs_enabled"],esc_enabled=options["esc_enabled"],base_config=requested)
    actual=json.loads((logs/"preload-AB-r1/B/vehicle.json").read_text(encoding="utf-8"))
    from dataclasses import asdict
    assert json.loads(json.dumps(asdict(effective)))==actual
    energy_context={"definition":"raw energy result.config is the requested input; effective config reconstructed from execution-matched DrivingMode and recorded actual Lab options, checked against actual B record; original file preserved",
        "requested_config":energy["config"],"effective_config":actual,"actual_options":options,
        "all_summary_fields_except_wall_compute_equal_to_B":True,"requested_esc":energy["config"]["stability"]["esc_enabled"],
        "effective_esc":actual["stability"]["esc_enabled"]}
    for name,value in (("source",source),("runtime",runtime),("AB",ab),("release",release),("energy-context",energy_context)):
        (output/(name+".json")).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")
    (output/"example-synthetic.json").write_bytes((logs/"preload-AB-r1/B-input.json").read_bytes())
    files=[file for folder in logs.iterdir() if folder.is_dir() and folder.name.startswith("preload-")
           for file in folder.rglob("*") if file.is_file()]
    files += [ROOT/"tests"/name for name in ("test_suspension_preload.py","suspension_preload_reference.py","test_suspension_bench.py")]
    files += [ROOT/"tools/physics"/name for name in ("preload_check.py","preload_release_check.py","lab_energy_check.py",Path(__file__).name)]
    files += [ROOT/"tools/preload_ui_check.py",ROOT/"tools/design/plot_preload_release.py"]
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
    manifest={"baseline":"f839933","files":{str(file.relative_to(ROOT)):hashlib.sha256(file.read_bytes()).hexdigest() for file in files},
        "archives":{file.name:hashlib.sha256(file.read_bytes()).hexdigest() for file in output.glob("*.zip")},
        "figures":{file.name:hashlib.sha256(file.read_bytes()).hexdigest() for file in output.iterdir() if file.suffix in (".png",".svg")},
        "source_runtime_start_end_checked":True,"candidate_full_recalculate_exact":True,
        "energy_raw_preserved":True,"default_changed":False,"scope":"synthetic installation test; actual native Simulation; no real-vehicle calibration claim"}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({"files":len(files),"source_files":len(source),"recalculate_exact":True}))


if __name__=="__main__":archive()
