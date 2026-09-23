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
from garage import GaragePreview
from highway_map import HIGHWAY_LENGTH
from highway_run import TRAFFIC_DENSITIES
from paths import user_data
from race import BestTimes, GameMode
from scene import Scene
from session import Phase, Session
from settings import AppearanceStore, AudioSettingsStore
from simulation import Control
from skins import MODELS, SKINS, apply_skin
from soundscape import Soundscape


class CoastalDrive(ShowBase):
    def __init__(self, *, smoke=False, onscreen=False, output=None, seed=0, track="coastal", road_shape="straight"):
        loadPrcFileData(
            "coastaldrive",
            "\n".join(
                [
                    "window-title CoastalDrive 0.8.1 Atmosphere",
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
        appearance_path = self.output / "test-appearance.json" if smoke else None
        self.appearance = AppearanceStore(appearance_path)
        audio_path = self.output / "test-audio.json" if smoke else None
        self.audio_settings = AudioSettingsStore(audio_path)
        self.session = Session(
            seed,
            track=track,
            road_shape=road_shape,
            scores=BestTimes(self.output / "test-best-times.json") if smoke else None,
        )
        self.skin_index = next(
            (i for i, skin in enumerate(SKINS) if skin.id == self.appearance.skin_id), 0
        )
        self.vehicle_model_id = self.appearance.model_id
        self.scene = Scene(self)
        self.soundscape = (
            None
            if smoke
            else Soundscape(
                self, self.audio_settings.master_volume, self.audio_settings.effects_volume
            )
        )
        self._scene_track = self.session.simulation.track
        self._scene_mode = self.session.mode
        self._scene_shape = self.session.road_shape
        self.highway_menu = False
        self.audio_settings_page = False
        self.highway_shape = "hills"
        self.highway_density_keys = tuple(TRAFFIC_DENSITIES)
        self.highway_density_index = self.highway_density_keys.index(self.session.traffic_density)
        self.garage = None
        self.garage_model_id = self.vehicle_model_id
        self.garage_skin_index = self.skin_index
        self._diagnostics_was_visible = False
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
        if track == "endless":
            self.session.traffic_density = self.highway_density_keys[self.highway_density_index]
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
        if self.garage is not None:
            if key in ("enter", "escape") and key not in self.commands_held:
                self.commands_held.add(key)
                self.apply_garage() if key == "enter" else self.cancel_garage()
            return
        if self.audio_settings_page and self.session.phase == Phase.MENU:
            if key == "escape" and key not in self.commands_held:
                self.commands_held.add(key)
                self.back_from_audio_settings()
            return
        if key in ("r", "c", "escape", "enter"):
            if key not in self.commands_held:
                self.commands_held.add(key)
                if self.session.phase == Phase.MENU and self.highway_menu:
                    if key == "enter":
                        self.start_highway(self.highway_shape)
                        return
                    if key == "escape":
                        self.back_to_modes()
                        return
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
        self.status_frame = DirectFrame(
            frameColor=(0.015, 0.025, 0.035, 0.74),
            frameSize=(0, 0.91, -0.43, 0),
            pos=(-1.72, 0, 0.91),
        )
        self.status = OnscreenText(
            **text_style,
            parent=self.status_frame,
            text="",
            pos=(0.06, -0.04),
            scale=0.046,
            align=TextNode.ALeft,
            mayChange=True,
        )
        self.help_frame = DirectFrame(
            frameColor=(0.015, 0.025, 0.035, 0.68),
            frameSize=(-0.89, 0.89, -0.06, 0.04),
            pos=(0, 0, -0.9),
        )
        self.help = OnscreenText(
            **text_style,
            parent=self.help_frame,
            text="W / ↑ 油门    S / ↓ 刹车·倒车    A D / ← → 转向    R 复位    C 视角    Esc 暂停",
            pos=(0, -0.018),
            scale=0.036,
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
                pos=(0, 0, 0.12 - i * 0.145),
                frameSize=(-5, 5, -0.5, 1),
                frameColor=(0.18, 0.27, 0.37, 1),
                text_fg=(0.96, 0.98, 1, 1),
                text_font=self.ui_font,
                relief=DGG.FLAT,
            )
            for i in range(6)
        ]

    def choose_audio_settings(self):
        self.audio_settings_page = True
        self._shown_phase = None
        self.refresh_panel()

    def adjust_audio_volume(self, setting, step):
        master = self.audio_settings.master_volume
        effects = self.audio_settings.effects_volume
        if setting == "master":
            master = max(0, min(100, master + step))
        else:
            effects = max(0, min(100, effects + step))
        self.audio_settings.save(master, effects)
        if self.soundscape is not None:
            self.soundscape.set_volumes(master, effects)
        self._shown_phase = None
        self.refresh_panel()

    def back_from_audio_settings(self):
        self.audio_settings_page = False
        self._shown_phase = None
        self.refresh_panel()

    def choose_garage(self):
        if self.session.phase != Phase.MENU:
            return
        self.garage_model_id = self.vehicle_model_id
        self.garage_skin_index = self.skin_index
        self._diagnostics_was_visible = not self.diagnostics.isHidden()
        self.diagnostics.hide()
        self.scene.render.hide()
        self.help_frame.hide()
        self.panel.setPos(0.72, 0, 0)
        self.panel_note.setPos(0, 0.35)
        self.panel["frameSize"] = (-0.55, 0.55, -0.68, 0.68)
        self.garage = GaragePreview(self, self.garage_model_id, self.garage_skin_index)
        self._shown_phase = None
        self.refresh_panel()

    def cycle_garage_model(self):
        index = next(i for i, model in enumerate(MODELS) if model.id == self.garage_model_id)
        self.garage_model_id = MODELS[(index + 1) % len(MODELS)].id
        self.garage.set_vehicle(self.garage_model_id, self.garage_skin_index)
        self._shown_phase = None
        self.refresh_panel()

    def cycle_garage_skin(self, step):
        self.garage_skin_index = (self.garage_skin_index + step) % len(SKINS)
        apply_skin(self.garage.body.getChild(0), self.garage_skin_index)
        self._shown_phase = None
        self.refresh_panel()

    def apply_garage(self):
        model_id = self.garage_model_id
        skin_id = SKINS[self.garage_skin_index].id
        if not self.appearance.save(model_id, skin_id):
            self._shown_phase = None
            self.refresh_panel()
            return
        self.vehicle_model_id = model_id
        self.skin_index = self.garage_skin_index
        self.close_garage()
        self.scene.close()
        self.scene = Scene(self)
        self._scene_track = self.session.simulation.track
        self._scene_mode = self.session.mode
        self._scene_shape = self.session.road_shape

    def cancel_garage(self):
        self.close_garage()

    def close_garage(self):
        if self.garage is None:
            return
        self.garage.close()
        self.garage = None
        self.scene.render.show()
        self.setBackgroundColor(0.55, 0.73, 0.82)
        self.help_frame.show()
        if self._diagnostics_was_visible:
            self.diagnostics.show()
        self.panel.setPos(0, 0, 0)
        self.panel_note.setPos(0, 0.29)
        self.panel["frameSize"] = (-0.8, 0.8, -0.68, 0.68)
        self.chase_camera.position = None
        self._shown_phase = None
        self.refresh_panel()

    def choose_highway(self):
        self.highway_menu = True
        self._shown_phase = None
        self.refresh_panel()

    def start_highway(self, shape, mode=GameMode.FREE_DRIVE):
        self.highway_menu = False
        self.highway_shape = shape
        self.session.road_shape = shape
        self.start_game(mode=mode, track="endless")

    def cycle_highway_shape(self):
        self.highway_shape = "straight" if self.highway_shape == "hills" else "hills"
        self._shown_phase = None
        self.refresh_panel()

    def cycle_highway_density(self):
        self.highway_density_index = (self.highway_density_index + 1) % len(self.highway_density_keys)
        self.session.traffic_density = self.highway_density_keys[self.highway_density_index]
        self._shown_phase = None
        self.refresh_panel()

    def back_to_modes(self):
        self.highway_menu = False
        self._shown_phase = None
        self.refresh_panel()

    def toggle_diagnostics(self):
        if self.garage is not None:
            return
        self.diagnostics.show() if self.diagnostics.isHidden() else self.diagnostics.hide()

    def refresh_panel(self):
        phase = self.session.phase
        panel_state = (phase, self.garage is not None, self.highway_menu, self.audio_settings_page)
        if panel_state == self._shown_phase:
            return
        self._shown_phase = panel_state
        if phase in (Phase.MENU, Phase.RESULTS):
            self.status_frame.hide()
            self.help_frame.hide()
        else:
            self.status_frame.show()
            self.help_frame.show()
        for button in self.buttons:
            button.hide()
        self.panel.show()
        self.panel_title.setText("COASTAL DRIVE")
        self.panel_note.setText("滨海环路 · 4 个检查点\n按 Enter 开始计时挑战")
        if phase == Phase.MENU and self.garage is None and not self.highway_menu and self.appearance.notice:
            self.panel_note.setText(f"滨海环路 · 4 个检查点\n按 Enter 开始计时挑战\n{self.appearance.notice}")
            self.appearance.notice = ""
        if self.garage is not None:
            model = next(model for model in MODELS if model.id == self.garage_model_id)
            skin = SKINS[self.garage_skin_index]
            self.panel_title.setText("车库")
            note = f"车型：{model.name}\n车漆：{skin.name}\nEnter 应用并返回 · Esc 取消"
            if self.appearance.notice:
                note += f"\n{self.appearance.notice}"
            self.panel_note.setText(note)
            options = [
                ("车型下一款", self.cycle_garage_model),
                ("下一种颜色", lambda: self.cycle_garage_skin(1)),
                ("上一种颜色", lambda: self.cycle_garage_skin(-1)),
                ("应用并返回  Enter", self.apply_garage),
                ("取消返回  Esc", self.cancel_garage),
            ]
        elif phase == Phase.MENU and self.audio_settings_page:
            self.panel_title.setText("声音设置")
            note = (
                f"主音量：{self.audio_settings.master_volume}%    "
                f"效果音量：{self.audio_settings.effects_volume}%\n"
                "发动机、路噪和碰撞声使用效果音量 · Esc 返回"
            )
            if self.audio_settings.notice:
                note += f"\n{self.audio_settings.notice}"
            self.panel_note.setText(note)
            options = [
                ("主音量 -10%", lambda: self.adjust_audio_volume("master", -10)),
                ("主音量 +10%", lambda: self.adjust_audio_volume("master", 10)),
                ("效果音量 -10%", lambda: self.adjust_audio_volume("effects", -10)),
                ("效果音量 +10%", lambda: self.adjust_audio_volume("effects", 10)),
                ("返回", self.back_from_audio_settings),
            ]
        elif phase == Phase.MENU and self.highway_menu:
            self.panel_title.setText("无限高速")
            density = self.highway_density_keys[self.highway_density_index]
            density_label = TRAFFIC_DENSITIES[density].label
            shape_label = "弯坡高速" if self.highway_shape == "hills" else "直线高速"
            self.panel_note.setText(
                f"{shape_label} · {density_label}\nEnter 启动自由驾驶 · Esc 返回\n"
                "挑战可倒车调整，复位会结束挑战"
            )
            options = [
                (f"道路：{shape_label}  >", self.cycle_highway_shape),
                (f"车流：{density_label}  >", self.cycle_highway_density),
                ("自由驾驶  Enter", lambda: self.start_highway(self.highway_shape)),
                (
                    "5公里无碰撞挑战",
                    lambda: self.start_highway(self.highway_shape, mode=GameMode.DISTANCE_CHALLENGE),
                ),
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
                ("车库", self.choose_garage),
                ("声音设置", self.choose_audio_settings),
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
            if self.session.simulation.track == "endless":
                highway_snapshot = self.session.highway.snapshot
                if highway_snapshot.challenge:
                    result = "挑战成功" if highway_snapshot.succeeded else "挑战失败"
                    reason = highway_snapshot.reason
                else:
                    result = "自由驾驶结束"
                    reason = highway_snapshot.reason or "自由驾驶结束"
                result_line = f"{result}：{reason}\n" if highway_snapshot.challenge else f"{result}\n"
                self.panel_note.setText(
                    result_line
                    + f"距离 {highway_snapshot.distance:.0f} m    "
                    f"用时 {highway_snapshot.elapsed:.2f} s    "
                    f"碰撞 {highway_snapshot.collisions}"
                )
            else:
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
        if self.garage is not None:
            if self.soundscape is not None:
                self.soundscape.update(self.session.current, self.session.phase, None)
            self.garage.update(self.clock.getDt())
            self.refresh_panel()
            return task.cont
        if self.session.phase == Phase.DRIVING and self.session.controller is self.session.keyboard:
            self.session.keyboard.pressed = self.driving_keys_held.copy()
        dropped = self.session.stepper.dropped_time
        state = self.session.frame(self.clock.getDt())
        if self.soundscape is not None:
            self.soundscape.update(state, self.session.phase, None)
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
                highway_snapshot = self.session.highway.snapshot
                density_label = TRAFFIC_DENSITIES[self.session.traffic_density].label
                title = "5公里无碰撞挑战" if highway_snapshot.challenge else "自由驾驶"
                distance = (
                    f"{highway_snapshot.distance:.0f} / {highway_snapshot.target:.0f} m"
                    if highway_snapshot.challenge else f"{highway_snapshot.distance / 1000:.2f} km"
                )
                race_line = (
                    f"{title}   {distance}   用时 {highway_snapshot.elapsed:.1f} s\n"
                    f"车流 {density_label}   碰撞 {highway_snapshot.collisions}"
                )
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
        if self.garage is not None:
            self.close_garage()
        self.taskMgr.remove("drive-update")
        self.taskMgr.remove("finish-smoke")
        self.ignoreAll()
        self.session.close()
        if self.soundscape is not None:
            self.soundscape.close()
        self.scene.close()
        for widget in (
            self.status,
            self.status_frame,
            self.help,
            self.help_frame,
            self.diagnostics,
            self.panel_title,
            self.panel_note,
            *self.buttons,
            self.panel,
        ):
            widget.destroy()
        self.destroy()
        self._shutdown = True
