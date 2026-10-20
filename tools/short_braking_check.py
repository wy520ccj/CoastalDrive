"""新真实键盘短距验车、结算改分配、原规则重放与独立进程恢复。"""

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

from application import CoastalDrive
from braking_lesson import BrakingScores
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from race import GameMode
from session import Phase
from short_braking import ShortBraking
from vehicle_workspace import WorkspaceVehicle
from workshop import build_config


def sources():
    names = ('src/ui/player_road_ab.py', 'src/ui/tire_tuning.py', 'src/ui/braking_feedback.py', 'src/ui/hud.py', 'tools/short_braking_check.py')
    return {**model_fingerprint(), **{name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}}


def recheck(folder):
    case = json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    run = ShortBraking(case['start_progress'], BrakingScores(folder/'recheck-best.json', 'check', maximum=42))
    with gzip.open(folder/'raw.json.gz', 'rt', encoding='utf-8') as stream:
        rows = json.load(stream)
    for row in rows:
        result = run.update(row['position'][1], row['velocity'][1], row['speed'], row['elapsed'], 1/120,
                            lateral=row['position'][0], heading=row['heading'], collisions=row['collisions'])
        for key, value in asdict(result).items():
            if key in ('best_distance', 'save_notice'):
                continue
            assert value == row['result'][key], (row['tick'], key, value, row['result'][key])
    return {'passed': True, 'rows': len(rows), 'distance': result.stopping_m, 'medal': result.medal}


def finish(app, workspace):
    for _ in range(30):
        app.taskMgr.step()
        if app._workspace_steps is None:
            break
    assert app.workspace == workspace and app._workspace_steps is None
    app.taskMgr.remove('lab-update' if workspace == 'lab' else 'drive-update')


