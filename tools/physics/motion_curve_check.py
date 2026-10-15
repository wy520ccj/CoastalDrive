"""同部件/安装压缩/参考运动比，常比与曲线安装的实际凸起A/B及完整复算。"""

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))
sys.path.insert(0,str(ROOT/"tools"))

from physics.unsprung_step_checkpoint import save_step
from suspension_motion_reference import constant_document, document, rejected_document

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
    records,results,configs=[],[],[]
    original=UnsprungAdvanceInput.solve
    for label,raw in (("A",constant_document()),("B",document())):
        (output/(label+"-input.json")).write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8")
        config,report=fit_bench(raw,base)
        assert report["passed"]
        metadata={"suspension_calibration":report,"basis":"合成安装曲线算法验证，非实测；部件与安装压缩保持，仅安装运动学A/B"}
        save_vehicle_config(output/(label+"-vehicle.json"),config,metadata=metadata)
        configs.append(config)

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
    assert all(asdict(configs[0])[field]==asdict(configs[1])[field] for field in asdict(configs[0]) if field!="suspension_installation_curves")
    assert fit_bench(rejected_document(),base)[1]["passed"] is False
    assert records[0].samples!=records[1].samples
    (output/"result.json").write_text(json.dumps({"results":results,"changed_conditions":changed_conditions(*records)},ensure_ascii=False,indent=2),encoding="utf-8")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    check(parser.parse_args().output.resolve())
