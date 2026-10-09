"""实际窗口/离屏检查起步动画与后台准备，截图属于渲染证据而非性能Gate。"""

import argparse
import ctypes
import json
import sys
import time
from ctypes import wintypes
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))

from panda3d.core import CallbackObject, Filename

from application import CoastalDrive
from driving_modes import DrivingMode
from session import GameMode, Phase


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=('game','simulation'),default='game')
    parser.add_argument('--onscreen',action='store_true')
    parser.add_argument('--no-images',action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    app = CoastalDrive(smoke=not args.onscreen,onscreen=args.onscreen,output=args.output,render_size=(1920,1080),
                       driving_mode=DrivingMode(args.mode),vehicle_design_id='gr86-2022-premium-6mt',
                       physics_workers=9,independent_clock=True,threading_model='/Draw' if args.onscreen else '')
    app.taskMgr.remove('finish-smoke')
    app.start_game(mode=GameMode.FREE_DRIVE,track='coastal')
    initial_tick = initial_remote = None
    if args.onscreen:
        user32 = ctypes.WinDLL('user32',use_last_error=True)
        user32.ShowWindow.argtypes = [wintypes.HWND,ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.IsIconic.argtypes = [wintypes.HWND]
        handle = app.win.getWindowHandle().getIntHandle()
        user32.ShowWindow(handle,9)
        user32.SetForegroundWindow(handle)
    rows,images = [],{}
    driving_at = None
    countdown_started_at = None
    started_at = time.perf_counter()
    draws = []

    def draw(data):
        if app.session.phase == Phase.COUNTDOWN:
            draws.append(time.perf_counter())
        data.upcall()

    region = max((region for region in app.win.getDisplayRegions() if region.isActive()),key=lambda region:region.getSort())
    region.setDrawCallback(CallbackObject.make(draw))

    def observe(task):
        nonlocal driving_at, countdown_started_at, initial_tick, initial_remote
        phase = app.session.phase
        now = time.perf_counter()
        if phase == Phase.COUNTDOWN and countdown_started_at is None:
            countdown_started_at = now
            initial_tick = app.session.current.tick
            initial_remote = app.session.simulation._physics_workers.remote_count
        elapsed = now-countdown_started_at if countdown_started_at is not None else None
        ticks = app.session.countdown_ticks
        pool = app.session.simulation._physics_workers
        rows.append({'wall':now-started_at,'countdown_wall':elapsed,'phase':phase.value,'ticks':ticks,'world_tick':app.session.current.tick,
                     'processes':len(pool.processes),'preparing':len(pool.preparing),'remote':pool.remote_count,
                     'player_z':app.session.current.player.position[2],
                     'race_elapsed':app.session.race.snapshot.elapsed,'settling':app.session._settling_initial,
                     'foreground':user32.GetForegroundWindow()==handle if args.onscreen else None,
                     'minimized':bool(user32.IsIconic(handle)) if args.onscreen else None})
        name = None
        if phase==Phase.COUNTDOWN:
            if 300<=ticks<=350:
                name = '3'
            elif 180<=ticks<=230:
                name = '2'
            elif 60<=ticks<=110:
                name = '1'
        elif phase==Phase.DRIVING:
            if driving_at is None:
                driving_at = elapsed
            if .1<elapsed-driving_at<.4:
                name = 'go'
        if not args.no_images and name is not None and name not in images:
            path = args.output / (name+'.png')
            app.win.saveScreenshot(Filename.fromOsSpecific(str(path.resolve())))
            images[name] = {'path':path.name,'wall':task.time,'ticks':ticks,'phase':phase.value}
        if (elapsed is not None and elapsed>5.5) or now-started_at>60.:
            app.session.stop_clock()
            frozen = [row for row in rows if row['phase']=='countdown']
            intervals = sorted((b-a)*1000 for a,b in pairwise(draws))
            result = {'mode':args.mode,'onscreen':args.onscreen,'images':images,'rows':rows,
                      'screenshot_readbacks':not args.no_images,
                      'countdown_draw':{'frames':len(draws),'fps':(len(draws)-1)/(draws[-1]-draws[0]),
                                        'p95_ms':intervals[int((len(intervals)-1)*.95)],'max_ms':max(intervals)} if intervals else {},
                      'driving_started_at':driving_at,'physics_workers':pool.diagnostics(),
                      'entry':'正常start_game/loading任务路径；首帧仍在Loading遮罩下',
                      'initialisation_tick':initial_tick,'initialisation_remote':initial_remote,
                      'settled_at_tick':app.session.simulation.initialisation_ticks,
                      'passed':(args.no_images or len(images)==4) and bool(frozen) and all(row['race_elapsed']==0. for row in frozen)
                          and not app.session._settling_initial and app.session.simulation.initialisation_ticks>0
                          and driving_at is not None and 2.8<=driving_at<=3.5,
                      'scope':'真实场景起步3秒与截图；有截图读回开销，不作为性能或人工Gate'}
            (args.output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False),flush=True)
            app.taskMgr.stop()
            return task.done
        return task.cont

    app.taskMgr.add(observe,'check-countdown')
    try:
        app.run()
    finally:
        app.close_game()
    report = json.loads((args.output/'report.json').read_text(encoding='utf-8'))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    from multiprocessing import freeze_support
    freeze_support()
    raise SystemExit(main())
