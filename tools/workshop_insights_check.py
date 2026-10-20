"""两库解读面板与失败导出；金牌复用原始记录，缺少留档的失败配方单独短测。"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

import workshop
import workshop_cornering as cornering
from lab_application import VehicleLab
from lab_experiment import LabExperiment
from lab_records import LabRecord, export_record, load_record
from lab_runtime import runtime_fingerprint
from workshop_insights import describe, export_insights


def check(output, size, braking, corner):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    sources = ['src/workshop_insights.py', 'src/ui/workshop_insights.py', 'src/ui/lab_workshop.py',
               'src/lab_application.py', 'src/workshop.py', 'src/workshop_cornering.py',
               'src/lab_experiment.py', 'tools/workshop_insights_check.py']

    def fingerprints():
        return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources}

    result = {'passed': False, 'runtime': runtime_fingerprint(), 'source_start': fingerprints(),
              'size': size, 'cases': [], 'human_gate': 'pending'}
    app = VehicleLab(offscreen=True, render_size=tuple(size), output=output/'exports')
    app.engine.taskMgr.remove('lab-update')

    def trial(topic, selection, name):
        module = cornering if topic else workshop
        run = LabExperiment(module.OPTIONS, config=module.build_config(*selection))
        try:
            while not run.done:
                run.step()
            record = LabRecord.from_run(run)
            export_record(record, output/'raw'/name)
            return record
        finally:
            run.close()

    def capture(name):
        app.resize()
        for _ in range(6):
            app.engine.taskMgr.step()
        app.engine.graphicsEngine.syncFrame()
        assert app.engine.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))

    try:
        brake_base = trial(0, (0, False), 'brake-base')
        brake_over = trial(0, (2, True), 'brake-over')
        corner_base = trial(1, (0, False, False), 'corner-base')
        corner_sharp = trial(1, (3, False, False), 'corner-sharp')
        cases = [('brake-original', 0, (0, False), brake_base, brake_base, None),
                 ('brake-over', 0, (2, True), brake_base, brake_over, None),
                 ('brake-gold', 0, (2, False), load_record(braking/'baseline-A'), load_record(braking), str(braking)),
                 ('corner-sharp', 1, (3, False, False), corner_base, corner_sharp, None),
                 ('corner-gold', 1, (2, False, False), load_record(corner/'baseline-A'), load_record(corner), str(corner))]
        panel = app.workshop
        for name, topic, selection, baseline, candidate, reused in cases:
            data = describe(baseline, candidate, topic, selection)
            folder = output/'reports'/name
            export_record(candidate, folder, baseline=baseline)
            export_insights(data, folder)
            panel.restore({'topic': topic, 'selection': selection, 'baseline': baseline, 'candidate': candidate,
                           'result': (cornering if topic else workshop).evaluate(baseline, candidate, *selection), 'text': ''})
            panel.show()
            panel.present_result()
            panel.show_insights()
            assert panel.insights.data == data and not panel.insights.root.isHidden()
            capture(name)
            state = panel.capture()
            panel.restore(state)
            assert not panel.insights.root.isHidden()
            app.escape()
            assert panel.insights.root.isHidden() and not panel.root.isHidden()
            panel.show_insights()
            proposal = data['next']['selection']
            if proposal is not None:
                panel.prepare_next_trial()
                assert panel.selection() == proposal and panel.result is None and panel.phase is None
                assert panel.baseline is baseline and panel.candidate is candidate
                capture(name+'-prepared')
            result['cases'].append({'name': name, 'data': data, 'reused_record': reused,
                                    'physical_ticks': [baseline.metadata['summary']['ticks'], candidate.metadata['summary']['ticks']]})
        result['source_end'] = fingerprints()
        assert result['source_start'] == result['source_end']
        assert app.workspace_vehicle is None and app.next_workspace is None
        result['passed'] = True
        return {'passed': True, 'bits': result['runtime']['math_scalar_bits'], 'cases': len(cases)}
    finally:
        (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--braking', type=Path, required=True)
    parser.add_argument('--cornering', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.braking.resolve(), args.cornering.resolve()), ensure_ascii=False))
