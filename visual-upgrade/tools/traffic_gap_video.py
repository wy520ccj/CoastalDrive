"""按固定种子重放诊断时间段，保存实际离屏驾驶画面。"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from endurance_check import EnduranceDriver
from panda3d.core import ClockObject, Filename

from application import CoastalDrive
from race import GameMode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.start < 0 or args.end <= args.start:
        parser.error("要求 0 <= start < end")
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "frames.json").exists():
        parser.error("录像记录已存在")
    app = CoastalDrive(smoke=True, output=args.output, seed=args.seed,
                       track="endless", road_shape="hills")
    app.taskMgr.remove("finish-smoke")
    app.taskMgr.remove("drive-update")
    app.session.traffic_density = "busy"
    app.session.start(seed=args.seed, countdown=False, mode=GameMode.FREE_DRIVE)
    sim = app.session.simulation
    app.session.set_controller(EnduranceDriver(sim, args.seed + 701))
    app.clock.setMode(ClockObject.MNonRealTime)
    app.clock.setDt(1 / 60)
    frames = []
    task = type("Frame", (), {"cont": None})()
    try:
        while app.session.current.time < args.start:
            app.session.tick()
        app.sync_scene()
        app.chase_camera.position = None
        app._camera_origin = sim.origin_y
        frame = 0
        while app.session.current.time < args.end:
            app.taskMgr.step()
            app.update(task)
            app.graphicsEngine.renderFrame()
            if frame % 6 == 0:
                path = args.output / f"frame-{len(frames):05d}.png"
                app.win.saveScreenshot(Filename.fromOsSpecific(str(path)))
                state = app.session.current
                frames.append({"file": path.name, "tick": state.tick,
                               "time": round(state.time, 3),
                               "player_s": round(sim.road.locate(state.player)[0], 3)})
            frame += 1
        (args.output / "frames.json").write_text(json.dumps({
            "seed": args.seed, "start": args.start, "end": args.end,
            "density": "busy", "shape": "hills", "fps": 10,
            "frames": frames,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved {len(frames)} real rendered frames")
    finally:
        app.close_game()


if __name__ == "__main__":
    main()
