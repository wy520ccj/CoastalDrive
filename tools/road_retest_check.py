"""从已存真实道路A/B运行两类参考复测、导出复载并查看同窗返回；不新造驾驶成绩。"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from lab_records import load_record, model_fingerprint
from lab_runtime import runtime_fingerprint
from player_road_ab import PlayerRoadAB
from race import GameMode
from road_retest import measured
from vehicle_workspace import WorkspaceVehicle


def finish(app, workspace):
    for _ in range(35):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


def check(output, size):
    output.mkdir(parents=True)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    runtime, source = runtime_fingerprint(), model_fingerprint()
    sdk = 'normal' if runtime['math_scalar_bits'] == 32 else 'double'
    car_source = ROOT/f'docs/evidence/BRAKE-ROAD-AB-01/{sdk}/original-vehicle.json'
    app = CoastalDrive(smoke=True, output=output, lab_output=output/'reports', render_size=tuple(size),
        workspace_vehicle=WorkspaceVehicle.load(car_source), independent_clock=True)
    app.workspace_vehicle.save(app.workspace_path)
    car_bytes = app.workspace_path.read_bytes()
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    app.back_to_menu()
    summary = {'passed': False, 'source_start': source, 'runtime_start': runtime, 'size': size,
               'scope': '新参考物理A/B；原道路结束记录复用，无新道路驾驶', 'runs': []}

    def capture(name):
        for _ in range(3):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))

    try:
        for brakes, task, name, mode in (
                (True, 'BRAKE-ROAD-AB-01', 'player-braking-ab.json', GameMode.SHORT_BRAKING),
                (False, 'PLAYER-ROAD-AB-01', 'player-road-ab.json', GameMode.FAST_SLALOM)):
            label = 'braking' if brakes else 'circle'
            path = output/name
            original = (ROOT/f'docs/evidence/{task}/{sdk}/{name}').read_bytes()
            path.write_bytes(original)
            store = PlayerRoadAB(path, brakes=brakes)
            if brakes:
                app.player_brake_ab = store
                app.choose_braking_lesson(mode)
                app.open_brake_tuning()
            else:
                app.player_road_ab = store
                app.choose_slalom_lesson(mode)
                app.open_tire_tuning()
            app.open_player_road_ab()
            app.player_road_panel.retest_button['command']()
            finish(app, 'lab')
            panel = app.lab.road_retest
            comparison = panel.comparison
            assert comparison.status == 'ready' and comparison.run is None
            capture(label+'-ready')
            panel.run_button['command']()
            frames, shown = 0, False
            while comparison.status == 'running':
                panel.update()
                frames += 1
                if not shown and comparison.run is not None and comparison.run.elapsed >= .5:
                    capture(label+'-running')
                    shown = True
                if frames % 30 == 0:
                    app.taskMgr.step()
            assert comparison.done
            report = comparison.report()
            assert all(row['valid'] for row in report['metrics'])
            assert report['comparable']
            capture(label+'-completed')
            panel.export_button['command']()
            assert panel.report_path is not None
            loaded = [load_record(panel.report_path.parent/'baseline-A'), load_record(panel.report_path.parent)]
            for actual, restored in zip(comparison.records, loaded, strict=True):
                assert actual.snapshots == restored.snapshots and actual.commands == restored.commands
                assert measured(actual) == measured(restored)
                assert actual.metadata['source_start'] == actual.metadata['source_end'] == source
                assert actual.metadata['runtime_start'] == actual.metadata['runtime_end'] == runtime
                assert actual.metadata['vehicle_config']['tire_substeps'] == 2
            panel.toggle_details()
            capture(label+'-conditions')
            panel.toggle_details()
            summary['runs'].append({'label': label, 'road_source': f'{task}/{sdk}/{name}',
                'input_sha256': hashlib.sha256(original).hexdigest(), 'report': report,
                'export': str(panel.report_path.relative_to(output))})
            panel.back_button['command']()
            finish(app, 'game')
            assert not app.player_road_panel.root.isHidden()
            assert (app.braking_mode if brakes else app.slalom_mode) == mode
            assert app.workspace_path.read_bytes() == car_bytes and path.read_bytes() == original
            capture(label+'-returned')
            app.player_road_panel.hide()
            app.back_from_tire_tuning()
        summary.update(passed=True, saved_car_unchanged=True, road_inputs_unchanged=True,
                       export_reloaded=True, human_gate='pending')
        return {'passed': True, 'bits': runtime['math_scalar_bits'],
                'ticks': sum(row['ticks'] for run in summary['runs'] for row in run['report']['metrics'])}
    finally:
        app.close_game()
        summary.update(source_end=model_fingerprint(), runtime_end=runtime_fingerprint())
        assert summary['source_end'] == source and summary['runtime_end'] == runtime
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size), ensure_ascii=False))
