"""本进程跨轮复用完整候选，逐字节核对r7原生证据；生产源冻结。"""
import gzip,hashlib,json,runpy,sys
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=E.parents[2]
experiment=runpy.run_path(str(E/"cross-wheel-reuse-experiment.py"))
before=experiment["source"]()
experiment["install"]()
probe=runpy.run_path(str(ROOT/"tools/physics/drivetrain_probe.py"))
receipt={"status":"running","scope":"isolated prototype against frozen r7 traces; not production/full T1/T2/performance gate","source_before":before,"experiment_sha256":hashlib.sha256((E/"cross-wheel-reuse-experiment.py").read_bytes()).hexdigest(),"runner_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"cases":[]}
target=E/"cross-wheel-reuse-native-r8.json"
def save():target.write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
save()
completed=False
try:
 for baseline_name,candidate_name,seconds,extra in (
  ("native-mode-control-r7","cross-wheel-native-flexible-r8",6.,[]),
  ("native-rigid-control-r7","cross-wheel-native-rigid-r8",4.,["--rigid","--cases","reverse","manual-shift"]),
 ):
  output=E/candidate_name;assert not output.exists()
  sys.argv=["drivetrain_probe.py","--output",str(output),"--seconds",str(seconds),*extra]
  probe["main"]()
  baseline=E/baseline_name
  old_names=sorted(p.name for p in baseline.glob("*.jsonl.gz"));new_names=sorted(p.name for p in output.glob("*.jsonl.gz"))
  assert old_names==new_names
  for name in old_names:
   with gzip.open(baseline/name,"rb") as f:old=f.read()
   with gzip.open(output/name,"rb") as f:new=f.read()
   row={"baseline":baseline_name,"candidate":candidate_name,"file":name,"ticks":old.count(b"\n"),"decompressed_bytes_equal":old==new,"baseline_sha256":hashlib.sha256(old).hexdigest(),"candidate_sha256":hashlib.sha256(new).hexdigest()}
   receipt["cases"].append(row);save();assert old==new,name
  native=json.loads((output/"summary.json").read_text(encoding="utf-8"))
  assert native["source_before"]==native["source_after"]==before
 completed=True
finally:
 receipt["status"]="completed_identical_native_traces" if completed else "failed"
 receipt["source_after"]=experiment["source"]()
 receipt["source_stable"]=receipt["source_after"]==before
 receipt["total_ticks"]=sum(c["ticks"] for c in receipt["cases"])
 save()
print(f"IDENTICAL {len(receipt['cases'])} traces / {receipt['total_ticks']} ticks",flush=True)
