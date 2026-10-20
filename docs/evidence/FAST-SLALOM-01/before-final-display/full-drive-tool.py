"""同一键盘策略实际驾驶35/50/70k配方，经原实验台改装回到高速验车。"""

import argparse
import gzip
import hashlib
import json
import math
import os
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename
from slalom_driver import SlalomDriver, apply_keys

from application import CoastalDrive
from lab_experiment import LabOptions
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from race import BestTimes, GameMode
from session import Phase
from session_process import SessionProcess
from slalom_lesson import SlalomLesson, SlalomScores
from vehicle_parameters import config_from_document
from vehicle_workspace import WorkspaceVehicle
from workshop_cornering import build_config


def sources():
    extra = ('src/ui/slalom_feedback.py', 'src/ui/hud.py', 'tools/fast_slalom_check.py', 'tools/slalom_driver.py')
    return {**model_fingerprint(), **{name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in extra}}


def recheck(folder):
    document = json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    config = config_from_document(document['config'], build_config(0, False, False))
    lesson = SlalomLesson(document['start_progress'], SlalomScores(folder/'recheck-best.json', 'recheck'), config, fast=True)
    # 复核的写盘位置单独隔离；旧有效复核可只读再运行。
    with gzip.open(folder/'raw.json.gz', 'rt', encoding='utf-8') as stream:
        rows = json.load(stream)
    for row in rows:
        state = row['result']
        actual = lesson.update(row['position'][1], row['velocity'][1], row['elapsed'],
            lateral=row['position'][0], heading=row['heading'], collisions=row['collisions'])
        observed = asdict(actual)
        for key, value in observed.items():
            if key in ('best_seconds', 'new_best', 'reference_times'):
                continue
            assert json.loads(json.dumps(value)) == state[key], (key, row['tick'], value, state[key])
    return {'passed': True, 'rows': len(rows), 'succeeded': actual.succeeded}


def finish(app, workspace):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


