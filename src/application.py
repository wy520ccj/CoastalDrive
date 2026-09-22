import json
import logging
import math
import os
from pathlib import Path

import simplepbr
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Filename, TextNode, Vec3, loadPrcFileData

from chase_camera import ChaseCamera
from controls import ConstantController
from highway_map import HIGHWAY_LENGTH
from paths import user_data
from race import BestTimes, GameMode
from scene import Scene
from session import Phase, Session
from simulation import Control
from skins import SKINS, apply_skin


class CoastalDrive(ShowBase):
    def __init__(self, *, smoke=False, onscreen=False, output=None, seed=0, track="coastal", road_shape="straight"):
        loadPrcFileData(
            "coastaldrive",
            "\n".join(
                [
                    "window-title CoastalDrive - Endless Traffic Preview 0.6.2",
                    "win-size 1280 720",
                    "sync-video 1",
                    "window-type offscreen" if smoke and not onscreen else "window-type onscreen",
                    "audio-library-name null" if smoke else "audio-library-name p3openal_audio",
                ]
            ),
        )
        super().__init__()
        self.disableMouse()
        # The default bias detaches contact shadows at our light's depth range.
        self.pipeline = simplepbr.init(enable_shadows=True, msaa_samples=4, shadow_bias=0.0007)
        self.camLens.setFov(68)
        self.camLens.setNearFar(0.15, 1500)
        self.smoke = smoke
        self.onscreen = onscreen
        self.output = output or user_data()
        self.session = Session(
            seed,
            track=track,
            road_shape=road_shape,
            scores=BestTimes(self.output / "test-best-times.json") if smoke else None,
        )
        self.skin_index = 0
        self.scene = Scene(self)
        self._scene_track = self.session.simulation.track
        self._scene_mode = self.session.mode
        self._scene_shape = self.session.road_shape
        self.highway_menu = False
        self._camera_origin = 0.0
        self.chase_camera = ChaseCamera()
        self.commands_held = set()
        self.driving_keys_held = set()
        self._shutdown = False
        self._shown_phase = None
        self.setup_controls()
        self.setup_hud()
        self.taskMgr.add(self.update, "drive-update")
        if smoke:
            self.session.start(countdown=False)
            self.session.set_controller(ConstantController(Control(throttle=1)))
            self.taskMgr.doMethodLater(1.2, self.finish_smoke, "finish-smoke")

    def start_game(self, *, mode, track="coastal"):
        self.driving_keys_held.clear()
        self.session.start(mode=mode, track=track)
        self.sync_scene()
        self.chase_camera.position = None
        self._camera_origin = self.session.simulation.origin_y

    def sync_scene(self):
        track = self.session.simulation.track
        mode = self.session.mode
        if (
            track != self._scene_track
            or mode != self._scene_mode
            or self.session.road_shape != self._scene_shape
            or len(self.scene.traffic) != len(self.session.current.traffic)
        ):
            self.scene.close()
            self.scene = Scene(self)
            self._scene_track = track
            self._scene_mode = mode
            self._scene_shape = self.session.road_shape
            self.chase_camera.position = None

    def setup_controls(self):
        for key in (
            "w",
            "a",
            "s",
            "d",
            "arrow_up",
            "arrow_down",
            "arrow_left",
            "arrow_right",
            "r",
            "c",
            "escape",
            "enter",
        ):
            self.accept(key, self.key_down, [key])
            self.accept(f"{key}-up", self.key_up, [key])
            if len(key) == 1:
                self.accept(f"raw-{key}", self.key_down, [key])
                self.accept(f"raw-{key}-up", self.key_up, [key])
        self.accept("f3", self.toggle_diagnostics)

    def key_down(self, key):
        if key in ("r", "c", "escape", "enter"):
            if key not in self.commands_held:
                self.commands_held.add(key)
                self.session.command(key)
                if key in ("r", "escape", "enter"):
                    self.driving_keys_held.clear()
        elif self.session.phase in (Phase.DRIVING, Phase.COUNTDOWN):
            self.driving_keys_held.add(key)
            if self.session.phase == Phase.DRIVING:
                self.session.keyboard.press(key)

    def key_up(self, key):
        self.commands_held.discard(key)
        self.driving_keys_held.discard(key)
        self.session.keyboard.release(key)

    def windowEvent(self, win):
        super().windowEvent(win)
        if hasattr(self, "session") and win == self.win and not self.smoke:
            properties = win.getProperties()
            self.session.focus_changed(properties.getForeground() and not properties.getMinimized())
            if not properties.getForeground():
                self.commands_held.clear()
                self.driving_keys_held.clear()

    def setup_hud(self):
        # Windows supplies this font. It is used locally, never copied into the assets.
        font_path = (Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc").resolve()
        self.ui_font = self.loader.loadFont(Filename.fromOsSpecific(str(font_path)).getFullpath())
        self.ui_font.setPixelsPerUnit(48)
        text_style = {"fg": (0.94, 0.97, 1, 1), "shadow": (0, 0, 0, 0.6), "font": self.ui_font}
        self.status = OnscreenText(
            **text_style,
            text="",
            pos=(-1.62, 0.85),
            scale=0.052,
            align=TextNode.ALeft,
            mayChange=True,
        )
        self.help = OnscreenText(
            **text_style,
            text="W / ↑ 油门    S / ↓ 刹车·倒车    A D / ← → 转向    R 复位    C 视角    Esc 暂停",
            pos=(0, -0.94),
            scale=0.04,
        )
        self.diagnostics = OnscreenText(
            **text_style,
            text="",
            pos=(-1.62, 0.37),
            scale=0.035,
            align=TextNode.ALeft,
            mayChange=True,
        )
        self.diagnostics.hide()
        self.panel = DirectFrame(
            frameColor=(0.02, 0.04, 0.065, 0.96), frameSize=(-0.8, 0.8, -0.68, 0.68)
        )
        self.panel_title = OnscreenText(
            **text_style, parent=self.panel, text="", pos=(0, 0.46), scale=0.07, mayChange=True
        )
        self.panel_note = OnscreenText(
            **text_style, parent=self.panel, text="", pos=(0, 0.29), scale=0.043, mayChange=True
        )
        self.buttons = [
            DirectButton(
                parent=self.panel,
                text="",
                scale=0.055,
                pos=(0, 0, 0.08 - i * 0.16),
                frameSize=(-5, 5, -0.5, 1),
                frameColor=(0.18, 0.27, 0.37, 1),
                text_fg=(0.96, 0.98, 1, 1),
                text_font=self.ui_font,
                relief=DGG.FLAT,
            )
            for i in range(5)
        ]

    def cycle_skin(self):
        if self.session.phase != Phase.MENU:
            return
        self.skin_index = (self.skin_index + 1) % len(SKINS)
        apply_skin(self.scene.player.getChild(0), self.skin_index)
        self._shown_phase = None
        self.refresh_panel()

    def choose_highway(self):
        self.highway_menu = True
        self._shown_phase = None
        self.refresh_panel()

    def start_highway(self, shape):
        self.highway_menu = False
        self.session.road_shape = shape
        self.start_game(mode=GameMode.FREE_DRIVE, track="endless")

    def back_to_modes(self):
        self.highway_menu = False
        self._shown_phase = None
        self.refresh_panel()

    def toggle_diagnostics(self):
        self.diagnostics.show() if self.diagnostics.isHidden() else self.diagnostics.hide()

    def refresh_panel(self):
        phase = self.session.phase
        if phase == self._shown_phase:
            return
        self._shown_phase = phase
        for button in self.buttons:
            button.hide()
        self.panel.show()
        self.panel_title.setText("COASTAL DRIVE")
        self.panel_note.setText("滨海环路 · 4 个检查点\n按 Enter 开始计时挑战")
        if phase == Phase.MENU and self.highway_menu:
            self.panel_title.setText("无限高速")
            self.panel_note.setText("选择道路\n两种道路均有连续车流")
            options = [
                ("弯坡高速 · 预览", lambda: self.start_highway("hills")),
                ("直线高速", lambda: self.start_highway("straight")),
                ("返回", self.back_to_modes),
            ]
        elif phase == Phase.MENU:
            options = [
                ("计时挑战  Enter", lambda: self.start_game(mode=GameMode.TIME_TRIAL)),
                ("滨海自由驾驶", lambda: self.start_game(mode=GameMode.FREE_DRIVE)),
                (
                    "无限高速",
                    self.choose_highway,
                ),
                (f"车漆：{SKINS[self.skin_index].name}  ›", self.cycle_skin),
                ("退出", self.userExit),
            ]
        elif phase == Phase.PAUSED:
            self.driving_keys_held.clear()
            self.panel_title.setText("已暂停")
            self.panel_note.setText("切出窗口会自动暂停\n按 Enter 或 Esc 继续驾驶")
            options = [
                ("继续驾驶  Enter", self.session.resume),
                ("重新开始", self.session.start),
                ("结束驾驶", self.session.finish),
                ("返回主菜单", self.session.menu),
            ]
        elif phase == Phase.RESULTS:
            self.panel_title.setText("驾驶结束")
            race = self.session.race.snapshot
            if race.finished and race.last_lap is not None:
                result = "有效圈" if not race.invalidated else f"本圈无效：{race.invalid_reason}"
                best = f"最佳 {race.best_lap:.3f} 秒" if race.best_lap else "暂无最佳成绩"
                self.panel_note.setText(
                    f"{result}\n本圈 {race.last_lap:.3f} 秒    {best}"
                    + (f"\n{race.save_error}" if race.save_error else "")
                )
            elif self.session.mode == GameMode.FREE_DRIVE:
                self.panel_note.setText("自由驾驶结束\n可重新出发或返回菜单")
            else:
                self.panel_note.setText("挑战提前结束，本次不记录圈速")
            options = [
                (
                    "重新挑战  Enter",
                    lambda: self.start_game(
                        mode=self.session.mode, track=self.session.simulation.track
                    ),
                ),
                ("返回主菜单", self.session.menu),
                ("退出", self.userExit),
            ]
        else:
            self.panel.hide()
            return
        for button, (label, action) in zip(self.buttons, options):
            button["text"] = label
            button["command"] = action
            button.show()

    def update(self, task):
        if self.session.phase == Phase.DRIVING and self.session.controller is self.session.keyboard:
            self.session.keyboard.pressed = self.driving_keys_held.copy()
        dropped = self.session.stepper.dropped_time
        state = self.session.frame(self.clock.getDt())
        if self.session.stepper.dropped_time > dropped:
            logging.getLogger(__name__).warning(
                "Simulation catch-up dropped %.6f seconds",
                self.session.stepper.dropped_time - dropped,
            )
        self.sync_scene()
        self.scene.apply(state)
        if self.chase_camera.position is not None:
            self.chase_camera.position.y -= state.origin_y - self._camera_origin
        self._camera_origin = state.origin_y
        position = Vec3(*state.player.position)
        snap = state.tick == 0 or "player_reset" in state.events
        camera_dt = self.clock.getDt() if self.session.phase == Phase.DRIVING else 0
        camera_position, look_at = self.chase_camera.update(
            state.player, self.session.camera_distance, camera_dt, snap=snap
        )
        camera_position = self.session.simulation.camera_position(
            position + Vec3(0, 0, 1.4), camera_position
        )
        self.camera.setPos(camera_position)
        self.camera.lookAt(look_at)
        self.camLens.setFov(self.chase_camera.fov)
        self.scene.update_lighting(position)
        phase = self.session.phase
        countdown = (
            f"   {math.ceil(self.session.countdown_ticks / 120)} 秒后开始"
            if phase == Phase.COUNTDOWN
            else ""
        )
        gear = "R" if state.player.gear < 0 else f"D{state.player.gear}"
        surface = "柏油" if state.player.surface == "asphalt" else "路肩 / 草地"
        race = self.session.race.snapshot
        if race.mode == GameMode.TIME_TRIAL:
            race_line = f"计时挑战   {race.elapsed:06.3f} s   检查点 {race.checkpoints}/4"
            if race.invalidated:
                race_line += f"\n本次无效：{race.invalid_reason} · 重新开始可再次挑战"
            else:
                target = "终点" if race.checkpoints == 4 else f"检查点 {race.next_checkpoint}"
                best = f"最佳 {race.best_lap:.3f} s" if race.best_lap else "暂无最佳成绩"
                race_line += f"\n下一处：{target}    {best}"
        else:
            race_line = "自由驾驶   不计时"
            if self.session.simulation.track == "highway":
                race_line += f"   距路段终点 {max(0, HIGHWAY_LENGTH - position.y):.0f} m\n交通车辆 · 基础跟车 / 实体碰撞"
            elif self.session.simulation.track == "endless":
                road = self.session.simulation.road
                distance = road.locate(state.player)[0] if road.curve else state.origin_y + position.y
                race_line += f"   里程 {(distance - 8) / 1000:.2f} km\n无限高速 · 连续车流"
        self.status.setText(
            f"{abs(state.player.speed) * 3.6:03.0f} km/h   {gear}   {state.player.rpm:4.0f} rpm{countdown}\n"
            f"油门 {state.player.throttle:.0%}    刹车 {state.player.brake:.0%}    {surface}\n"
            f"加速度 {self.chase_camera.acceleration:+.1f} m/s²\n{race_line}"
            + (f"\n{self.session.notice}" if self.session.notice else "")
        )
        self.diagnostics.setText(
            f"Tick {self.session.current.tick}   Simulation 120 Hz\n"
            f"Dropped time {self.session.stepper.dropped_time:.3f} s\n"
            f"转向 {state.player.steering:+.1f}°    横向 {state.player.lateral_acceleration / 9.81:+.2f} g\n"
            f"风阻 {state.player.dynamics.aerodynamic_force:.0f} N    滚阻 {state.player.dynamics.rolling_force:.0f} N\n"
            f"前/后轴载荷 {state.player.dynamics.front_load:.0f} / {state.player.dynamics.rear_load:.0f} N\n"
            f"横摆 {state.player.dynamics.yaw_rate:.2f} rad/s    侧偏 {state.player.dynamics.sideslip:.1f}°"
        )
        self.refresh_panel()
        return task.cont

    def finish_smoke(self, task):
        # Shader startup can consume the first second without advancing the car.
        if self.session.current.tick < 240 and task.time < 10:
            return task.again
        self.output.mkdir(parents=True, exist_ok=True)
        state = self.session.current
        self.graphicsEngine.renderFrame()
        screenshot = self.output / ("h0-window.png" if self.onscreen else "h0-offscreen.png")
        captured = self.win.saveScreenshot(Filename.fromOsSpecific(str(screenshot)))
        nodes = self.scene.render.findAllMatches("**").getNumPaths()
        tasks = len(self.taskMgr.getAllTasks())
        events = len(self.getAllAccepting())
        for _ in range(20):
            self.session.start(countdown=False)
        report = {
            "passed": state.tick > 0 and state.player.position[1] > 0.5 and captured,
            "tick": state.tick,
            "player_position": state.player.position,
            "traffic_count": len(state.traffic),
            "renderer": self.win.getGsg().getDriverRenderer(),
            "screenshot": str(screenshot),
            "restart_20_nodes_stable": nodes
            == self.scene.render.findAllMatches("**").getNumPaths(),
            "restart_20_tasks_stable": tasks == len(self.taskMgr.getAllTasks()),
            "restart_20_events_stable": events == len(self.getAllAccepting()),
        }
        report["passed"] = report["passed"] and all(
            report[k] for k in report if k.endswith("_stable")
        )
        (self.output / "h0-render-smoke.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        self.smoke_passed = report["passed"]
        self.userExit()
        return task.done

    def finalizeExit(self):
        self.taskMgr.stop()

    def close_game(self):
        if self._shutdown:
            return
        self.taskMgr.remove("drive-update")
        self.taskMgr.remove("finish-smoke")
        self.ignoreAll()
        self.session.close()
        self.scene.close()
        for widget in (
            self.status,
            self.help,
            self.diagnostics,
            self.panel_title,
            self.panel_note,
            *self.buttons,
            self.panel,
        ):
            widget.destroy()
        self.destroy()
        self._shutdown = True
