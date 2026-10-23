"""隔离目录检查实际新赛道简报和手动调校，再保存同一车辆进入工坊。"""

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from career import EVENTS
from garage_setup import GROUPS
from vehicle_workspace import WorkspaceVehicle


def capture(output, size, *, brief_only=False):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    rows = []

    def shot(name):
        before = asdict(app.session.current)
        for _ in range(8):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        assert before == asdict(app.session.current)
        rows.append(name+'.png')

    try:
        app.open_career()
        for event in EVENTS[3:]:
            app.career_action('brief', event.id)
            shot('brief-'+event.id)
        if brief_only:
            (output/'summary.json').write_text(json.dumps({'passed': True, 'captures': rows,
                'size': size, 'new_driving_steps': 0}), encoding='utf-8')
            return
        app.open_career_collection()
        app.career_action('garage-tab', 'setup')
        for group in GROUPS:
            app.career_action('setup-group', group)
            shot('setup-'+group)
        app.career_panel.setup_entries['final_drive'].enterText('4.1')
        app.career_action('setup-group', 'tires')
        app.career_panel.setup_entries['front_tire'].enterText('72')
        app.career_action('setup-save')
        assert app.workspace_vehicle.config.final_drive == 4.1
        assert app.session.base_vehicle_config.lateral_stiffness == 72000.
        assert WorkspaceVehicle.load(app.workspace_path) == app.workspace_vehicle
        shot('setup-saved')
        vehicle = app.workspace_vehicle
        app.career_action('setup-lab')
        for _ in range(2500):
            app.taskMgr.step()
            if app._workspace_steps is None:
                break
        assert app._workspace_steps is None and app.lab is not None
        assert app.workspace_vehicle == app.lab.workspace_vehicle == vehicle
        assert app.lab.engineered_config == vehicle.config
        report = {'passed': True, 'captures': rows, 'size': size, 'new_driving_steps': 0,
                  'saved_vehicle': asdict(vehicle), 'same_vehicle_sent_to_lab': True}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'passed': True, 'captures': rows, 'same_vehicle_sent_to_lab': True}))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--brief-only', action='store_true')
    args = parser.parse_args()
    capture(args.output.resolve(), tuple(args.size), brief_only=args.brief_only)
