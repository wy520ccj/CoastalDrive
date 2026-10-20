"""从原保存方案经游戏前胎面板真实验车，独立进程再恢复原车。"""

import argparse
import gzip
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from fast_slalom_check import recheck
from panda3d.core import Filename
from slalom_driver import SlalomDriver, apply_keys

from application import CoastalDrive
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from race import GameMode
from session import Phase
from tire_tuning import previous_path
from vehicle_workspace import WorkspaceVehicle


def sources():
    paths = ('src/ui/tire_tuning.py', 'tools/tire_tuning_check.py', 'tools/fast_slalom_check.py', 'tools/slalom_driver.py')
    return {**model_fingerprint(), **{name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}}


def files(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


def check(output, size, restore=False):
    output.mkdir(parents=True, exist_ok=restore)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    path = output/'test-workspace-vehicle.json'
    if not restore:
        source = ROOT/'docs/evidence/DESIGN-SCHEMES-01/normal/schemes'
        for entry in source.rglob('*'):
            if entry.is_file():
                dest = output/'test-schemes'/entry.relative_to(source)
                dest = dest.with_suffix('') if dest.suffix == '.gz' else dest
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(gzip.decompress(entry.read_bytes()) if entry.suffix == '.gz' else entry.read_bytes())
        original = WorkspaceVehicle.load(output/'test-schemes/e8009496ea504a31b63bdd5e754955b5/vehicle.json')
        original.save(output/'original-vehicle.json')
        original.save(path)
    else:
        original = WorkspaceVehicle.load(output/'original-vehicle.json')
    car = WorkspaceVehicle.load(path)
    summary = {'passed': False, 'source_start': sources(), 'runtime_start': runtime_fingerprint(),
               'restore': restore, 'cases': [], 'size': size, 'human_gate': 'pending'}
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size), workspace_vehicle=car, independent_clock=restore)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    window = app.win
    frozen_schemes = files(output/'test-schemes')

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        if app.scene is not None:
            app.chase_camera.position = None
            app.apply_scene(app.session.current, 0.)
        before = app.session.current
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert before == app.session.current
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))

    try:
        app.back_to_menu()
        app.choose_slalom_lesson(GameMode.FAST_SLALOM)
        if restore:
            old_scores = (output/'slalom-best.json').read_bytes()
            app.open_tire_tuning()
            assert car.config.lateral_stiffness == 70000.
            capture('reopened-tuning')
            app.tire_tuning.activate(5)
            assert app.workspace_vehicle.config.lateral_stiffness == 35000.
            app.tire_tuning.activate(5)
            assert app.workspace_vehicle == original and WorkspaceVehicle.load(path) == original
            assert path.read_bytes() == (output/'original-vehicle.json').read_bytes()
            assert (output/'slalom-best.json').read_bytes() == old_scores
            capture('restored-original')
            summary.update(pid=app.session.process.pid, original_restored=True, scores_unchanged=True,
                scope='实际独立SessionProcess菜单读取70k，再恢复35k及完整原50k/方案关联；无新完整驾驶')
        else:
            for index in (0, 3):
                app.open_tire_tuning()
                capture(f'{index}-tuning')
                before = app.workspace_vehicle
                app.tire_tuning.activate(index)
                capture(f'{index}-preview')
                assert app.workspace_vehicle == before
                app.tire_tuning.activate(4)
                tuned = app.workspace_vehicle
                assert WorkspaceVehicle.load(path) == tuned and tuned.scheme_id is None and tuned.workshop_result is None
                assert previous_path(tuned, path).exists()
                capture(f'{index}-installed')
                app.tire_tuning.activate(6)
                app.buttons[0]['command']()
                for _ in range(360):
                    app.session.tick()
                assert app.session.phase == Phase.DRIVING and app.session.mode == GameMode.FAST_SLALOM
                driver = SlalomDriver(75., app.session.vehicle_config, origin=app.session.highway.snapshot.slalom.start_progress)
                rows = []
                for _ in range(4802):
                    apply_keys(app.session.keyboard, driver.sample(app.session.current, 1/120))
                    app.session.tick()
                    state, result = app.session.current, app.session.highway.snapshot.slalom
                    rows.append({'tick': state.tick, 'elapsed': app.session.highway.snapshot.elapsed,
                        'position': state.player.position, 'velocity': state.player.velocity, 'heading': state.player.heading,
                        'collisions': state.collisions, 'keys': sorted(app.session.keyboard.pressed),
                        'request': asdict(app.session.last_control), 'result': asdict(result)})
                    if result.finished:
                        break
                folder = output/str(index)
                folder.mkdir()
                case = {'config': asdict(app.session.vehicle_config), 'start_progress': result.start_progress,
                        'rows': len(rows), 'variant': app.session.score_variant(), 'result': asdict(result)}
                with gzip.open(folder/'raw.json.gz', 'wt', encoding='utf-8') as stream:
                    json.dump(rows, stream, ensure_ascii=False)
                (folder/'summary.json').write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')
                summary['cases'].append(case)
                checked = recheck(folder)
                (folder/'recheck.json').write_text(json.dumps(checked, indent=2), encoding='utf-8')
                assert result.finished and result.succeeded == (index == 3) and app.win is window
                app._shown_phase = None
                app.refresh_panel()
                capture(f'{index}-result')
                app.back_to_menu()
                app.choose_slalom_lesson(GameMode.FAST_SLALOM)
            summary.update(rows=sum(case['rows'] for case in summary['cases']), same_window=True,
                scope='新真实二值KeyboardController，游戏内前胎35k失败→70k成功；同一原75km/h策略，非人工驾驶')
        assert files(output/'test-schemes') == frozen_schemes
        summary.update(scheme_files_unchanged=True, source_end=sources(), runtime_end=runtime_fingerprint(), passed=True)
        assert summary['source_start'] == summary['source_end'] and summary['runtime_start'] == summary['runtime_end']
        return {'passed': True, 'bits': summary['runtime_start']['math_scalar_bits'], 'restore': restore, 'rows': summary.get('rows', 0)}
    finally:
        summary.update(source_end=sources(), runtime_end=runtime_fingerprint())
        (output/('restore-summary.json' if restore else 'summary.json')).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.restore), ensure_ascii=False))
