"""真实三站串联、逐拍原规则复核与独立重开；不修改物理状态或伪造玩家成绩。"""

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

from overtake_check import recheck as recheck_overtake
from overtake_check import record
from panda3d.core import Filename
from slalom_driver import apply_keys
from sprint_route_probe import SprintDriver
from sprint_routes_check import recheck as recheck_sprint

from application import CoastalDrive
from driving_tour import LEGS, DrivingTour, overall_medal, points
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from overtake_routes import OVERTAKE_ROUTES
from road_test_driver import OvertakeDriver
from session import Phase
from sprint_routes import SPRINT_ROUTES
from vehicle_state import FIXED_DT


def sources():
    paths = ('src/ui/driving_tour.py', 'src/ui/hud.py', 'src/ui/overtake_feedback.py',
             'tools/driving_tour_check.py', 'tools/overtake_probe.py', 'tools/sprint_route_probe.py',
             'tools/overtake_check.py', 'tools/sprint_routes_check.py', 'tools/slalom_driver.py')
    return {**model_fingerprint(), **{name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}}


def check(output, size, restore):
    output.mkdir(parents=True, exist_ok=restore)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    source, runtime = sources(), runtime_fingerprint()
    summary = {'passed': False, 'source_start': source, 'runtime_start': runtime, 'cases': [],
               'size': size, 'restore': restore, 'human_gate': 'pending'}
    path = output/'driving-tour.json'
    old_bytes = path.read_bytes() if restore else None
    app = CoastalDrive(smoke=True, output=output, render_size=tuple(size), independent_clock=restore)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    window = app.win

    def capture(name):
        app.main_menu.resize(app.getAspectRatio())
        app.hud.resize(app.getAspectRatio())
        app.lab_return_button.setX(app.getAspectRatio()-.44)
        app.ghost_button.setX(app.getAspectRatio()-.44)
        if app.scene is not None:
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
        app.open_driving_tour()
        capture('restored-tour' if restore else 'tour-start')
        if restore:
            assert len(app.tour_store.current) == len(app.tour_store.best) == 3
            assert path.read_bytes() == old_bytes
            summary.update(saved_best=[asdict(row) for row in app.tour_store.best], best_file_unchanged=True,
                           pid=app.session.process.pid, scope='另起实际独立SessionProcess与菜单读取三站完整记录；无新完整驾驶')
        else:
            variant = app.session.score_variant()
            config = app.session.vehicle_config
            app.tour_panel.activate(0)
            for index, mode in enumerate(LEGS):
                assert app.session.mode == mode and app.session.vehicle_config == config and app.win is window
                for _ in range(360):
                    app.session.tick()
                assert app.session.phase == Phase.DRIVING
                app.countdown.update('driving', 0, 0.)
                initial = record(app.session.current)
                sprint = mode in SPRINT_ROUTES
                route = SPRINT_ROUTES[mode] if sprint else OVERTAKE_ROUTES[mode]
                current = app.session.highway.snapshot.sprint if sprint else app.session.highway.snapshot.overtake
                start_progress = current.start_progress
                driver = (SprintDriver(app.session.simulation.road, config, 90., route=route, start_progress=start_progress) if sprint else
                          OvertakeDriver(app.session.simulation.road, config, app.session.keyboard.input_config, 40.))
                if not sprint:
                    app.session.set_controller(driver)
                capture(f'{index+1}-driving')
                rows = []
                for _ in range(180*120+2):
                    if sprint:
                        apply_keys(app.session.keyboard, driver.sample(app.session.current, FIXED_DT))
                    app.session.tick()
                    state = app.session.current
                    current = app.session.highway.snapshot.sprint if sprint else app.session.highway.snapshot.overtake
                    if sprint:
                        row = {'tick': state.tick, 'time': state.time, 'position': state.player.position,
                            'velocity': state.player.velocity, 'heading': state.player.heading, 'origin_y': state.origin_y,
                            'collisions': state.collisions, 'events': state.events, 'keys': sorted(app.session.keyboard.pressed),
                            'request': asdict(app.session.last_control), 'sprint': asdict(current)}
                    else:
                        row = record(state)
                        row.update(control=asdict(app.session.last_control), result=asdict(current))
                    rows.append(row)
                    if current.finished:
                        break
                folder = output/f'{index+1}-{mode.value}'
                folder.mkdir()
                with gzip.open(folder/'raw.json.gz', 'wt', encoding='utf-8') as stream:
                    json.dump(rows, stream, ensure_ascii=False)
                case = {'mode': mode.value, 'route': asdict(route), 'config': asdict(config), 'variant': variant,
                    'initial': initial, 'start_progress': start_progress, 'initial_tick': initial['tick'],
                    'record': 'raw.json.gz', 'record_sha256': hashlib.sha256((folder/'raw.json.gz').read_bytes()).hexdigest(),
                    'result': asdict(current), 'rows': len(rows), 'expected_succeeded': True}
                (folder/'summary.json').write_text(json.dumps({'cases': [case]} if sprint else case,
                                                              ensure_ascii=False, indent=2), encoding='utf-8')
                summary['cases'].append(case)
                capture(f'{index+1}-result')
                assert current.succeeded and current.medal and state.collisions == 0
                assert len(app.tour_store.current) == index+1
                recheck = recheck_sprint(folder) if sprint else recheck_overtake(folder)
                (folder/'recheck.json').write_text(json.dumps(recheck, ensure_ascii=False, indent=2), encoding='utf-8')
                loaded = DrivingTour(path, variant)
                assert loaded.current == app.tour_store.current
                if index < 2:
                    app.buttons[0]['command']()
            assert app.tour_store.best == app.tour_store.current and app.tour_store.new_best
            summary.update(points=points(app.tour_store.current), medal=overall_medal(app.tour_store.current),
                saved_best=[asdict(row) for row in app.tour_store.best], same_window=app.win is window,
                rows=sum(case['rows'] for case in summary['cases']),
                scope='新真实三站：前两站原二值KeyboardController、末站原HighwayDriver试车Control；非人工体验')
            app.buttons[1]['command']()
            capture('tour-complete')
        summary.update(source_end=sources(), runtime_end=runtime_fingerprint())
        assert summary['source_start'] == summary['source_end'] and runtime == runtime_fingerprint()
        summary['passed'] = True
        return {'passed': True, 'bits': runtime['math_scalar_bits'], 'restore': restore,
                'rows': summary.get('rows', 0), 'points': points(app.tour_store.current)}
    finally:
        summary.update(source_end=sources(), runtime_end=runtime_fingerprint())
        (output/('restore-summary.json' if restore else 'summary.json')).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size, args.restore), ensure_ascii=False))
