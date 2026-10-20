"""复用归档真实解读数据检查布局；不新增物理试验。"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from lab_application import VehicleLab


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    sources = ROOT/'docs/evidence/WORKSHOP-INSIGHTS-01/normal/reports'
    inputs = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources.rglob('insights.json')}
    app = VehicleLab(offscreen=True, render_size=tuple(size), output=output/'exports')
    app.engine.taskMgr.remove('lab-update')
    try:
        current = app.active_record(), app.baseline, app.workspace_vehicle
        app.workshop.show()
        panel = app.workshop.insights
        cases = []
        for name in ('brake-gold', 'brake-over', 'corner-sharp', 'corner-gold'):
            path = sources/name/'insights.json'
            data = json.loads(path.read_text(encoding='utf-8'))
            panel.show(data)
            app.resize()
            for _ in range(6):
                app.engine.taskMgr.step()
            app.engine.graphicsEngine.syncFrame()
            assert app.engine.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
            assert panel.data == data
            assert (app.active_record(), app.baseline, app.workspace_vehicle) == current
            cases.append({'case': name, 'source': str(path.relative_to(ROOT)), 'sha256': inputs[path],
                          'passed_challenge': data['passed'], 'cost': data['cost']})
        assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in inputs.items())
        result = {'passed': True, 'size': size, 'cases': cases, 'new_physics_ticks': 0,
                  'basis': '归档真实A/B解读JSON静态显示；原记录、参考、基线与驾驶车保持。人工体验待确认。'}
        (output/'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'passed': True, 'images': len(cases), 'new_physics_ticks': 0}
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size)))