def check(output, size, restore=False, road_ab=False):
    output.mkdir(parents=True, exist_ok=restore)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    summary = {'passed': False, 'source_start': sources(), 'runtime_start': runtime_fingerprint(),
               'restore': restore, 'road_ab': road_ab, 'cases': [], 'size': size, 'human_gate': 'pending'}
    path = output/'test-workspace-vehicle.json'
    if restore:
        car = WorkspaceVehicle.load(path)
        scores = output/'short-braking-best.json'
        old = scores.read_bytes()
        app = CoastalDrive(smoke=True, output=output, workspace_vehicle=car,
                           render_size=tuple(size), independent_clock=True)
        app.taskMgr.remove('finish-smoke')
        app.taskMgr.remove('drive-update')
        try:
            app.session.start(countdown=False, mode=GameMode.SHORT_BRAKING, track='endless', settle_initial=True)
            app.session.pause()
            result = app.session.highway.snapshot.braking
            expected = json.loads((output/'summary.json').read_text(encoding='utf-8'))['cases'][-1]['result']['stopping_m']
            assert result.short and result.best_distance == expected and scores.read_bytes() == old
            app.back_to_menu()
            app.choose_braking_lesson(GameMode.SHORT_BRAKING)
            app.open_brake_tuning()
            if road_ab:
                ab = app.player_brake_ab
                old_ab, old_tires = ab.path.read_bytes(), app.player_road_ab.path.read_bytes()
                assert ab.a['config']['front_brake_share'] == .45 and ab.b['config']['front_brake_share'] == .70
                assert ab.b['result']['stopping_m'] == expected
                app.tire_tuning.activate(7)
                app.main_menu.resize(app.getAspectRatio())
                for _ in range(6):
                    app.taskMgr.step()
                app.graphicsEngine.syncFrame()
                assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/'reopened-brake-ab.png')))
                assert ab.path.read_bytes() == old_ab and app.player_road_ab.path.read_bytes() == old_tires
                app.player_road_panel.hide()
                summary.update(comparison_restored=True, comparison_unchanged=True, tires_unchanged=True)
            app.tire_tuning.activate(5)
            assert app.workspace_vehicle == WorkspaceVehicle.load(output/'original-vehicle.json')
            assert scores.read_bytes() == old
            summary.update(passed=True, pid=app.session.process.pid, best_restored=expected,
                scores_unchanged=True, original_restored=True, scope='实际独立120Hz进程恢复新结果/最佳及对照，再恢复完整原车；无新完整驾驶')
        finally:
            app.close_game()
            summary.update(source_end=sources(), runtime_end=runtime_fingerprint())
            assert summary['source_start'] == summary['source_end'] and summary['runtime_start'] == summary['runtime_end']
            (output/'restore-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'passed': True, 'restore': True}
    if road_ab:
        sdk = 'normal' if summary['runtime_start']['math_scalar_bits'] == 32 else 'double'
        source = ROOT/f'docs/evidence/PLAYER-ROAD-AB-01/{sdk}/player-road-ab.json'
        (output/'player-road-ab.json').write_bytes(source.read_bytes())
        summary['tire_input'] = {'source': str(source.relative_to(ROOT)), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    car = WorkspaceVehicle('reference-rwd', build_config(0, False))
    car.save(output/'original-vehicle.json')
    car.save(path)
    app = CoastalDrive(smoke=True, output=output, lab_output=output/'reports', workspace_vehicle=car, render_size=tuple(size))
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    window = app.win
    old_tires = app.player_road_ab.path.read_bytes() if road_ab else None

    def capture(name):
        if app.workspace == 'lab':
            app.lab.resize()
        else:
            app.main_menu.resize(app.getAspectRatio())
            app.hud.resize(app.getAspectRatio())
            app.lab_return_button.setX(app.getAspectRatio()-.44)
            app.ghost_button.setX(app.getAspectRatio()-.44)
            if app.scene is not None:
                app.chase_camera.position = None
                app.apply_scene(app.session.current, 0.)
                app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                               track='endless', countdown='', notice='')
            if app.tire_tuning.root.isHidden():
                app._shown_phase = None
                app.refresh_panel()
        before = app.session.current if app.workspace == 'game' else None
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        if before is not None:
            assert app.session.current == before
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))

    try:
        app.back_to_menu()
        app.choose_braking_lesson()
        capture('precision-rules')
        app.buttons[1]['command']()
        capture('short-rules')
        app.buttons[0]['command']()
        for index in (0, 2):
            for _ in range(360):
                app.session.tick()
            assert app.session.phase == Phase.DRIVING and app.session.mode == GameMode.SHORT_BRAKING
            config, variant = app.session.vehicle_config, app.session.score_variant()
            assert config.front_brake_share == (.45 if index == 0 else .70)
            start = app.session.highway.snapshot.braking.start_progress
            braking, rows, captured = False, [], False
            for _ in range(3602):
                state, result = app.session.current, app.session.highway.snapshot.braking
                if result.position >= 100.:
                    braking = True
                # 降至低速后提前松S，沿用原踏板和倒车规则。
                desired = ('s' if state.player.velocity[1] > 1. else '') if braking else ('w' if state.player.speed < 82.5/3.6 else '')
                for key in ('w', 's'):
                    app.session.keyboard.press(key) if key == desired else app.session.keyboard.release(key)
                app.session.tick()
                state, result = app.session.current, app.session.highway.snapshot.braking
                rows.append({'tick': state.tick, 'elapsed': app.session.highway.snapshot.elapsed,
                    'position': state.player.position, 'velocity': state.player.velocity, 'heading': state.player.heading,
                    'speed': math.hypot(*state.player.velocity[:2]), 'collisions': state.collisions,
                    'keys': sorted(app.session.keyboard.pressed), 'request': asdict(app.session.last_control), 'result': asdict(result)})
                if result.position > 108. and not captured:
                    capture(f'{index}-braking')
                    captured = True
                if result.finished:
                    break
            folder = output/str(index)
            folder.mkdir()
            with gzip.open(folder/'raw.json.gz', 'wt', encoding='utf-8') as stream:
                json.dump(rows, stream, ensure_ascii=False)
            case = {'rows': len(rows), 'config': asdict(config), 'variant': variant, 'start_progress': start, 'result': asdict(result)}
            (folder/'summary.json').write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding='utf-8')
            summary['cases'].append(case)
            checked = recheck(folder)
            (folder/'recheck.json').write_text(json.dumps(checked, indent=2), encoding='utf-8')
            assert result.succeeded and result.medal == ('铜' if index == 0 else '银') and app.win is window
            capture(f'{index}-result')
            if index == 2 and road_ab:
                ab = app.player_brake_ab
                assert ab.a['config']['front_brake_share'] == .45 and ab.b['config']['front_brake_share'] == .70
                assert ab.a['result'] == summary['cases'][0]['result'] and ab.b['result'] == asdict(result)
                old_ab, old_best = ab.path.read_bytes(), (output/'short-braking-best.json').read_bytes()
                app.buttons[3]['command']()
                app.tire_tuning.activate(7)
                assert 'B−A -4.32' in app.player_road_panel.delta.getText()
                capture('brake-road-ab')
                app.player_road_panel.hide()
                app.tire_tuning.activate(6)
                assert ab.path.read_bytes() == old_ab and (output/'short-braking-best.json').read_bytes() == old_best
                summary['comparison'] = {'A': ab.a, 'B': ab.b, 'read_only': True}
            if index == 0:
                app.buttons[3]['command']()
                app.tire_tuning.activate(2)
                capture('preview-70')
                assert app.session.phase == Phase.RESULTS and app.session.vehicle_config == config
                app.tire_tuning.activate(4)
                capture('installed-70')
                assert app.session.phase == Phase.MENU and app.braking_mode == GameMode.SHORT_BRAKING
                app.tire_tuning.activate(6)
                app.buttons[0]['command']()
        app.open_vehicle_lab()
        finish(app, 'lab')
        assert app.lab.engineered_config.front_brake_share == .70
        capture('lab-current-car')
        app.lab.back_to_game()
        finish(app, 'game')
        assert app.win is window and app.session.mode == GameMode.SHORT_BRAKING
        for _ in range(360):
            app.session.tick()
        assert app.session.highway.snapshot.braking.best_distance == result.stopping_m
        assert not (output/'braking-best.json').exists()
        if road_ab:
            assert app.player_road_ab.path.read_bytes() == old_tires
        else:
            assert app.player_road_ab.a is None
        summary.update(passed=True, same_window=True, returns_to_short=True,
            rows=sum(case['rows'] for case in summary['cases']),
            scope='新真实KeyboardController，同一82.5km/h目标/过门后制动，45%铜→结果改70%银；非人工驾驶或纯80–0试验')
        return {'passed': True, 'bits': summary['runtime_start']['math_scalar_bits'], 'rows': summary['rows']}
    finally:
        summary.update(source_end=sources(), runtime_end=runtime_fingerprint())
        assert summary['source_start'] == summary['source_end'] and summary['runtime_start'] == summary['runtime_end']
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--road-ab', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.restore, args.road_ab), ensure_ascii=False))
