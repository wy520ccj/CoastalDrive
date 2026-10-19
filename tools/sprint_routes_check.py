"""两路线实际键盘驾驶/逐拍规则复核/界面与独立物理进程恢复。"""

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename
from slalom_driver import apply_keys
from sprint_route_probe import SprintDriver

from application import CoastalDrive
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from race import BestTimes, GameMode
from session import Phase
from simulation import FIXED_DT
from sprint_routes import SPRINT_ROUTES
from sprint_run import SprintRun
from traffic import Road
from vehicle_config import CAR
from vehicle_parameters import config_from_document


def recheck(folder):
    summary = json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    checked = 0
    for case in summary['cases']:
        mode = GameMode(case['mode'])
        route = SPRINT_ROUTES[mode]
        config = config_from_document(case['config'], CAR)
        road = Road('endless', seed=route.seed, shape=route.shape)
        with gzip.open(folder/case['record'], 'rt', encoding='utf-8') as stream:
            rows = json.load(stream)
        with tempfile.TemporaryDirectory() as temporary:
            item = SprintRun(case['start_progress'], mode, BestTimes(Path(temporary)/'best.json'), case['variant'], config)
            elapsed = 0.
            for row in rows:
                x, y, _z = row['position']
                progress, lateral = road.curve.project((x, y+row['origin_y']))
                point = road.curve.sample(progress)
                heading = (row['heading']-point.heading+180)%360-180
                elapsed += FIXED_DT
                state = item.update(progress, elapsed, lateral=lateral, heading=heading,
                                    collisions=row['collisions'], reset='player_reset' in row['events'])
                assert json.loads(json.dumps(asdict(state))) == row['sprint'], (case['mode'], row['tick'])
                assert len(row['keys']) == len(set(row['keys'])) and not set(row['keys'])-{'w', 's', 'a', 'd'}
            assert json.loads(json.dumps(asdict(state))) == case['result']
            assert state.succeeded and state.medal == '金'
        for previous, current in pairwise(rows):
            assert current['tick'] == previous['tick']+1 and current['time'] > previous['time']
        assert rows[0]['tick'] == case['initial_tick']+1
        assert case['record_sha256'] == hashlib.sha256((folder/case['record']).read_bytes()).hexdigest()
        checked += len(rows)
    return {'passed': True, 'rows': checked, 'scope': '从保存的真实位置/朝向重新投影道路并逐拍复算规则；不重跑物理'}


