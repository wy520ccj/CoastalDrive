"""同初始斜率/安装/硬件：常阻尼近似与完整力速表的原生凸起A/B和复算。"""

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))
sys.path.insert(0,str(ROOT/"tools"))

from damper_bench_reference import document
from physics.unsprung_step_checkpoint import save_step

from lab_experiment import LabExperiment, LabOptions
from lab_metrics import engineering_analysis
from lab_records import LabRecord, changed_conditions, export_record, load_record, recalculate
from suspension_bench import fit_bench
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import save_vehicle_config
from vehicle_unsprung import UnsprungAdvanceInput


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    base=replace(REFERENCE_DESIGN,unsprung_enabled=True)
    raw=document()
    (output/"input.json").write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8")
    candidate,report=fit_bench(raw,base)
    assert report["passed"] and not fit_bench(document(bad_validation=True),base)[1]["passed"]
    baseline=replace(candidate,suspension_damper_curves=None)
    original=UnsprungAdvanceInput.solve
    records,results=[],[]
    for label,config in (("A",baseline),("B",candidate)):
        metadata={"suspension_calibration":report,"basis":"合成数据非实测；A为零速斜率的线性近似，B为完整被动力速表；其余硬件相同"}
        save_vehicle_config(output/(label+"-vehicle.json"),config,metadata=metadata)

        def solve(inputs,*,capture=output/(label+"-failed-step.pkl"),**kwargs):
            try:return original(inputs,**kwargs)
            except ArithmeticError:
                save_step(inputs,capture)
                raise

        UnsprungAdvanceInput.solve=solve
        run=None
        try:
            run=LabExperiment(LabOptions(maneuver="ride_bump",speed_kph=18.,duration=2.4),config=config,parameter_metadata=metadata)
            while not run.done:run.step()
            assert run.reason=="time_limit",(run.reason,run.error)
            record=LabRecord.from_run(run)
            assert record.metadata["source_start"]==record.metadata["source_end"]
            assert record.metadata["runtime_start"]==record.metadata["runtime_end"]
            export_record(record,output/label,records[0] if records else None)
            restored=load_record(output/label)
            assert restored.snapshots==record.snapshots and restored.samples==record.samples and restored.commands==record.commands
            repeated_exact=None
            if label=="B":
                repeated=recalculate(restored)
                repeated_exact=(repeated.snapshots==restored.snapshots and repeated.samples==restored.samples and repeated.commands==restored.commands)
                assert repeated_exact
            records.append(record)
            results.append({"label":label,"summary":run.summary(),"record_roundtrip_exact":True,"recalculate_exact":repeated_exact,
                "analysis":engineering_analysis(record.samples,record.snapshots,asdict(run.options),run.reason)})
            (output/"result.json").write_text(json.dumps({"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps({"label":label,"frames":len(record.samples),"recalculate_exact":repeated_exact}),flush=True)
        finally:
            UnsprungAdvanceInput.solve=original
            if run is not None:run.close()
    assert all(asdict(baseline)[field]==asdict(candidate)[field] for field in asdict(candidate) if field!="suspension_damper_curves")
    assert records[0].samples!=records[1].samples
    (output/"result.json").write_text(json.dumps({"results":results,"changed_conditions":changed_conditions(*records)},ensure_ascii=False,indent=2),encoding="utf-8")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    check(parser.parse_args().output.resolve())
