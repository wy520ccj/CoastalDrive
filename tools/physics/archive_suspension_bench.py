"""归档实际部件换算、整车A/B、复算及渲染；核对执行源码和运行时。"""

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src"))

from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint


def archive():
    output = ROOT/"docs/evidence/SIM-UNSPRUNG-01/component-bench"
    output.mkdir(parents=True, exist_ok=True)
    source, runtime = model_fingerprint(), runtime_fingerprint()
    run_path = ROOT/"logs/SIM-UNSPRUNG-01/component-bench-AB-r2"
    result = json.loads((run_path/"result.json").read_text(encoding="utf-8"))
    for label in ("A", "B"):
        record = json.loads((run_path/label/"experiment.json").read_text(encoding="utf-8"))
        assert record["source_start"] == record["source_end"] == source
        assert record["runtime_start"] == record["runtime_end"] == runtime
    assert result["results"][1]["recalculate_exact"] is True
    for name, value in (("source", source), ("runtime", runtime), ("result", result)):
        (output/(name+".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    (output/"example-synthetic.json").write_bytes((run_path/"good-input.json").read_bytes())
    files = [file for folder in (ROOT/"logs/SIM-UNSPRUNG-01").iterdir()
             if folder.is_dir() and folder.name.startswith("component-bench-")
             for file in folder.rglob("*") if file.is_file()]
    files += [ROOT/"tests"/name for name in ("suspension_bench_reference.py", "test_suspension_bench.py", "test_unsprung_dry_ports.py",
                                           "data/unsprung-soft-spring-init.pkl")]
    files += [ROOT/"tools/physics"/name for name in ("fit_suspension_bench.py", "suspension_bench_check.py", "suspension_bench_failure.py", "suspension_bench_port_check.py", Path(__file__).name)]
    files += [ROOT/"tools/suspension_bench_ui_check.py"]
    with zipfile.ZipFile(output/"raw-evidence.zip", "w", zipfile.ZIP_DEFLATED) as package:
        for file in files: package.write(file, file.relative_to(ROOT))
    with zipfile.ZipFile(output/"executed-model.zip", "w", zipfile.ZIP_DEFLATED) as package:
        for relative, digest in source.items():
            file = ROOT/relative
            assert hashlib.sha256(file.read_bytes()).hexdigest() == digest
            package.write(file, relative)
        for directory in ("src/ui", "assets/game/ui/formulas"):
            for file in (ROOT/directory).rglob("*"):
                if file.is_file() and "__pycache__" not in file.parts: package.write(file, file.relative_to(ROOT))
    manifest = {"baseline": "dd1c9bf", "files": {str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest() for file in files},
                "archives": {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in output.glob("*.zip")},
                "record_source_runtime_start_end_equal": True, "full_candidate_recalculate_exact": True,
                "scope": "synthetic component fit and complete native-world Simulation A/B; NOT real-vehicle calibration"}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"files": len(files), "model_files": len(source), "recalculate_exact": True}))


if __name__ == "__main__": archive()
