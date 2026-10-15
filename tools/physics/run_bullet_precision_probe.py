"""对照同源Bullet的32/64位实际世界；复用既有Panda恒力证据，不改生产环境。"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT/"build/bullet-precision-proof"
sys.path.insert(0,str(BUILD/"modules"))

import bullet_precision_double
import bullet_precision_float


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    single,double = bullet_precision_float.check(),bullet_precision_double.check()
    previous = json.loads((ROOT/"logs/SIM-UNSPRUNG-01/native-force-rounding-r1/result.json").read_text(encoding="utf-8"))
    assert len(single)==len(double)==len(previous)==18
    assert all(row["scalar_bytes"]==4 for row in single) and all(row["scalar_bytes"]==8 for row in double)
    matched = all(a["velocity_mps"]==b["velocity_mps"] for a,b in zip(single,previous))
    differences = [a["velocity_mps"]-b["velocity_mps"] for a,b in zip(single,previous)]
    for a,b in zip(single,double):
        assert (a["force_N"],a["substeps"],a["mode"])==(b["force_N"],b["substeps"],b["mode"])
    assert max(abs(row["velocity_error"]) for row in double)<1e-11
    result = {"source_tag":"Bullet official 2.84","scope":"Independent constant-force world; not production vehicle precision or completed integration",
        "single":single,"double":double,"previous_panda_single_bit_exact":matched,"previous_velocity_differences":differences,
        "double_velocity_error_max":max(abs(row["velocity_error"]) for row in double),
        "single_velocity_error_max":max(abs(row["velocity_error"]) for row in single)}
    files = [ROOT/"tools/physics/bullet_precision_probe.cpp",ROOT/"tools/physics/build_bullet_precision_probe.py",
             Path(__file__),BUILD/"upstream.json",*(BUILD/"modules").glob("*.pyd")]
    result["executed_files"] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    for path in files:(output/path.name).write_bytes(path.read_bytes())
    (output/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("previous_panda_single_bit_exact","double_velocity_error_max","single_velocity_error_max")}))


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    check(parser.parse_args().output.resolve())
