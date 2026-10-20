"""当前驾驶车显式载入后真实同题A/B；旧曲线保持，导出复载验证硬件与代价。"""

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from lab_records import export_record, load_record, model_fingerprint
from lab_runtime import runtime_fingerprint
from race import GameMode
from vehicle_workspace import WorkspaceVehicle
from workshop_cornering import OPTIONS, build_config, evaluate, record_metrics


def sources():
    names = ('src/ui/lab_workbench.py', 'src/ui/lab_workspace.py', 'src/ui/tire_tuning.py', 'tools/lab_driving_car_check.py')
    return {**model_fingerprint(), **{name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}}


def finish(app, workspace):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


def complete(lab):
    lab.start_experiment()
    while not lab.run_state.done:
        lab.run_state.step()
    lab.run_state.paused = True
    lab.record = lab.active_record()
    lab.present_summary(lab.record.metadata['summary'])
    lab.refresh_plots()
    lab.show_sample(960)
    return lab.record


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    summary = {'passed': False, 'source_start': sources(), 'runtime_start': runtime_fingerprint(),
               'size': size, 'human_gate': 'pending'}
    app = CoastalDrive(smoke=True, output=output, lab_output=output/'reports', render_size=tuple(size),
        workspace_vehicle=WorkspaceVehicle('reference-rwd', build_config(0, False, False)))
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    window = app.win

    def capture(name):
        if app.workspace == 'lab':
            app.lab.resize()
        else:
            app.main_menu.resize(app.getAspectRatio())
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))

    try:
        app.open_vehicle_lab()
        finish(app, 'lab')
        lab = app.lab
        lab.set_options(OPTIONS)
        a = complete(lab)
        lab.pin_baseline()
        a_hash = hashlib.sha256(repr(a.snapshots).encode()).hexdigest()
        export_record(a, output/'A')
        lab.entries['cg'].enterText('.47')
        lab.entries['tire_load'].enterText('3500')
        capture('old-A')
        lab.back_to_game()
        finish(app, 'game')
        app.back_to_menu()
        app.choose_slalom_lesson(GameMode.FAST_SLALOM)
        app.open_tire_tuning()
        app.tire_tuning.activate(3)
        app.tire_tuning.activate(4)
        fitted = app.workspace_vehicle
        current_bytes = app.workspace_path.read_bytes()
        app.back_from_tire_tuning()
        app.start_slalom_lesson()
        app.open_vehicle_lab()
        finish(app, 'lab')
        lab = app.lab
        assert lab.engineered_config.lateral_stiffness == 35000. and lab.entries['cg'].get() == '.47'
        assert lab.record.snapshots == a.snapshots and lab.baseline.snapshots == a.snapshots
        cursor, metric = lab.view_index, lab.metric.getText()
        lab.toggle_record_menu()
        capture('load-menu')
        lab.driving_car_button['command']()
        assert lab.engineered_config == fitted.config and lab.workspace_vehicle == fitted
        assert lab.entries['cg'].get() == lab.entries['tire_load'].get() == ''
        assert lab.read_options() == OPTIONS
        assert lab.record.snapshots == a.snapshots and lab.baseline.snapshots == a.snapshots
        assert lab.view_index == cursor and lab.metric.getText() == metric
        capture('prepared-current-car-old-curves')
        b = complete(lab)
        assert hashlib.sha256(repr(a.snapshots).encode()).hexdigest() == a_hash
        assert lab.baseline.snapshots == a.snapshots and b.metadata['vehicle_config']['lateral_stiffness'] == 70000.
        assert b.metadata['vehicle_config']['center_of_mass_height'] == fitted.config.center_of_mass_height
        export_record(b, output/'B', baseline=a)
        restored_a, restored_b = load_record(output/'A'), load_record(output/'B')
        assert restored_a.snapshots == a.snapshots and restored_b.snapshots == b.snapshots
        grade = evaluate(restored_a, restored_b, 3, False, False)
        assert not grade['passed'] and '峰值侧偏超过4°' in grade['unmet']
        assert app.workspace_path.read_bytes() == current_bytes
        capture('new-B-and-old-A')
        lab.back_to_game()
        finish(app, 'game')
        assert app.win is window and app.session.mode == GameMode.FAST_SLALOM and app.workspace_vehicle == fitted
        summary.update(passed=True, A=record_metrics(restored_a), B=record_metrics(restored_b), grade=grade,
            ticks=restored_a.metadata['summary']['ticks']+restored_b.metadata['summary']['ticks'],
            actual_driving_vehicle=asdict(fitted), old_curves_preserved_before_rerun=True,
            old_A_unchanged=True, export_reload_matches=True, current_vehicle_file_unchanged=True,
            same_window=True, returns_to_fast_slalom=True,
            scope='本批两次各1200拍新真实参考定圆；游戏35→70快捷配方与同窗恢复。未新跑完整道路课题，沿用TIRE-TUNING-01驾驶证据。')
        return {'passed': True, 'bits': summary['runtime_start']['math_scalar_bits'], 'ticks': summary['ticks'],
                'B_beta_deg': summary['B']['peak_beta_deg']}
    finally:
        summary.update(source_end=sources(), runtime_end=runtime_fingerprint())
        assert summary['source_start'] == summary['source_end'] and summary['runtime_start'] == summary['runtime_end']
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size), ensure_ascii=False))