def check(output, size, restore):
    output.mkdir(parents=True, exist_ok=restore)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    source, runtime = model_fingerprint(), runtime_fingerprint()
    prior = json.loads((output/'summary.json').read_text(encoding='utf-8')) if restore else None
    best_path = output/'sprint-best.json'
    old_bytes = best_path.read_bytes() if restore else None
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size), independent_clock=restore)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    cases, captures = [], []

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        if app.scene is not None:
            app.chase_camera.position = None
            app.apply_scene(app.session.current, 0.)
            app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                           track=app.session.simulation.track, countdown='', notice='')
        app.refresh_panel()
        before = app.session.current
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.session.current == before
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        captures.append(name)

    try:
        app.back_to_menu()
        app._shown_phase = None
        app.refresh_panel()
        capture('restore-main-menu' if restore else 'main-menu')
        app.choose_highway()
        capture('restore-highway-menu' if restore else 'highway-menu')
        app.buttons[6]['command']()
        capture('restore-routes' if restore else 'routes')
        for index, (mode, route) in enumerate(SPRINT_ROUTES.items()):
            if index:
                app.back_to_menu()
                app.choose_sprint_routes()
            app.buttons[index]['command']()
            if restore:
                deadline = time.perf_counter()+20.
                while app.session.phase == Phase.COUNTDOWN and time.perf_counter() < deadline:
                    app.session.frame(0.)
                    time.sleep(.02)
                app.session.stop_clock()
                assert app.session.phase == Phase.DRIVING
                result = app.session.highway.snapshot.sprint
                expected = next(case for case in prior['cases'] if case['mode'] == mode.value)
                assert result.best_seconds == expected['result']['seconds']
                assert list(result.reference_times) == expected['result']['gate_times']
                assert app.session.seed == route.seed and app.session.road_shape == route.shape
                capture('restored-'+mode.value)
                cases.append({'mode': mode.value, 'best': result.best_seconds, 'reference': result.reference_times,
                              'session_pid': app.session.process.pid})
                continue
            for _ in range(360):
                app.session.tick()
            assert app.session.phase == Phase.DRIVING
            app.countdown.update('driving', 0, 0.)
            config = app.session.vehicle_config
            start_progress = app.session.highway.snapshot.sprint.start_progress
            initial_tick = app.session.current.tick
            driver = SprintDriver(app.session.simulation.road, config, 90.)
            rows, shown = [], set()
            for _ in range(180*120+2):
                apply_keys(app.session.keyboard, driver.sample(app.session.current, FIXED_DT))
                keys = sorted(app.session.keyboard.pressed)
                app.session.tick()
                state, result = app.session.current, app.session.highway.snapshot.sprint
                rows.append({'tick': state.tick, 'time': state.time, 'position': state.player.position,
                    'velocity': state.player.velocity, 'heading': state.player.heading, 'origin_y': state.origin_y,
                    'collisions': state.collisions, 'events': state.events, 'keys': keys,
                    'request': asdict(app.session.last_control), 'sprint': asdict(result)})
                for label, progress in (('first-bend', 275.), ('descent', 650.), ('next-bend', 1150.)):
                    if result.position >= progress and label not in shown:
                        capture(mode.value+'-'+label)
                        shown.add(label)
                if app.session.phase == Phase.RESULTS:
                    break
            name = mode.value+'.json.gz'
            with gzip.open(output/name, 'wt', encoding='utf-8') as stream:
                json.dump(rows, stream, ensure_ascii=False)
            case = {'mode': mode.value, 'route': asdict(route), 'config': asdict(config), 'variant': app.session.score_variant(),
                'input': asdict(app.session.keyboard.input_config), 'start_progress': start_progress, 'initial_tick': initial_tick,
                'record': name, 'record_sha256': hashlib.sha256((output/name).read_bytes()).hexdigest(),
                'result': asdict(result), 'rows': len(rows), 'collisions': state.collisions}
            cases.append(case)
            assert result.succeeded and result.medal == '金' and result.new_best and state.collisions == 0, case
            capture(mode.value+'-result')
            app.buttons[0]['command']()
            for _ in range(360):
                app.session.tick()
            retry = app.session.highway.snapshot.sprint
            assert retry.best_seconds == result.seconds and retry.reference_times == result.gate_times
            assert retry.gates == 0 and retry.seconds == 0.
            capture(mode.value+'-retry')
            print(json.dumps({'mode': mode.value, 'seconds': result.seconds, 'medal': result.medal, 'rows': len(rows)}), flush=True)
        source_end, runtime_end = model_fingerprint(), runtime_fingerprint()
        summary = {'passed': source == source_end and runtime == runtime_end,
            'source_start': source, 'source_end': source_end, 'runtime_start': runtime, 'runtime_end': runtime_end,
            'size': size, 'cases': cases, 'captures': captures, 'human_gate': 'pending',
            'driver': '实际KeyboardController二值按键请求；非人工驾驶',
            'scope': '独立物理进程重启/正常菜单/两赛事最佳恢复，无新完整驾驶' if restore else '两路线新实际键盘驾驶与实际离屏界面'}
        if restore:
            assert best_path.read_bytes() == old_bytes
            summary['best_file_unchanged'] = True
        target = output/('restore-summary.json' if restore else 'summary.json')
        target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        assert summary['passed']
        if not restore:
            verified = recheck(output)
            (output/'recheck.json').write_text(json.dumps(verified, ensure_ascii=False, indent=2), encoding='utf-8')
        return {'passed': True, 'bits': runtime['math_scalar_bits'], 'cases': len(cases), 'restore': restore}
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    print(json.dumps(recheck(args.output.resolve()) if args.verify else check(args.output.resolve(), args.size, args.restore), ensure_ascii=False))
