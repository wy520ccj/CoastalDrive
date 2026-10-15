"""部件安装预压进入唯一Simulation：静载/车高解析差与完整实体凸起记录复算。"""

import argparse
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))

from suspension_preload_reference import document

from lab_experiment import LabExperiment, LabOptions
from lab_metrics import engineering_analysis
from lab_records import LabRecord, changed_conditions, export_record, load_record, recalculate
from suspension_bench import fit_bench
from vehicle_designs import REFERENCE_DESIGN
from vehicle_parameters import save_vehicle_config


def check(output):
    output.mkdir(parents=True,exist_ok=False)
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    results,records,statics,configs = [],[],[],[]
    base = replace(REFERENCE_DESIGN,unsprung_enabled=True)
    for label,compression in (("A",0.),("B",.016)):
        raw = document(compression)
        (output/(label+"-input.json")).write_text(json.dumps(raw,ensure_ascii=False,indent=2),encoding="utf-8")
        config,report = fit_bench(raw,base)
        assert report["passed"]
        metadata = {"suspension_calibration":report,"basis":"合成线性部件安装预压验证，非实测；仅安装压缩A/B"}
        save_vehicle_config(output/(label+"-vehicle.json"),config,metadata=metadata)
        configs.append(config)
        run = LabExperiment(LabOptions(maneuver="ride_bump",speed_kph=18.,duration=2.4),config=config,parameter_metadata=metadata)
        try:
            state = run.current.player
            statics.append({"q_m":[wheel.compression for wheel in state.wheel_contacts],
                "normal_N":state.unsprung_state.normal_force,"sprung_position_m":state.unsprung_state.sprung_position,
                "total_center_m":state.unsprung_state.total_center_position})
            while not run.done:run.step()
            assert run.reason=="time_limit",(run.reason,run.error)
            record=LabRecord.from_run(run)
            assert record.metadata["source_start"]==record.metadata["source_end"]
            assert record.metadata["runtime_start"]==record.metadata["runtime_end"]
            export_record(record,output/label,records[0] if records else None)
            loaded=load_record(output/label)
            assert loaded.snapshots==record.snapshots and loaded.samples==record.samples and loaded.commands==record.commands
            repeated_exact = None
            if label=="B":
                repeated=recalculate(loaded)
                repeated_exact=(repeated.snapshots==loaded.snapshots and repeated.samples==loaded.samples and repeated.commands==loaded.commands)
                assert repeated_exact
            records.append(record)
            results.append({"label":label,"summary":run.summary(),"static":statics[-1],"record_roundtrip_exact":True,
                "recalculate_exact":repeated_exact,"analysis":engineering_analysis(record.samples,record.snapshots,asdict(run.options),run.reason)})
            (output/"result.json").write_text(json.dumps({"results":results},ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps({"label":label,"frames":len(record.samples),"recalculate_exact":repeated_exact}),flush=True)
        finally:
            run.close()
    changes={field for field in asdict(configs[0]) if asdict(configs[0])[field]!=asdict(configs[1])[field]}
    assert changes=={"suspension_spring_preloads"}
    q_shift=np.array(statics[1]["q_m"])-statics[0]["q_m"]
    height_shift=statics[1]["sprung_position_m"][2]-statics[0]["sprung_position_m"][2]
    assert np.max(np.abs(q_shift+.02))<2e-5
    assert abs(height_shift-.02)<2e-5
    assert np.max(np.abs(np.asarray(statics[1]["normal_N"])-statics[0]["normal_N"]))<.5
    (output/"result.json").write_text(json.dumps({"results":results,"q_shift_m":q_shift.tolist(),"height_shift_m":height_shift,
        "analytic_q_shift_m":-.02,"changed_conditions":changed_conditions(*records)},ensure_ascii=False,indent=2),encoding="utf-8")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    check(parser.parse_args().output.resolve())
