"""正式实验台实体凸起对照；保存实际快照、指标、模型版本与精确复算结果。"""

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from lab_experiment import LabExperiment, LabOptions
from lab_metrics import engineering_analysis
from lab_records import LabRecord, changed_conditions, export_record, load_record, recalculate
from vehicle_designs import REFERENCE_DESIGN


def check(output, masses, duration, repeat):
    output.mkdir(parents=True, exist_ok=False)
    baseline = None
    results = []
    for mass in masses:
        options = LabOptions(maneuver="ride_bump", speed_kph=18., duration=duration)
        config = replace(REFERENCE_DESIGN, unsprung_enabled=True, unsprung_masses=(mass,)*4)
        run = LabExperiment(options, config=config, parameter_metadata={
            "basis":"轮端质量/径向材料为设计假设；总质量1200kg固定，簧上质量随分解变化，非实测"})
        try:
            while not run.done:
                run.step()
            record = LabRecord.from_run(run)
            folder = output / f"mass-{mass:g}"
            export_record(record, folder, baseline)
            restored = load_record(folder)
            assert restored.snapshots == record.snapshots and restored.samples == record.samples
            analysis = engineering_analysis(restored.samples, restored.snapshots,
                                            restored.metadata["summary"]["options"], run.reason)
            item = {"mass_kg":mass, "reason":run.reason, "error":run.error,
                    "frames":len(run.snapshots), "metrics":analysis["ride"]["metrics"],
                    "changed_conditions":changed_conditions(baseline, record) if baseline else {},
                    "record_roundtrip_exact":True, "recalculate_exact":None}
            if repeat and run.reason=="time_limit":
                repeated = recalculate(restored)
                item["recalculate_exact"] = (repeated.snapshots==restored.snapshots
                                             and repeated.samples==restored.samples
                                             and repeated.commands==restored.commands)
                assert item["recalculate_exact"]
            results.append(item)
            (output / "result.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(item), flush=True)
            baseline = record if baseline is None else baseline
            if run.reason!="time_limit":
                raise RuntimeError(f"实际凸起试验未完成：{run.reason} / {run.error}")
        finally:
            run.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--masses", type=float, nargs="+", default=[25.,65.])
    parser.add_argument("--duration", type=float, default=2.4)
    parser.add_argument("--repeat", action="store_true")
    args = parser.parse_args()
    check(args.output.resolve(), args.masses, args.duration, args.repeat)
