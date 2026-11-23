"""正常随车记录权威姿态、显示插值与相机；不改变物理或加视觉阻尼。"""

import argparse
import json
import multiprocessing
import time
from pathlib import Path

from check_interactive_local_drive import DrivingProbe, check
from panda3d.core import CallbackObject

from session import Phase
from session_clock import PRESENTATION_DELAY
from session_process import SessionProcess


def run(output, *, pipeline='/Draw', hd2_rocks=False, trace_draw=False):
    raw, display, frames, draws = {}, [], [], []
    original_update = SessionProcess._update
    original_frame = SessionProcess.frame
    original_apply = DrivingProbe.apply_scene
    original_initialize = DrivingProbe.__init__
    original_finish = DrivingProbe.probe_finish
    measuring, regions = [True], []

    def initialize(app, *args, **kwargs):
        original_initialize(app, *args, **kwargs)
        if not trace_draw:
            return
        region = max((r for r in app.win.getDisplayRegions() if r.isActive()), key=lambda r: r.getSort())

        def draw(data):
            if measuring[0] and app.probe_driver and app.scene is not None and app.session.phase == Phase.DRIVING:
                draws.append({'wall': time.perf_counter(), 'body': list(app.scene.player.getPos()),
                              'camera': list(app.camera.getPos())})
            data.upcall()

        region.setDrawCallback(CallbackObject.make(draw))
        regions.append(region)

    def finish(app):
        measuring[0] = False
        app.graphicsEngine.syncFrame()
        for region in regions:
            region.clearDrawCallback()
        original_finish(app)

    def update(session, value):
        original_update(session, value)
        if value.phase == Phase.DRIVING:
            for snapshot in value.history:
                car = snapshot.player
                raw[(snapshot.contact_epoch, snapshot.tick)] = {
                    'tick': snapshot.tick, 'time': snapshot.time, 'origin_y': snapshot.origin_y,
                    'position': list(car.position), 'hpr': [car.heading, car.pitch, car.roll],
                    'orientation': list(car.orientation), 'speed': car.speed,
                    'wheels': [list(wheel.position) for wheel in car.wheels]}

    def frame(session, elapsed, *, sampled_at=None):
        result = original_frame(session, elapsed, sampled_at=sampled_at)
        if session.phase == Phase.DRIVING:
            value = session.output
            stamp = time.perf_counter() if sampled_at is None else sampled_at
            wanted = stamp-value.timeline_origin-(value.dropped_time-value.dropped_epoch)-PRESENTATION_DELAY
            frames.append({'wanted_time': wanted, 'visible_time': result.time,
                           'latest_source_time': session.history[-1].time,
                           'oldest_source_time': session.history[0].time,
                           'source_times': [row.time for row in session.history],
                           'underflow_ms': max(0., wanted-session.history[-1].time)*1000})
        return result

    def apply(app, state, dt):
        original_apply(app, state, dt)
        if app.session.phase == Phase.DRIVING:
            car = state.player
            display.append({'wall': time.perf_counter(), 'tick': state.tick, 'time': state.time,
                'dt': dt, 'position': list(car.position), 'hpr': [car.heading, car.pitch, car.roll],
                'orientation': list(car.orientation), 'speed': car.speed,
                'wheels': [list(wheel.position) for wheel in car.wheels],
                'camera': list(app.camera.getPos()), 'camera_hpr': list(app.camera.getHpr()),
                'rendered_body': list(app.scene.player.getPos()),
                'unswept_camera': list(app.chase_camera.position),
                'car_in_camera': list(app.scene.player.getPos(app.camera)),
                'collisions': state.collisions, 'events': list(state.events)})

    SessionProcess._update, SessionProcess.frame, DrivingProbe.apply_scene = update, frame, apply
    DrivingProbe.__init__, DrivingProbe.probe_finish = initialize, finish
    try:
        check(output, False, False, hd2_rocks=hd2_rocks, threading_model=pipeline)
    finally:
        SessionProcess._update, SessionProcess.frame, DrivingProbe.apply_scene = original_update, original_frame, original_apply
        DrivingProbe.__init__, DrivingProbe.probe_finish = original_initialize, original_finish
        if output.exists():
            summary = {'scope': '正常山脊，原120Hz权威姿态与原显示/相机；未改输入或新增阻尼',
                       'threading_model': pipeline, 'hd2_rocks': hd2_rocks, 'trace_draw': trace_draw,
                       'raw': list(raw.values()), 'display': display, 'interpolation': frames, 'draw': draws}
            (output/'continuity.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pipeline', choices=('draw', 'cull-draw'), default='draw')
    parser.add_argument('--hd2-rocks', action='store_true')
    parser.add_argument('--trace-draw', action='store_true')
    arguments = parser.parse_args()
    run(arguments.output.resolve(), pipeline={'draw': '/Draw', 'cull-draw': 'Cull/Draw'}[arguments.pipeline],
        hd2_rocks=arguments.hd2_rocks, trace_draw=arguments.trace_draw)
