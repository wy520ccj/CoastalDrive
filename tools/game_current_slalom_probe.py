"""按game-current的配置、加载生成器和独立物理进程检查持续W起步。"""

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename

from application import CoastalDrive
from driving_modes import DrivingMode
from race import GameMode
from session import Phase
from settings import AppearanceStore, DrivingModeStore
from skins import vehicle_definition
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle, workspace_vehicle_path


def check(output, timing):
    output.mkdir(parents=True, exist_ok=False)
    original_path = workspace_vehicle_path()
    original = original_path.read_bytes() if original_path.exists() else None
    vehicle = WorkspaceVehicle.load()
    settings, appearance = DrivingModeStore(), AppearanceStore()
    if vehicle is None:
        design = vehicle_design(vehicle_definition(appearance.model_id).physics_id)
        config = DrivingMode.GAME.configured_vehicle(settings.abs_enabled, settings.tcs_enabled,
                                                     settings.esc_enabled, base_config=design.config)
        vehicle = WorkspaceVehicle(design.id, config)
    os.environ['LOCALAPPDATA'] = str(output/'isolated-user')
    app = CoastalDrive(smoke=True, independent_clock=True, driving_mode=DrivingMode.GAME,
                       output=output, workspace_vehicle=vehicle, render_size=(1280, 720))
    app.taskMgr.remove('finish-smoke')
    rows, sent, last_tick, input_phase = [], False, -1, None
    try:
        app.back_to_menu()
        app.choose_slalom_lesson(GameMode.FAST_SLALOM)
        app.slalom_menu = app.highway_menu = False
        app.session.road_shape = 'straight'
        # 正式入口使用此生成器；离屏仅免去OS前台焦点，不改物理时钟或控制链。
        app._begin_workspace(app._load_road(GameMode.FAST_SLALOM, 'endless'), '起步复现', '原车持续W')
        if timing == 'loading':
            app.messenger.send('w')
            sent = True
            input_phase = app.session.phase.value
        deadline = time.monotonic()+65.
        while time.monotonic() < deadline:
            app.taskMgr.step()
            if (not sent and app.workspace == 'game' and app._workspace_steps is None
                    and app.session.phase in (Phase.COUNTDOWN, Phase.DRIVING)):
                app.messenger.send('w')
                sent = True
                input_phase = app.session.phase.value
            if app.workspace != 'game':
                continue
            state, result = app.session.current, app.session.highway.snapshot.slalom
            if result is not None and state.tick != last_tick:
                last_tick = state.tick
                rows.append({'tick': state.tick, 'phase': app.session.phase.value,
                             'position': result.position, 'speed_kph': state.player.speed*3.6,
                             'forward_kph': state.player.velocity[1]*3.6,
                             'keys': sorted(app.driving_keys_held),
                             'throttle': state.player.throttle, 'brake': state.player.brake,
                             'published_input_word': app.session.keyboard.input_word.value})
            if app.session.phase == Phase.RESULTS:
                break
        app.taskMgr.remove('drive-update')
        app._shown_phase = None
        app.refresh_panel()
        for _ in range(3):
            app.graphicsEngine.renderFrame()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/'result.png')))
        result = app.session.highway.snapshot.slalom
        document = {'finished': app.session.phase == Phase.RESULTS, 'input_timing': timing,
                    'input_phase': input_phase,
                    'session_type': type(app.session).__name__, 'mode': app.session.driving_mode.value,
                    'vehicle_id': vehicle.design_id, 'config': asdict(app.session.vehicle_config),
                    'launcher_sha': hashlib.sha256((ROOT/'launchers/game-current.cmd').read_bytes()).hexdigest(),
                    'result': asdict(result) if result is not None else None, 'samples': rows,
                    'scope': '正式加载生成器+独立时钟+实际Messenger按键；离屏无OS焦点，非人工驾驶'}
        (output/'summary.json').write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
        if original is not None:
            assert original_path.read_bytes() == original
        else:
            assert not original_path.exists()
        return {key: document[key] for key in ('finished', 'input_timing', 'session_type', 'vehicle_id', 'result')}
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--input-timing', choices=('ready', 'loading'), default='ready')
    args = parser.parse_args()
    print(json.dumps(check(args.output.resolve(), args.input_timing), ensure_ascii=False))
