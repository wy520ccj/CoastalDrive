"""真实原生交通挑战、每完成步规则复算、离屏图及独立物理进程成绩恢复。"""

import argparse
import gzip
import hashlib
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from overtake_probe import car_record
from panda3d.core import Filename
from slalom_driver import apply_keys
from sprint_route_probe import SprintDriver

from application import CoastalDrive
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from overtake_routes import OVERTAKE_ROUTES
from overtake_run import OvertakeRun
from race import BestTimes, GameMode
from road_test_driver import OvertakeDriver
from session import Phase
from simulation import FIXED_DT, Snapshot
from traffic import Road
from vehicle_config import CAR
from vehicle_parameters import config_from_document
from vehicle_state import CarState


def sources():
    result = model_fingerprint()
    for name in ('src/ui/hud.py', 'src/ui/overtake_feedback.py', 'tools/overtake_check.py',
                 'tools/overtake_probe.py', 'tools/sprint_route_probe.py', 'tools/slalom_driver.py'):
        result[name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    return result


def record(state):
    return {'tick': state.tick, 'time': state.time, 'origin_y': state.origin_y,
            'player': car_record(state.player), 'traffic': [car_record(car) for car in state.traffic],
            'collisions': state.collisions, 'events': state.events}


def snapshot(row):
    return Snapshot(row['tick'], row['time'], CarState(**row['player']),
                    tuple(CarState(**car) for car in row['traffic']), tuple(row['events']), row['origin_y'], row['collisions'])


def recheck(folder):
    summary = json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    with gzip.open(folder/'raw.json.gz', 'rt', encoding='utf-8') as stream:
        rows = json.load(stream)
    config = config_from_document(summary['config'], CAR)
    mode = GameMode(summary.get('mode', 'safe_overtake'))
    route = OVERTAKE_ROUTES[mode]
    road = Road('endless', seed=route.seed, shape=route.shape)
    road.origin_y = summary['initial']['origin_y']
    with tempfile.TemporaryDirectory() as temporary:
        item = OvertakeRun(snapshot(summary['initial']), config, BestTimes(Path(temporary)/'best.json'), summary['variant'], mode=mode, road=road)
        elapsed = 0.
        reading_kinds = set()
        previous_tick = summary['initial']['tick']
        for row in rows:
            assert row['tick'] == previous_tick+1
            previous_tick = row['tick']
            elapsed += FIXED_DT
            road.origin_y = row['origin_y']
            state = item.update(snapshot(row), elapsed, reset='player_reset' in row['events'])
            if state.traffic_reading is not None:
                reading_kinds.add(state.traffic_reading.kind)
            current = json.loads(json.dumps(asdict(state)))
            assert set(current)-set(row['result']) <= {'route_id', 'traffic_reading', 'incident'}
            assert {key: current[key] for key in row['result']} == row['result'], row['tick']
        assert {key: current[key] for key in summary['result']} == summary['result']
        assert state.succeeded == summary['expected_succeeded']
    assert hashlib.sha256((folder/'raw.json.gz').read_bytes()).hexdigest() == summary['record_sha256']
    return {'passed': True, 'rows': len(rows), 'reading_kinds': sorted(reading_kinds),
            'incident': asdict(state.incident) if state.incident is not None else None,
            'scope': '从保存真实位置/朝向/代次/速度逐拍重算规则，不重跑物理'}


def check(output, size, unsafe, restore, mode=GameMode.SAFE_OVERTAKE, follow=False):
    route = OVERTAKE_ROUTES[mode]
    output.mkdir(parents=True, exist_ok=restore)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    source, runtime = sources(), runtime_fingerprint()
    context = output/('restore-context.json' if restore else 'capture-context.json')
    context.write_text(json.dumps({'source_start': source, 'runtime_start': runtime}, indent=2), encoding='utf-8')
    prior = json.loads((output/'summary.json').read_text(encoding='utf-8')) if restore else None
    best_path = output/'overtake-best.json'
    best_bytes = best_path.read_bytes() if restore else None
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size), independent_clock=restore)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        if app.scene is not None:
            # 脱离渲染循环快进后补完实际美术段；单次3ms预算不足以完成全部节点。
            app.scene.sync_segments()
            app.chase_camera.position = None
            app.apply_scene(app.session.current, 0.)
            app.hud.update(app.session.current, app.session.race.snapshot, app.session.highway.snapshot,
                           track=app.session.simulation.track, countdown='', notice='')
        app._shown_phase = None
        app.refresh_panel()
        before = app.session.current
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.session.current == before
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))

    try:
        app.back_to_menu()
        capture('restore-main' if restore else 'main')
        app.choose_highway()
        app.buttons[6]['command']()
        capture('restore-events' if restore else 'events')
        app.buttons[3 if mode == GameMode.SAFE_OVERTAKE else 4]['command']()
        capture('restore-rules' if restore else 'rules')
        app.buttons[0]['command']()
        if restore:
            deadline = time.perf_counter()+25.
            while app.session.phase == Phase.COUNTDOWN and time.perf_counter() < deadline:
                app.session.frame(0.)
                time.sleep(.02)
            app.session.stop_clock()
            assert app.session.phase == Phase.DRIVING
            result = app.session.highway.snapshot.overtake
            assert result.best_seconds == prior['result']['seconds']
            expected = prior['result']['pass_times']+([prior['result']['seconds']] if route.finish_at_end else [])
            assert list(result.reference_times) == expected
            assert len(app.session.current.traffic) == 12 and app.session.seed == route.seed and app.session.road_shape == route.shape
            capture('restored')
            assert best_path.read_bytes() == best_bytes
            summary = {'passed': True, 'pid': app.session.process.pid, 'result': asdict(result),
                       'best_file_unchanged': True, 'scope': '实际独立进程/菜单恢复，无新完整驾驶'}
        else:
            for _ in range(360):
                app.session.tick()
            assert app.session.phase == Phase.DRIVING
            app.countdown.update('driving', 0, 0.)
            config = app.session.vehicle_config
            initial = record(app.session.current)
            if unsafe:
                driver = SprintDriver(app.session.simulation.road, config, 130.)
            else:
                driver = OvertakeDriver(app.session.simulation.road, config, app.session.keyboard.input_config, 20. if follow else 40.)
                app.session.set_controller(driver)
            capture('driving')
            rows, shown, qualified, near_finish, warned = [], False, False, False, False
            for _ in range(round(route.seconds*120)+2):
                if unsafe:
                    apply_keys(app.session.keyboard, driver.sample(app.session.current, FIXED_DT))
                app.session.tick()
                result = app.session.highway.snapshot.overtake
                row = record(app.session.current)
                row.update(control=asdict(app.session.last_control), result=asdict(result))
                rows.append(row)
                if result.traffic_reading is not None and result.traffic_reading.warning and not result.finished and not warned:
                    capture('clearance-warning')
                    warned = True
                if result.passes and not shown and not result.finished:
                    capture('first-pass')
                    shown = True
                if route.finish_at_end and not result.finished:
                    if result.passes == route.passes and not qualified:
                        capture('qualified-continue')
                        qualified = True
                    if result.distance >= route.distance-120. and not near_finish:
                        capture('near-finish')
                        near_finish = True
                if result.finished:
                    break
            with gzip.open(output/'raw.json.gz', 'wt', encoding='utf-8') as stream:
                json.dump(rows, stream, ensure_ascii=False)
            summary = {'initial': initial, 'config': asdict(config), 'variant': app.session.score_variant(),
                'mode': mode.value, 'route': asdict(route),
                'input': asdict(app.session.keyboard.input_config), 'expected_succeeded': not (unsafe or follow),
                'result': asdict(result), 'rows': len(rows), 'record_sha256': hashlib.sha256((output/'raw.json.gz').read_bytes()).hexdigest(),
                'driver': '原KeyboardController持续直行请求' if unsafe else '固定意图的原HighwayDriver，仅试车工具输出Control',
                'scope': '新实际原生交通驾驶/离屏图，非人工体验', 'human_gate': 'pending',
                'qualified_before_finish': qualified, 'follow_only': follow, 'rebases': app.session.simulation.rebases}
            (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
            capture('result')
            assert result.succeeded == (not (unsafe or follow)) and app.session.current.collisions == 0, result
            if unsafe:
                assert '间距不足' in result.reason and not best_path.exists()
            elif follow:
                assert '仅安全超越' in result.reason and not best_path.exists()
            else:
                assert result.new_best and result.passes == route.passes
                if route.finish_at_end:
                    assert qualified and result.distance >= route.distance
            app.buttons[0]['command']()
            for _ in range(360):
                app.session.tick()
            retry = app.session.highway.snapshot.overtake
            assert retry.passes == 0 and retry.seconds == 0.
            assert retry.best_seconds == result.best_seconds
            capture('retry')
            (output/'recheck.json').write_text(json.dumps(recheck(output), ensure_ascii=False, indent=2), encoding='utf-8')
        summary.update(source_start=source, source_end=sources(), runtime_start=runtime, runtime_end=runtime_fingerprint(), size=size)
        summary['passed'] = summary['source_start'] == summary['source_end'] and summary['runtime_start'] == summary['runtime_end']
        (output/('restore-summary.json' if restore else 'summary.json')).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        assert summary['passed']
        print(json.dumps({'passed': True, 'bits': runtime['math_scalar_bits'], 'restore': restore,
                          'seconds': summary['result']['seconds'], 'passes': summary['result']['passes']}), flush=True)
    finally:
        context.write_text(json.dumps({'source_start': source, 'source_end': sources(),
                           'runtime_start': runtime, 'runtime_end': runtime_fingerprint()}, indent=2), encoding='utf-8')
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    parser.add_argument('--unsafe', action='store_true')
    parser.add_argument('--restore', action='store_true')
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--mode', choices=[mode.value for mode in OVERTAKE_ROUTES], default=GameMode.SAFE_OVERTAKE.value)
    parser.add_argument('--follow', action='store_true')
    args = parser.parse_args()
    if args.verify:
        print(json.dumps(recheck(args.output.resolve()), ensure_ascii=False))
    else:
        check(args.output.resolve(), args.size, args.unsafe, args.restore, GameMode(args.mode), args.follow)
