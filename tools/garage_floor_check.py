"""采集七车地面反射、开关像素对照与静态显示耗时，不推进驾驶。"""

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

from panda3d.core import Filename, Point2, Point3

from application import CoastalDrive
from career import EVENTS
from career_garage import GARAGE_CARS
from career_run import CareerResult


def check(output, size):
    output.mkdir(parents=True, exist_ok=False)
    os.environ['LOCALAPPDATA'] = str(output/'user')
    app = CoastalDrive(smoke=True, output=output, render_size=size)
    app.taskMgr.remove('finish-smoke')
    app.taskMgr.remove('drive-update')
    before = asdict(app.session.current)
    files, models = [], []

    def draw():
        for _ in range(8):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        assert asdict(app.session.current) == before

    def shot(name):
        draw()
        app.win.getScreenshot().write(Filename.fromOsSpecific(str(output/name)))
        files.append(name)

    try:
        for event in EVENTS:
            app.career_progress.record(CareerResult(event.id, 8., elapsed=25., finished=True, succeeded=True, stars=3))
        app.open_career_collection()
        view = app.workshop_vehicle
        for car in GARAGE_CARS:
            app.career_action('garage-car', car.design_id)
            assert len(view.scene.findAllMatches('garage-floor-reflection')) == 1
            reflection = view.floor_reflection
            draw()
            assert view.floor_reflection == reflection
            assert not reflection.isHidden()
            shot(car.design_id+'.png')
            models.append({'design': car.design_id, 'reflection_passes': reflection.getNumChildren()})
        app.career_action('garage-car', 'game-tuned')
        shot('reflection-on.png')
        reflected = view.floor_reflection
        view.buffer.getScreenshot().write(Filename.fromOsSpecific(str(output/'buffer-on.png')))
        reflected.hide()
        shot('reflection-off.png')
        view.buffer.getScreenshot().write(Filename.fromOsSpecific(str(output/'buffer-off.png')))
        on = np.asarray(Image.open(output/'buffer-on.png').convert('RGB')).astype(float)
        off = np.asarray(Image.open(output/'buffer-off.png').convert('RGB')).astype(float)
        changed = np.max(abs(on-off), axis=2) > 2
        assert changed.sum() > 100
        low, high = view.car_root.getTightBounds(view.scene)
        ground = []
        for x in (low.x, high.x):
            for y in (low.y, high.y):
                point = Point2()
                camera_point = view.camera.getRelativePoint(view.scene, Point3(x, y, 0))
                assert camera_point.y > view.camera.node().getLens().getNear()
                # 地面空角可超出视口；project仍给出坐标，不能将不可见误判为无投影。
                view.camera.node().getLens().project(camera_point, point)
                ground.append((1-point.y)*on.shape[0]/2)
        floor_top = max(0, int(min(ground))-2)
        assert not changed[:floor_top].any()
        timings = {}
        for design_id in ('game-tuned', 'coastal-roadster'):
            app.career_action('garage-car', design_id)
            reflected = view.floor_reflection
            timings[design_id] = {}
            for enabled in (False, True):
                reflected.show() if enabled else reflected.hide()
                draw()
                wall, cpu = [], []
                total_cpu_start = time.thread_time()
                for _ in range(48):
                    started, started_cpu = time.perf_counter(), time.thread_time()
                    app.taskMgr.step()
                    app.graphicsEngine.syncFrame()
                    wall.append((time.perf_counter()-started)*1000)
                    cpu.append((time.thread_time()-started_cpu)*1000)
                timings[design_id]['on' if enabled else 'off'] = {
                    'samples': len(wall), 'wall_median_ms': float(np.median(wall)),
                    'wall_p95_ms': float(np.percentile(wall, 95)), 'main_thread_cpu_median_ms': float(np.median(cpu)),
                    'main_thread_cpu_total_ms': (time.thread_time()-total_cpu_start)*1000}
        assert asdict(app.session.current) == before
        report = {'passed': True, 'size': size, 'captures': files, 'models': models,
            'changed_buffer_pixels': int(changed.sum()), 'unchanged_above_ground_row': floor_top,
            'timings': timings, 'new_driving_steps': 0,
            'scope': '隔离18星夹具；静态显示开关诊断，不是正式运行性能或人工审美验收'}
        (output/'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))
    finally:
        app.close_game()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--size', nargs=2, type=int, default=(1280, 720))
    args = parser.parse_args()
    check(args.output.resolve(), tuple(args.size))
