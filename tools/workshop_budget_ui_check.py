"""真实参考A/B的预算页与结果实图；第二画幅直接复用同一批原始记录。"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from panda3d.core import Filename

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from challenge_build import BuildDraft
from lab_application import VehicleLab
from lab_records import export_record, load_record


def check(output, size, records=None, topics=(0, 1)):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = VehicleLab(offscreen=True, render_size=size, output=output/'reports', workspace_path=output/'vehicle.json')
    app.engine.taskMgr.remove('lab-update')
    cases, trials = [], []

    def capture(name):
        panel = app.workshop.editor
        count = None if app.run_state is None else len(app.run_state.snapshots)
        app.engine.taskMgr.step()
        for _ in range(6):
            app.engine.graphicsEngine.renderFrame()
        path = output/(name+'.png')
        assert app.engine.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
        aspect = app.engine.getAspectRatio()
        bounds = []
        for label in panel.labels:
            if not label.getText():
                continue
            low, high = label.getTightBounds(app.engine.aspect2d)
            fits = -aspect-.001 <= low.x <= high.x <= aspect+.001 and -1.001 <= low.z <= high.z <= 1.001
            bounds.append({'text': label.getText(), 'fits': fits, 'low': list(low), 'high': list(high)})
        assert app.run_state is None or len(app.run_state.snapshots) == count
        cases.append({'image': path.name, 'passed': all(row['fits'] for row in bounds), 'bounds': bounds})

    try:
        panel = app.workshop
        for topic, title, build, tab in ((0, 'braking', BuildDraft(brake_share=.7), 2),
                (1, 'cornering', BuildDraft(front_tire=1.3, antiroll_share=round(8/30, 10)), 1)):
            if topic not in topics:
                continue
            panel.set_topic(topic)
            panel.drafts[topic], panel.tab = build, tab
            panel.show()
            capture(title+'-build')
            if records is None:
                panel.start()
                while panel.phase is not None:
                    while not app.run_state.done:
                        app.run_state.step()
                    app.update(SimpleNamespace(cont=None))
                if panel.result is None:
                    raise RuntimeError('真实A/B未完成，不能以夹具补结果')
                folder = output/'records'/title
                export_record(panel.candidate, folder, panel.baseline)
                (folder/'challenge.json').write_text(json.dumps(panel.result, ensure_ascii=False, indent=2), encoding='utf-8')
            else:
                folder = records/title
                receipt = json.loads((folder/'challenge.json').read_text(encoding='utf-8'))
                panel.baseline, panel.candidate = load_record(folder/'baseline-A'), load_record(folder)
                panel.measured_build = BuildDraft(**receipt['build'])
                panel.result = panel.evaluate_records()
                if panel.result != receipt:
                    raise ValueError('复用原始记录与本次参考规则不一致')
                panel.present_result()
            capture(title+'-result')
            trials.append({'topic': topic, 'result': panel.result, 'build': asdict(panel.measured_build),
                           'records': str(folder.resolve()), 'new_trial': records is None})
        report = {'passed': all(row['passed'] for row in cases), 'cases': cases, 'size': size, 'trials': trials,
                  'scope': '真实参考制动/定圆A/B与原始记录；无真人道路驾驶、金牌标定或驾驶FPS结论。'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'passed': report['passed'], 'cases': len(cases),
                           'trials': [(row['topic'], row['result']['medal'], row['result']['cost']) for row in trials]}))
        return report['passed']
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1672, 941))
    parser.add_argument('--records', type=Path, help='直接复用另一画幅已完成的两个真实A/B，不重跑物理')
    parser.add_argument('--topics', type=int, choices=(0, 1), nargs='+', default=[0, 1])
    args = parser.parse_args()
    raise SystemExit(0 if check(args.output.resolve(), tuple(args.size), args.records, args.topics) else 1)
