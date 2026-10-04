"""独立原型保留既有端口/共同机械台架的完整断言。"""
import hashlib,json,runpy,sys
from pathlib import Path
import pytest
E=Path(__file__).resolve().parent
experiment=runpy.run_path(str(E/"cross-wheel-reuse-experiment.py"))
before=experiment["source"]()
experiment["install"]()
args=["-q","tests/test_transmission_ports.py","tests/test_tire_drivetrain.py","--junitxml=docs/evidence/PHYS-DRIVE-01/cross-wheel-reuse-tests-r8.junit.xml"]
code=pytest.main(args)
after=experiment["source"]()
(E/"cross-wheel-reuse-tests-r8.json").write_text(json.dumps({"scope":"isolated proposed function; production unchanged; not full T0/T1/T2","pytest_exit_code":int(code),"source_before":before,"source_after":after,"source_stable":before==after,"pytest_args":args,"runner_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"experiment_sha256":hashlib.sha256((E/"cross-wheel-reuse-experiment.py").read_bytes()).hexdigest()},indent=2)+"\n",encoding="utf-8")
raise SystemExit(code)
