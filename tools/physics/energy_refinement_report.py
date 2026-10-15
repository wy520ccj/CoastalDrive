"""同源/同SDK/同硬件的原始能量与实际完成拍细化报告；不调整物理或验收阈值。"""

import argparse
import csv
import hashlib
import json
import math
from itertools import pairwise
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"logs/SIM-UNSPRUNG-01"
TERMS=("frozen_energy_residual","native_kinetic_defect","elastic_geometry_defect","geometry_work_defect",
       "numerical_guide_work","body_gyro_work","suspension_geometry_work")
OBSERVATIONS=("cg_speed","sprung_az","hub_az_fl","travel_fl","load_fl","yaw")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    folders={2:BASE/"damper-curve-energy-r1",4:BASE/"energy-refinement-4-r1",8:BASE/"energy-refinement-8-r1"}
    record_folders={2:BASE/"damper-curve-AB-r1/B",4:folders[4]/"record",8:folders[8]/"record"}
    reports={n:read(folder/"result.json") for n,folder in folders.items()}
    reference=reports[2]
    inputs={}
    results=[]
    records={}
    for n,report in reports.items():
        assert report["source"]==reference["source"] and report["runtime"]==reference["runtime"]
        assert report["summary"]["options"]==reference["summary"]["options"]
        assert report["summary"]["reason"]=="time_limit"
        assert {key:value for key,value in report["config"].items() if key!="tire_substeps"}=={
            key:value for key,value in reference["config"].items() if key!="tire_substeps"}
        assert report["config"]["tire_substeps"]==n
        records[n]=read(record_folders[n]/"experiment.json")
        record=records[n]
        assert record["source_start"]==record["source_end"]==report["source"]
        assert record["runtime_start"]==record["runtime_end"]==report["runtime"]
        assert record["vehicle_config"]==report["config"]
        assert record["commands"]==read(record_folders[2]/"experiment.json")["commands"]
        for name in ("result.json","substeps.csv"):
            path=folders[n]/name
            inputs[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
        with (folders[n]/"substeps.csv").open(encoding="utf-8",newline="") as stream:
            rows=[{key:float(value) for key,value in row.items()} for row in csv.DictReader(stream)]
        assert len(rows)==288*n
        closure=max(abs(row["actual_energy_residual"]-sum(row[key] for key in TERMS)) for row in rows)
        assert closure<1e-8
        item={"substeps":n,"dt_s":1/(120*n),"mechanical_steps":len(rows),"completed_samples":len(record["samples"]),
            "initialization_ticks":record["summary"]["initialization_ticks"],
            "raw_energy_sum_J":sum(row["actual_energy_residual"] for row in rows),
            "raw_energy_abs_peak_J":max(abs(row["actual_energy_residual"]) for row in rows),
            "derived_budget_sum_J":{key:sum(row[key] for row in rows) for key in TERMS},
            "independent_budget_identity_peak_J":closure,
            "initial_observations":{key:record["samples"][0][key] for key in OBSERVATIONS},
            "ride_metrics":read(record_folders[n]/"engineering.json")["B" if n==2 else "current"]["ride"]["metrics"],
            "suspension_expansion":None}
        if n!=2:
            item["suspension_expansion"]={"sum_J":{key:sum(row[key] for row in rows) for key in
                ("spring_port_defect","damper_port_defect","rate_drift_work","rotation_leading_work","suspension_expansion_remainder","damper_material_heat")},
                "remainder_abs_peak_J":max(abs(row["suspension_expansion_remainder"]) for row in rows),
                "heat_identity_abs_peak_J":max(abs(row["damper_material_heat_identity_error"]) for row in rows),
                "heat_min_J":min(row["damper_material_heat"] for row in rows)}
            assert item["suspension_expansion"]["heat_identity_abs_peak_J"]<1e-10
        results.append(item)
    differences={}
    for key in OBSERVATIONS:
        lengths={len(record["samples"]) for record in records.values()}
        assert lengths=={289}
        indices=[i for i in range(289) if all(record["samples"][i][key] is not None for record in records.values())]
        assert indices
        for i in indices:
            assert max(abs(record["samples"][i]["time"]-records[2]["samples"][i]["time"]) for record in records.values())<1e-12
        arrays={n:np.array([record["samples"][i][key] for i in indices]) for n,record in records.items()}
        first=float(np.sqrt(np.mean((arrays[2]-arrays[4])**2)))
        second=float(np.sqrt(np.mean((arrays[4]-arrays[8])**2)))
        differences[key]={"rms_2_to_4":first,"rms_4_to_8":second,
                          "common_samples":len(indices),"excluded_missing_samples":289-len(indices),
                          "empirical_order":math.log2(first/second) if first>0. and second>0. else None}
    for key in ("raw_energy_sum_J","raw_energy_abs_peak_J"):
        for previous,current in pairwise(results):
            current.setdefault("orders",{})[key]=math.log2(abs(previous[key]/current[key]))
    result={"results":results,"trajectory_differences":differences,"inputs_sha256":inputs,
        "source":reference["source"],"runtime":reference["runtime"],
        "gate_status":"not_assessed; original residuals retained; numerical term identities are not physical closure",
        "initialization_scope":"same real settling protocol; initial settled states may differ with discretization, explicitly listed",
        "reused":{2:"existing complete 576-step energy run and matching B record; no rerun"},
        "expansion_scope":"first two Taylor coefficients along frozen end-velocity path; no fitting to total energy residual"}
    (output/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    with (output/"budget.csv").open("w",encoding="utf-8-sig",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=("substeps","dt_s","raw_sum_J","raw_peak_J",*TERMS))
        writer.writeheader()
        for row in results:writer.writerow({"substeps":row["substeps"],"dt_s":row["dt_s"],
            "raw_sum_J":row["raw_energy_sum_J"],"raw_peak_J":row["raw_energy_abs_peak_J"],**row["derived_budget_sum_J"]})
    print(json.dumps({"energy_sum_J":[row["raw_energy_sum_J"] for row in results],
        "orders":[row.get("orders") for row in results],"gate_status":result["gate_status"]}))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    check(parser.parse_args().output.resolve())
