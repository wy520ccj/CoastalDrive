"""真实颠簸制动的簧下质量A/B；保留全配置、快照、信号、命令和准确复算。"""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src"))

from unsprung_step_checkpoint import save_step

from lab_experiment import LabExperiment, LabOptions
from lab_metrics import engineering_analysis
from lab_records import LabRecord, changed_conditions, export_record, load_record, recalculate
from vehicle_designs import REFERENCE_DESIGN
from vehicle_unsprung import UnsprungAdvanceInput


def check(output,masses,repeat):
    output.mkdir(parents=True,exist_ok=False)
    (output/"executed-tool.py").write_bytes(Path(__file__).read_bytes())
    baseline,results = None,[]
    original_solve = UnsprungAdvanceInput.solve
    for mass in masses:
        config = replace(REFERENCE_DESIGN,unsprung_enabled=True,unsprung_masses=(mass,)*4)
        options = LabOptions(maneuver="ride_braking",speed_kph=30.,onset=.6,duration=3.)
        run = LabExperiment(options,config=config,parameter_metadata={
            "basis":"总质量1200kg固定，轮端质量为设计假设，随分解改变簧上质量/惯量；非实测"})
        folder = output/f"mass-{mass:g}"
        def solve(source,*,capture_file=output/f"mass-{mass:g}-failed-step.pkl",**kwargs):
            try:return original_solve(source,**kwargs)
            except ArithmeticError:
                save_step(source,capture_file)
                raise

        UnsprungAdvanceInput.solve = solve
        try:
            try:
                while not run.done:run.step()
            except ArithmeticError:
                export_record(LabRecord.from_run(run),folder,baseline)
                (output/"failure.json").write_text(json.dumps(run.summary(),indent=2,ensure_ascii=False),encoding="utf-8")
                raise
            record = LabRecord.from_run(run)
            export_record(record,folder,baseline)
            restored = load_record(folder)
            assert restored.snapshots==record.snapshots and restored.samples==record.samples
            analysis = engineering_analysis(record.samples,record.snapshots,
                record.metadata["summary"]["options"],record.metadata["summary"]["reason"])
            item = {"mass_kg":mass,"summary":run.summary(),"analysis":analysis,
                    "changed_conditions":changed_conditions(baseline,record) if baseline else {},
                    "record_roundtrip_exact":True,"recalculate_exact":None}
            if repeat and mass==masses[0] and run.reason=="stopped":
                repeated = recalculate(restored)
                item["recalculate_exact"] = (repeated.snapshots==restored.snapshots
                    and repeated.samples==restored.samples and repeated.commands==restored.commands)
                assert item["recalculate_exact"]
            results.append(item)
            (output/"result.json").write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding="utf-8")
            print(json.dumps({"mass":mass,"reason":run.reason,"stop_m":run.summary()["stopping_distance_m"],
                             "recalculate_exact":item["recalculate_exact"]}),flush=True)
            if run.reason!="stopped":raise RuntimeError(f"颠簸制动未完成：{run.reason}")
            baseline = record if baseline is None else baseline
        finally:
            UnsprungAdvanceInput.solve = original_solve
            run.close()


if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--masses",type=float,nargs="+",default=(25.,65.))
    parser.add_argument("--repeat",action="store_true",help="只对第一组完整记录精确复算")
    args = parser.parse_args()
    check(args.output.resolve(),args.masses,args.repeat)
