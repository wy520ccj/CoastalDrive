"""固定参考定圆的工程取舍实测；每个候选用同一控制器、原车和连续报价。"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from challenge_build import BuildDraft
from lab_experiment import LabExperiment
from lab_records import LabRecord, export_record
from workshop_budget import REFERENCE_CHALLENGES, evaluate

BUILDS = {'front125': BuildDraft(front_tire=1.25, antiroll_share=8/30),
          'front130': BuildDraft(front_tire=1.3, antiroll_share=8/30),
          'rear90': BuildDraft(front_tire=1.3, rear_tire=.9, antiroll_share=8/30),
          'balanced': BuildDraft(front_tire=1.2, rear_tire=.8, antiroll_share=.15),
          'free': BuildDraft(antiroll_share=.05)}


def run(output, builds):
    output.mkdir(parents=True, exist_ok=False)
    spec = REFERENCE_CHALLENGES[1]

    def trial(config):
        experiment = LabExperiment(spec.options, config=config)
        try:
            while not experiment.done:
                experiment.step()
            return LabRecord.from_run(experiment)
        finally:
            experiment.close()

    baseline = trial(spec.base_config)
    export_record(baseline, output/'baseline-A')
    rows = []
    for name in builds:
        build = BUILDS[name]
        candidate = trial(spec.configuration(build))
        result = evaluate(1, baseline, candidate, build)
        export_record(candidate, output/name)
        rows.append({'name': name, 'build': asdict(build), 'result': result,
                     'record': str((output/name).resolve())})
        (output/'summary.json').write_text(json.dumps({'rows': rows, 'baseline': str((output/'baseline-A').resolve()),
            'scope': '固定参考控制器/10秒定圆工程实测；不是道路真人样本、整包难度或驾驶FPS验收。'},
            ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'build': name, 'cost': build.cost, 'medal': result['medal'],
                          'improvement_pct': result['improvement_pct'], 'unmet': result['unmet']},
                         ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--builds', choices=tuple(BUILDS), nargs='+', default=list(BUILDS))
    args = parser.parse_args()
    run(args.output.resolve(), args.builds)
