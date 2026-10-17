"""同一真实窗口连续往返；每个加载阶段留图并核对世界与工作区。"""

import argparse
import json
import multiprocessing
import os
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))

from direct.gui.DirectGuiBase import DirectGuiWidget
from panda3d.core import Filename, GraphicsWindow, KeyboardButton, WindowProperties

from application import CoastalDrive
from lab_experiment import LabOptions
from lab_records import LabRecord
from session import Phase


def require(condition, message):
    # 冻结发行包启用优化，不能把真实检查或截图副作用放进assert。
    if not condition:
        raise AssertionError(message)


def check(output, *, onscreen=False, independent=False):
    output.mkdir(parents=True, exist_ok=True)
    app = CoastalDrive(smoke=True, smoke_audio=True, onscreen=onscreen, output=output, lab_output=output/"records",
                       render_size=(1100, 740), independent_clock=independent)
    app.taskMgr.remove("finish-smoke")
    require(all(track.status() != track.BAD and track.length() > 1 for track in app.soundscape.music.tracks),
            "音乐解码失败或曲目为空")
    app.audio_settings.master_volume = 0
    app.soundscape.set_volumes(0, 0, 0)
    window, pipeline = app.win, app.pipeline
    handle = window.getWindowHandle().getIntHandle() if isinstance(window, GraphicsWindow) else None
    transitions, sizes, counts = [], [], []

    def capture(name):
        app.graphicsEngine.syncFrame()
        require(window.getScreenshot().write(Filename.fromOsSpecific(str(output/f"{name}.png"))), "截图保存失败")

    def edit(entry, value):
        app.lab.advanced_panel.show()
        app.lab.blur_entries()
        entry.enterText("")
        entry.guiItem.setFocus(True)
        for _ in range(3):
            app.taskMgr.step()
        device = window.getInputDevice(0)
        for char in value:
            key = KeyboardButton.asciiKey(char)
            device.buttonDown(key)
            device.keystroke(ord(char))
            device.buttonUp(key)
            for _ in range(3):
                app.taskMgr.step()
        require(entry.get() == value, entry.get())
        app.lab.blur_entries()
        app.lab.advanced_panel.hide()

    def pump(name, target):
        stages, times = [], []
        started = perf_counter()
        while app._workspace_steps is not None:
            require(perf_counter() - started < 120, '切换超时')
            before = perf_counter()
            app.taskMgr.step()
            times.append(perf_counter()-before)
            require(app.win is window and app.pipeline is pipeline, "窗口或渲染管线被替换")
            if not app.workspace_loading.root.isHidden():
                progress = app.workspace_loading.history[-1]
                if not stages or stages[-1] != progress:
                    stages.append(progress)
                    capture(f"{name}-{len(stages)-1}")
            elif app.workspace != target:
                raise AssertionError(app.workspace_loading.stage.getText())
        require(app.workspace == target, "未进入目标工作区")
        require(stages[-1][0] == 5 and [s[0] for s in stages] == sorted(s[0] for s in stages), "加载阶段未顺序完成")
        require(len(stages) >= 5, "加载阶段缺失")
        if handle is not None:
            require(window.getWindowHandle().getIntHandle() == handle, "原生窗口句柄改变")
        size = (window.getXSize(), window.getYSize())
        require(size == expected_size, (name, size, expected_size))
        sizes.append(size)
        app.taskMgr.step()
        capture(name+"-ready")
        transitions.append({"name": name, "stages": stages, "seconds": perf_counter()-started,
                            "longest_stage_frame_s": max(times)})

    try:
        if onscreen:
            props = WindowProperties()
            props.setSize(1180, 760)
            window.requestProperties(props)
            deadline = perf_counter()+5
            while (window.getXSize(), window.getYSize()) != (1180, 760):
                require(perf_counter() < deadline, '窗口未完成用户尺寸请求')
                app.taskMgr.step()
        for _ in range(5):
            app.taskMgr.step()
        expected_size = (window.getXSize(), window.getYSize())
        for index in range(3):
            if onscreen and index == 1:
                props = WindowProperties()
                props.setSize(1600, 900)
                window.requestProperties(props)
                deadline = perf_counter()+5
                while (window.getXSize(), window.getYSize()) != (1600, 900):
                    require(perf_counter() < deadline, '窗口未完成放大请求')
                    app.taskMgr.step()
                for _ in range(5):
                    app.taskMgr.step()
                expected_size = (window.getXSize(), window.getYSize())
            previous_sound = app.soundscape
            previous_session = app.session
            game_world = app.session.simulation
            previous_process = app.session.process if independent else None
            app.open_vehicle_lab()
            require(not app.workspace_loading.root.isHidden(), "加载界面未显示")
            pump(f"lab-{index}", "lab")
            require(app.session is None and app.lab.engine is app and not app.lab.owns_window, "实验台未复用窗口或旧会话未释放")
            require(previous_sound.closed and app.soundscape is None, "旧声音会话未释放")
            if independent:
                require(previous_session.closed and previous_process._closed, "旧独立物理进程未关闭")
            else:
                require(game_world.closed, "旧物理世界未关闭")
            lab = app.lab
            if index == 0:
                lab.set_options(LabOptions(speed_kph=15, duration=.025, cg_height=.42))
                lab.start_experiment()
                while not lab.run_state.done:
                    lab.run_state.step()
                lab.record = LabRecord.from_run(lab.run_state)
                lab.pin_baseline()
                if onscreen:
                    edit(lab.entries["cg"], ".47")
                else:
                    lab.entries["cg"].enterText(".47")
                lab.show_sample(2)
                lab.design_loop.show()
                lab.design_loop.drive()
            else:
                require(lab.entries["cg"].get() == ".47" and lab.view_index == 2, "输入草稿或时间游标未恢复")
                require(lab.baseline is not None and lab.record is not None, "试验记录或A槽丢失")
                require(lab.workspace_vehicle.config.center_of_mass_height == .42, "实验台工程车配置改变")
                if onscreen:
                    edit(lab.entries["cg"], ".47")
                lab.next_drive = True
                lab.back_to_game()
            run = lab.run_state
            pump(f"drive-{index}", "game")
            require(lab._closed and (run is None or run.closed), "实验台或试验物理世界未释放")
            require(app.session.base_vehicle_config.center_of_mass_height == .42, "试驾未使用工程车")
            require(app.session.phase in (Phase.COUNTDOWN, Phase.DRIVING, Phase.PAUSED), "未返回试驾")
            require(tuple(app.cam.node().getDisplayRegion(0).getDimensions()) == (0, 1, 0, 1), "驾驶相机区域未恢复")
            require(app.render.findAllMatches("**/vehicle-lab-scene").getNumPaths() == 0, "实验台场景残留")
            counts.append((len(app.taskMgr.getAllTasks()), app.win.getNumDisplayRegions(),
                           app.graphicsEngine.getNumWindows(), len(app.game_input.getAllAccepting()),
                           len(DirectGuiWidget.guiDict)))
        require(counts[1:] == counts[:-1], counts)
        app.back_to_menu()
        app.taskMgr.step()
        capture("returned-menu")
        app._begin_workspace(app._load_road(app.session.mode, "coastal"), "驶向滨海公路", "同一加载流程")
        pump("menu-road", "game")
        report = {"passed": True, "onscreen": onscreen, "independent_physics": independent,
                  "window_handle": handle, "sizes": sizes, "task_regions_windows_events": counts,
                  "transitions": transitions}
        (output/"report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        app.close_game()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--onscreen", action="store_true")
    parser.add_argument("--independent", action="store_true")
    args = parser.parse_args()
    os.environ["LOCALAPPDATA"] = str(args.output.resolve()/"user-data")
    print(json.dumps(check(args.output, onscreen=args.onscreen, independent=args.independent), ensure_ascii=False))
