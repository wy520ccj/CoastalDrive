"""独立物理进程只读载入实际道路A/B图解；边界图明确使用显示夹具。"""

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
from lab_records import model_fingerprint
from lab_runtime import runtime_fingerprint
from player_road_ab import BRAKE_VERSION, PlayerRoadAB, document
from race import GameMode
from vehicle_workspace import WorkspaceVehicle


def sources():
    names = ('src/ui/player_road_ab.py', 'src/ui/player_road_diagram.py', 'tools/player_road_diagram_check.py')
    return {**model_fingerprint(), **{name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}}


def check(output, size):
    output.mkdir(parents=True)
    os.environ['LOCALAPPDATA'] = str(output/'user-data')
    summary = {'passed': False, 'source_start': sources(), 'runtime_start': runtime_fingerprint(),
               'scope': '独立进程静态读取实际A/B，无新完整驾驶；fixture图片为明确显示夹具', 'size': size, 'images': []}
    sdk = 'normal' if summary['runtime_start']['math_scalar_bits'] == 32 else 'double'
    inputs = {}
    for task, name in [('PLAYER-ROAD-AB-01', 'player-road-ab.json'), ('BRAKE-ROAD-AB-01', 'player-braking-ab.json')]:
        source = ROOT/f'docs/evidence/{task}/{sdk}/{name}'
        (output/name).write_bytes(source.read_bytes())
        inputs[name] = {'source': str(source.relative_to(ROOT)), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    summary['inputs'] = inputs
    car = WorkspaceVehicle.load(ROOT/f'docs/evidence/BRAKE-ROAD-AB-01/{sdk}/original-vehicle.json')
    app = CoastalDrive(smoke=True, output=output, workspace_vehicle=car, render_size=tuple(size), independent_clock=True)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    app.back_to_menu()
    before = app.session.current

    def capture(name, scope):
        app.main_menu.resize(app.getAspectRatio())
        for _ in range(6):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert app.session.current == before
        assert app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/(name+'.png'))))
        summary['images'].append({'name': name, 'scope': scope, 'readout': app.player_road_panel.diagram.detail.getText()})

    def show(store):
        if store.brakes:
            app.player_brake_ab = store
            mode = GameMode.SHORT_BRAKING if store.a is None or store.a['result']['short'] else GameMode.BRAKING_LESSON
            app.choose_braking_lesson(mode)
            app.open_brake_tuning()
        else:
            app.player_road_ab = store
            app.choose_slalom_lesson(GameMode.FAST_SLALOM)
            app.open_tire_tuning()
        app.tire_tuning.activate(7)
        assert app.player_road_panel.graph

    def fixture(name, a, b):
        path = output/(name+'.json')
        path.write_text(json.dumps({'version': BRAKE_VERSION, 'A': a, 'B': b, 'target': brake.target},
                                   ensure_ascii=False, indent=2), encoding='utf-8')
        return PlayerRoadAB(path, brakes=True)

    try:
        brake = app.player_brake_ab
        show(app.player_road_ab)
        assert app.player_road_panel.diagram.selected == 2
        capture('slalom-focus', '实际35k漏第3门/70k完成的结束记录')
        app.key_down('arrow_right')
        app.key_up('arrow_right')
        assert 'A 未到达' in app.player_road_panel.diagram.detail.getText()
        capture('slalom-next', '实际记录，第4门A未到达，保留B真实余量')
        app.key_down('space')
        app.key_up('space')
        capture('slalom-table', '同一实际六门数值表')
        show(brake)
        capture('brake-distance', '实际45%铜/70%银的最大前进位置')
        app.key_down('space')
        app.key_up('space')
        capture('brake-table', '同一实际制动数值表')
        a, b = document(brake.a), document(brake.b)
        for item, position, error, medal in [(a, 162., -8., '铜'), (b, 172., 2., '金')]:
            item['context']['mode'] = GameMode.BRAKING_LESSON.value
            item['result'].update(short=False, position=position, error_m=error, stopping_m=None, medal=medal,
                                  reason='显示夹具 · 定点停车位置', best_error=abs(error), best_distance=None)
        show(fixture('fixture-precision', a, b))
        capture('fixture-precision', '明确显示夹具：定点162/172米，不是新实际驾驶')
        a = document(brake.a)
        a['result'].update(succeeded=False, medal='', position=60., entry_kph=None, stopping_m=None,
                           hold_seconds=0., reason='显示夹具 · 过门前结束')
        show(fixture('fixture-before-gate', a, None))
        capture('fixture-before-gate', '明确显示夹具：未过门不生成最大前进点')
        a = document(brake.a)
        a['result'].update(succeeded=False, medal='', position=143., stopping_m=43., hold_seconds=0.,
                           reason='显示夹具 · 超过停车线')
        show(fixture('fixture-overrun', a, document(brake.b)))
        capture('fixture-overrun', '明确显示夹具：失败43米空心点与实际B位置同轴，不生成成绩差')
        for name, item in inputs.items():
            assert hashlib.sha256((output/name).read_bytes()).hexdigest() == item['sha256']
        assert app.session.current == before
        summary.update(passed=True, pid=app.session.process.pid, inputs_unchanged=True, snapshot_unchanged=True, human_gate='pending')
        return {'passed': True, 'bits': summary['runtime_start']['math_scalar_bits'], 'images': len(summary['images'])}
    finally:
        app.close_game()
        summary.update(source_end=sources(), runtime_end=runtime_fingerprint())
        assert summary['source_start'] == summary['source_end'] and summary['runtime_start'] == summary['runtime_end']
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', type=int, nargs=2, default=(1280, 720))
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.size), ensure_ascii=False))