def check(output, size, restore=False):
    output.mkdir(parents=True, exist_ok=restore)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    summary = {'passed': False, 'source_start': sources(), 'runtime_start': runtime_fingerprint(),
               'cases': [], 'human_gate': 'pending', 'restore': restore}
    if restore:
        path = output/'slalom-best.json'
        old = path.read_bytes()
        session = SessionProcess(scores=BestTimes(output/'test-best-times.json'),
            vehicle_config=build_config(3, False, False), independent_clock=False)
        try:
            session.start(countdown=False, mode=GameMode.FAST_SLALOM, track='endless', settle_initial=True)
            result = session.highway.snapshot.slalom
            assert result.fast and result.best_seconds is not None and result.reference_times
            assert path.read_bytes() == old
            summary.update(passed=True, pid=session.process.pid, restored=asdict(result), file_unchanged=True,
                           source_end=sources(), runtime_end=runtime_fingerprint(), scope='实际独立进程只读恢复；没有新完整驾驶')
        finally:
            session.close()
            (output/'restore-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'passed': summary['passed'], 'restore': True}
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size), lab_output=output/'reports',
        workspace_vehicle=WorkspaceVehicle('reference-rwd', build_config(0, False, False)))
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    window = app.win

    def capture(name):
        if app.workspace == 'lab':
            app.lab.resize()
        else:
            app.main_menu.resize(app.getAspectRatio())
            app.hud.resize(app.getAspectRatio())
            app.lab_return_button.setX(app.getAspectRatio()-.44)
            if app.scene is not None:
                app.chase_camera.position = None
                app.apply_scene(app.session.current, 0.)
                app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                               track=app.session.simulation.track, countdown='', notice='')
            app._shown_phase = None
            app.refresh_panel()
        before = app.session.current if app.workspace == 'game' else app.lab.active_record()
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert before == (app.session.current if app.workspace == 'game' else app.lab.active_record())
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))

    try:
        app.back_to_menu()
        app.choose_slalom_lesson()
        capture('ordinary-rules')
        app.buttons[1]['command']()
        capture('fast-rules')
        app.buttons[0]['command']()
        for index in (0, 2, 3):
            for _ in range(360):
                app.session.tick()
            assert app.session.phase == Phase.DRIVING and app.session.mode == GameMode.FAST_SLALOM
            config, variant = app.session.vehicle_config, app.session.score_variant()
            assert config.lateral_stiffness == build_config(index, False, False).lateral_stiffness
            start = app.session.highway.snapshot.slalom.start_progress
            driver = SlalomDriver(75., config, origin=start)
            rows = []
            for _ in range(4802):
                apply_keys(app.session.keyboard, driver.sample(app.session.current, 1/120))
                app.session.tick()
                state, result = app.session.current, app.session.highway.snapshot.slalom
                rows.append({'tick': state.tick, 'elapsed': app.session.highway.snapshot.elapsed,
                    'position': state.player.position, 'velocity': state.player.velocity, 'heading': state.player.heading,
                    'collisions': state.collisions, 'keys': sorted(app.session.keyboard.pressed),
                    'request': asdict(app.session.last_control), 'beta_deg': math.degrees(state.player.dynamics.sideslip),
                    'roll_deg': state.player.roll, 'result': asdict(result)})
                if result.position >= 90. and result.position < 90.3:
                    capture(f'{index}-driving')
                if app.session.phase == Phase.RESULTS:
                    break
            folder = output/str(index)
            folder.mkdir()
            with gzip.open(folder/'raw.json.gz', 'wt', encoding='utf-8') as stream:
                json.dump(rows, stream, ensure_ascii=False)
            case = {'config': asdict(config), 'variant': variant, 'start_progress': start, 'rows': len(rows),
                'result': asdict(result), 'peak_beta_deg': max(abs(row['beta_deg']) for row in rows),
                'peak_roll_deg': max(abs(row['roll_deg']) for row in rows)}
            (folder/'summary.json').write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')
            summary['cases'].append(case)
            checked = recheck(folder)
            (folder/'recheck.json').write_text(json.dumps(checked, indent=2), encoding='utf-8')
            assert result.finished and result.succeeded == (index == 3) and app.win is window
            capture(f'{index}-result')
            if index == 3:
                app.buttons[0]['command']()
                for _ in range(360):
                    app.session.tick()
                assert app.session.highway.snapshot.slalom.best_seconds == result.run_seconds
                assert app.session.highway.snapshot.slalom.reference_times == result.gate_times
                break
            app.open_vehicle_lab()
            finish(app, 'lab')
            lab = app.lab
            next_index = 2 if index == 0 else 3
            path = output/f'{next_index}-engineering.json'
            path.write_text(json.dumps(asdict(build_config(next_index, False, False))), encoding='utf-8')
            lab.import_engineering(path)
            lab.set_options(LabOptions(vehicle_id='reference-rwd', duration=.1, speed_kph=20., friction=1.1,
                                       esc_enabled=False))
            lab.start_experiment()
            while not lab.run_state.done:
                lab.run_state.step()
            lab.design_loop.show()
            capture(f'{next_index}-lab')
            lab.design_loop.drive()
            finish(app, 'game')
            assert app.win is window and app.session.mode == GameMode.FAST_SLALOM
        summary.update(passed=True, source_end=sources(), runtime_end=runtime_fingerprint(),
            rows=sum(case['rows'] for case in summary['cases']), same_window=True,
            scope='新真实KeyboardController三种配方，同一75km/h策略；实验台导入/短参考试验/保存后回到同题，非人工驾驶')
        assert summary['source_start'] == summary['source_end'] and summary['runtime_start'] == summary['runtime_end']
        return {'passed': True, 'rows': summary['rows'], 'bits': summary['runtime_start']['math_scalar_bits']}
    finally:
        summary.update(source_end=sources(), runtime_end=runtime_fingerprint())
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.restore), ensure_ascii=False))
