import json
import logging
import math

import simplepbr
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Filename, TextNode, TransparencyAttrib, Vec3, loadPrcFileData

from chase_camera import ChaseCamera
from controls import ConstantController
from garage import GaragePreview
from highway_run import TRAFFIC_DENSITIES
from paths import user_data
from race import BestTimes, GameMode
from scene import Scene
from session import Phase, Session
from settings import AppearanceStore, AudioSettingsStore
from simulation import Control
from skins import MODELS, SKINS, apply_skin
from soundscape import Soundscape
from ui import theme
from ui.hud import DrivingHUD
from ui.main_menu import MainMenu


class CoastalDrive(ShowBase):
    def __init__(self, *, smoke=False, onscreen=False, output=None, seed=0, track="coastal", road_shape="straight", render_size=(1280, 720), startup_trace=None):
        self.startup_trace = startup_trace
        loadPrcFileData(
            "coastaldrive",
            "\n".join(
                [
                    "window-title CoastalDrive 0.8.3 Impact Audio",
                    'icon-filename assets/game/ui/coastal-drive.ico',
                    f"win-size {render_size[0]} {render_size[1]}",
                    "sync-video 1",
                    "window-type offscreen" if smoke and not onscreen else "window-type onscreen",
                    "audio-library-name null" if smoke else "audio-library-name p3openal_audio",
                ]
            ),
        )
        super().__init__()
        if startup_trace is not None:
            startup_trace.mark("window_initialized")
        self.disableMouse()
        # The default bias detaches contact shadows at our light's depth range.
        self.pipeline = simplepbr.init(enable_shadows=True, msaa_samples=4, shadow_bias=0.0007)
        if startup_trace is not None:
            startup_trace.mark("renderer_initialized")
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
        if startup_trace is not None:
            startup_trace.mark("simulation_initialized")
        self.skin_index = next(
            (i for i, skin in enumerate(SKINS) if skin.id == self.appearance.skin_id), 0
        )
        self.vehicle_model_id = self.appearance.model_id
        if startup_trace is not None:
            startup_trace.mark("environment_load_started")
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
        self.panel_selection = 0
        self.panel_option_count = 0
        self._diagnostics_was_visible = False
        self._camera_origin = 0.0
        self.chase_camera = ChaseCamera()
        self.commands_held = set()
        self.driving_keys_held = set()
        self._shutdown = False
        self._shown_phase = None
        self.setup_controls()
        self.setup_hud()
        if startup_trace is not None:
            startup_trace.mark("ui_ready")
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
        if (self.session.phase == Phase.MENU and self.garage is None
                and not self.audio_settings_page and not self.highway_menu
                and key in ("arrow_up", "arrow_down", "w", "s", "enter")):
            if key not in self.commands_held:
                self.commands_held.add(key)
                if key == "enter":
                    self.main_menu.activate()
                else:
                    self.main_menu.move(-1 if key in ("arrow_up", "w") else 1)
            return
        if self.has_panel_navigation():
            if key not in self.commands_held:
                self.commands_held.add(key)
                # 状态可能刚从驾驶切到暂停/结算，先绑定当前页动作再处理按键。
                self.refresh_panel()
                self.handle_panel_key(key)
                self.refresh_panel()
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

    def has_panel_navigation(self):
        return (
            self.garage is not None
            or self.audio_settings_page
            or self.highway_menu
            or self.session.phase in (Phase.PAUSED, Phase.RESULTS)
        )

    def handle_panel_key(self, key):
        if key in ("arrow_up", "w"):
            self.select_panel_option(self.panel_selection - 1)
        elif key in ("arrow_down", "s"):
            self.select_panel_option(self.panel_selection + 1)
        elif key in ("arrow_left", "a"):
            self.adjust_panel_option(-1)
        elif key in ("arrow_right", "d"):
            self.adjust_panel_option(1)
        elif key == "enter":
            self.buttons[self.panel_selection]["command"]()
        elif key == "escape":
            if self.garage is not None:
                self.cancel_garage()
            elif self.audio_settings_page:
                self.back_from_audio_settings()
            elif self.highway_menu:
                self.back_to_modes()
            elif self.session.phase == Phase.PAUSED:
                self.session.resume()
                self._shown_phase = None
                self.refresh_panel()

    def select_panel_option(self, index):
        self.panel_selection = index % self.panel_option_count
        for option_index, button in enumerate(self.buttons[:self.panel_option_count]):
            states = self.primary_states if option_index == 0 else self.button_states
            button["frameTexture"] = (
                (states[2], states[1], states[2], states[3])
                if option_index == self.panel_selection else states
            )

    def adjust_panel_option(self, direction):
        if self.session.phase == Phase.RESULTS:
            # 结算按钮横排，左右键与A/D移动焦点；设置页仍按原逻辑调值。
            self.select_panel_option(self.panel_selection + direction)
        elif self.garage is not None:
            if self.panel_selection == 0:
                self.cycle_garage_model(direction)
            elif self.panel_selection in (1, 2):
                self.cycle_garage_skin(direction)
        elif self.audio_settings_page:
            if self.panel_selection in (0, 1):
                self.adjust_audio_volume("master", direction * 10)
            elif self.panel_selection in (2, 3):
                self.adjust_audio_volume("effects", direction * 10)
        elif self.highway_menu:
            if self.panel_selection == 0:
                self.cycle_highway_shape()
            elif self.panel_selection == 1:
                self.cycle_highway_density(direction)

    def windowEvent(self, win):
        super().windowEvent(win)
        if hasattr(self, "session") and win == self.win and not self.smoke:
            properties = win.getProperties()
            self.session.focus_changed(properties.getForeground() and not properties.getMinimized())
            if not properties.getForeground():
                self.commands_held.clear()
                self.driving_keys_held.clear()

    def setup_hud(self):
        self.ui_font = theme.load_font()
        if self.startup_trace is not None:
            self.startup_trace.mark("primary_font_loaded")
        text_style = theme.text_style(self.ui_font)
        self.panel_texture = self.loader.loadTexture(theme.asset_filename("components/panel.png"))
        self.button_texture = self.loader.loadTexture(theme.asset_filename("components/button-normal.png"))
        self.display_font = theme.load_font(theme.DISPLAY_FONT_FILE)
        if self.startup_trace is not None:
            self.startup_trace.mark("display_font_loaded")
        self.hud = DrivingHUD(self.aspect2d, self.loader, self.ui_font, self.display_font)
        self.status_frame = self.hud.status_frame
        self.status = self.hud.status
        self.status_notice = self.hud.status_notice
        self.speed = self.hud.speed
        self.gear_rpm = self.hud.gear_rpm
        self.help_frame = self.hud.help_frame
        self.help = self.hud.help
        self.main_menu = MainMenu(self.aspect2d, self.loader, self.ui_font, self.display_font, (
            lambda: self.start_game(mode=GameMode.TIME_TRIAL),
            lambda: self.start_game(mode=GameMode.FREE_DRIVE),
            self.choose_highway, self.choose_garage, self.choose_audio_settings, self.userExit,
        ))
        self.diagnostics = OnscreenText(
            **{**text_style, "fg": theme.DIAGNOSTIC_TEXT, "shadow": theme.DIAGNOSTIC_SHADOW},
            text="",
            pos=(-1.62, 0.37),
            scale=0.035,
            align=TextNode.ALeft,
            mayChange=True,
        )
        self.diagnostics.hide()
        self.panel = DirectFrame(
            frameColor=(1, 1, 1, 1), frameTexture=self.panel_texture,
            frameSize=(-0.8, 0.8, -0.80, 0.68)
        )
        self.panel.setTransparency(TransparencyAttrib.MAlpha)
        self.result_icon = DirectFrame(
            parent=self.panel, frameColor=(1, 1, 1, 1),
            frameTexture=self.loader.loadTexture(theme.asset_filename("components/icon-trophy.png")),
            frameSize=(-0.09, 0.09, -0.09, 0.09), pos=(0, 0, 0.56),
        )
        self.result_icon.hide()
        self.button_states = tuple(self.loader.loadTexture(theme.asset_filename(f"components/button-{state}.png"))
                                   for state in ("normal", "pressed", "hover", "disabled"))
        self.primary_states = tuple(self.loader.loadTexture(theme.asset_filename(f"components/primary-{state}.png"))
                                    for state in ("normal", "pressed", "hover", "normal"))
        self.panel_accent = DirectFrame(
            parent=self.panel, frameColor=theme.ORANGE,
            frameSize=(-0.55, 0.55, -0.005, 0.005), pos=(0, 0, 0.61),
        )
        self.panel_title = OnscreenText(
            **text_style, parent=self.panel, text="", pos=(0, 0.46), scale=0.07, mayChange=True
        )
        self.panel_note = OnscreenText(
            **text_style, parent=self.panel, text="", pos=(0, 0.29), scale=0.040, mayChange=True
        )
        self.panel_detail = OnscreenText(
            **text_style, parent=self.panel, text="", pos=(0, 0.12),
            scale=0.041, mayChange=True,
        )
        self.buttons = [
            DirectButton(
                parent=self.panel,
                text="",
                scale=0.055,
                pos=(0, 0, 0.12 - i * 0.145),
                frameSize=(-5, 5, -0.5, 1),
                frameColor=theme.BUTTON_TINT,
                frameTexture=self.button_texture,
                text_fg=theme.INK,
                text_font=self.ui_font,
                relief=DGG.FLAT,
            )
            for i in range(6)
        ]
        for index, button in enumerate(self.buttons):
            button.bind(DGG.ENTER, lambda event, i=index: self.select_panel_option(i))

    def fit_lines(self, value, width, scale, max_lines=None):
        """按实际字体宽度换行，避免中文 notice 超出底板。"""
        probe = TextNode("ui-line-measure")
        probe.setFont(self.ui_font)
        lines = []
        for source in value.split("\n"):
            line = ""
            for char in source:
                probe.setText(line + char)
                if line and probe.getWidth() * scale > width:
                    lines.append(line)
                    line = char
                else:
                    line += char
            lines.append(line)
        if max_lines is not None:
            lines = lines[:max_lines]
        return "\n".join(lines)

    def choose_audio_settings(self):
        self.panel_selection = 0
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
        self.panel_selection = 3
        self.garage_model_id = self.vehicle_model_id
        self.garage_skin_index = self.skin_index
        self._diagnostics_was_visible = not self.diagnostics.isHidden()
        self.diagnostics.hide()
        self.scene.render.hide()
        self.help_frame.hide()
        self.panel.setPos(0.72, 0, 0)
        self.panel_note.setPos(0, 0.35)
        self.panel["frameSize"] = (-0.61, 0.61, -0.80, 0.68)
        self.garage = GaragePreview(self, self.garage_model_id, self.garage_skin_index)
        self._shown_phase = None
        self.refresh_panel()

    def cycle_garage_model(self, step=1):
        index = next(i for i, model in enumerate(MODELS) if model.id == self.garage_model_id)
        self.garage_model_id = MODELS[(index + step) % len(MODELS)].id
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
        self.panel["frameSize"] = (-0.8, 0.8, -0.80, 0.68)
        self.chase_camera.position = None
        self._shown_phase = None
        self.refresh_panel()

    def choose_highway(self):
        self.panel_selection = 2
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

    def cycle_highway_density(self, step=1):
        self.highway_density_index = (self.highway_density_index + step) % len(self.highway_density_keys)
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
        if not (self.garage is not None or self.highway_menu or self.audio_settings_page):
            self.panel_selection = 0
        self._shown_phase = panel_state
        self.main_menu.root.hide()
        if phase in (Phase.MENU, Phase.PAUSED, Phase.RESULTS):
            self.hud.root.hide()
        else:
            self.hud.root.show()
        if phase == Phase.MENU and self.garage is None and not self.highway_menu and not self.audio_settings_page:
            self.panel.hide()
            self.main_menu.notice.setText(self.fit_lines(self.appearance.notice, 1.0, 0.028))
            self.main_menu.root.show()
            return
        for button in self.buttons:
            button.hide()
        self.panel.show()
        self.panel_accent.show()
        self.result_icon.hide()
        self.panel_title.setPos(0, 0.46)
        self.panel_title.textNode.setSlant(0.14)
        self.panel_detail.setScale(0.041)
        self.panel["frameSize"] = (-0.61, 0.61, -0.80, 0.68) if self.garage is not None else (-0.8, 0.8, -0.80, 0.68)
        self.panel_title.setText(theme.BRAND_NAME)
        self.panel_note.setText("滨海环路 · 4 个检查点\n按 Enter 开始计时挑战")
        self.panel_detail.setText("")
        self.panel_title["fg"] = theme.INK
        self.panel_title.setScale(0.07)
        self.panel_note.setScale(0.040)
        self.panel_note.setPos(0, 0.29)
        self.panel_detail.setPos(0, 0.10)
        self.panel["frameColor"] = (1, 1, 1, 1)
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
            if self.session.simulation.track == "endless":
                highway_snapshot = self.session.highway.snapshot
                if highway_snapshot.challenge:
                    self.panel_title.setText("挑战成功" if highway_snapshot.succeeded else "挑战失败")
                    self.panel_note.setText(highway_snapshot.reason)
                else:
                    self.panel_title.setText("驾驶结束")
                    self.panel_note.setText("无限高速自由驾驶")
                self.panel_detail.setText(
                    f"距离 {highway_snapshot.distance:.0f} m   用时 {highway_snapshot.elapsed:.2f} s\n"
                    f"碰撞 {highway_snapshot.collisions} 次"
                )
            else:
                race = self.session.race.snapshot
                if race.finished and race.last_lap is not None:
                    self.panel_title.setText("挑战失败" if race.invalidated else "挑战成功")
                    self.panel_note.setText(
                        f"圈速无效：{race.invalid_reason}" if race.invalidated else "有效完成计时挑战"
                    )
                    best = f"最佳 {race.best_lap:.3f} 秒" if race.best_lap else "暂无最佳成绩"
                    self.panel_detail.setText(
                        f"本圈 {race.last_lap:.3f} 秒\n{best}"
                    )
                    if race.save_error:
                        self.panel_note.setText(f"{self.panel_note.getText()}\n{race.save_error}")
                elif self.session.mode == GameMode.FREE_DRIVE:
                    self.panel_title.setText("驾驶结束")
                    self.panel_note.setText("滨海自由驾驶")
                    self.panel_detail.setText("可重新出发或返回菜单")
                else:
                    self.panel_title.setText("挑战失败")
                    self.panel_note.setText("挑战提前结束，本次不记录圈速")
            self.panel_title.setScale(0.10)
            if self.panel_title.getText() == "挑战成功":
                self.panel_title["fg"] = theme.SUCCESS
            elif self.panel_title.getText() == "挑战失败":
                self.panel_title["fg"] = theme.FAILURE
            else:
                self.panel_title["fg"] = theme.INK
            self.panel_note.setPos(0, 0.24)
            self.panel_detail.setPos(0, 0.04)
            options = [
                (
                    "重新出发  Enter" if self.session.mode == GameMode.FREE_DRIVE else "重新挑战  Enter",
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
        note_width = 0.99 if self.garage is not None else 1.37
        self.panel_note.setText(self.fit_lines(self.panel_note.getText(), note_width, 0.040))
        self.panel_detail.setText(self.fit_lines(self.panel_detail.getText(), 1.36, 0.041))
        note_lines = self.panel_note.getText().count("\n") + 1
        if phase == Phase.RESULTS:
            self.panel_detail.setPos(0, 0.19 - 0.060 * note_lines)
        if phase == Phase.RESULTS:
            button_top = -0.16 if note_lines <= 2 else -0.23
        elif self.garage is not None or self.audio_settings_page:
            button_top = -0.03
        else:
            button_top = 0.02 if note_lines > 2 else 0.10
        for index, button in enumerate(self.buttons):
            button.setPos(0, 0, button_top - index * 0.145)
            button["frameColor"] = (
                theme.SECONDARY_BUTTON_TINT if phase == Phase.MENU and self.garage is None
                and not self.highway_menu and not self.audio_settings_page and index >= 3
                else theme.BUTTON_TINT
            )
        for button, (label, action) in zip(self.buttons, options):
            button["text"] = label
            button["command"] = action
            button.show()
        self.panel_option_count = len(options)
        self.panel_selection %= self.panel_option_count
        # 页面只安排现有动作，不在这里计算或改写比赛结果。
        for index, button in enumerate(self.buttons[:len(options)]):
            button.setScale(1)
            button["frameSize"] = (-0.51, 0.51, -0.073, 0.073)
            button["text_scale"] = 0.055
            button["text_pos"] = (0, -0.018)
            button["frameColor"] = (1, 1, 1, 1)
            button["frameTexture"] = self.primary_states if index == 0 else self.button_states
            button["text_fg"] = theme.INK
            if index == self.panel_selection:
                states = self.primary_states if index == 0 else self.button_states
                button["frameTexture"] = (states[2], states[1], states[2], states[3])
            button.setZ(button_top - index * 0.17)
        if phase == Phase.PAUSED:
            self.panel_title.setScale(0.14)
            self.panel_note.setPos(0, 0.27)
        elif phase == Phase.RESULTS:
            self.panel["frameSize"] = (-0.94, 0.94, -0.62, 0.75)
            self.panel_accent.hide()
            self.result_icon.show()
            icon = "trophy" if self.panel_title.getText() == "挑战成功" else "car"
            self.result_icon["frameTexture"] = self.loader.loadTexture(theme.asset_filename(f"components/icon-{icon}.png"))
            self.panel_title.setScale(0.18)
            self.panel_title.setPos(0, 0.32)
            self.panel_note.setPos(0, 0.18)
            self.panel_detail.setScale(0.058)
            self.panel_detail.setPos(0, 0.09 - 0.065 * note_lines)
            for button, x, width in zip(self.buttons, (-0.56, 0.12, 0.69), (0.64, 0.64, 0.40)):
                button.setPos(x, 0, -0.47)
                button["frameSize"] = (-width / 2, width / 2, -0.085, 0.085)
                button["text_scale"] = 0.047
        else:
            self.panel_accent.show()

    def update(self, task):
        self.main_menu.resize(self.getAspectRatio())
        self.hud.resize(self.getAspectRatio())
        if self.garage is not None:
            if self.soundscape is not None:
                self.soundscape.update(self.session.current, self.session.phase, None,
                                       self.clock.getDt())
            self.garage.update(self.clock.getDt())
            self.refresh_panel()
            return task.cont
        if self.session.phase == Phase.DRIVING and self.session.controller is self.session.keyboard:
            self.session.keyboard.pressed = self.driving_keys_held.copy()
        dropped = self.session.stepper.dropped_time
        state = self.session.frame(self.clock.getDt())
        if self.soundscape is not None:
            self.soundscape.update(state, self.session.phase, None, self.clock.getDt())
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
        countdown = f"{math.ceil(self.session.countdown_ticks / 120)} 秒后开始" if phase == Phase.COUNTDOWN else ""
        surface = "asphalt" if state.player.surface == "asphalt" else "off-road"
        self.hud.update(
            state, self.session.race.snapshot, self.session.highway.snapshot,
            track=self.session.simulation.track, countdown=countdown,
            notice=self.session.notice, fit_lines=self.fit_lines,
        )
        self.diagnostics.setText(
            f"Tick {self.session.current.tick}   Simulation 120 Hz\n"
            f"Dropped time {self.session.stepper.dropped_time:.3f} s\n"
            f"油门 {state.player.throttle:.0%}   刹车 {state.player.brake:.0%}   {surface}\n"
            f"加速度 {self.chase_camera.acceleration:+.1f} m/s²\n"
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
        self.main_menu.destroy()
        self.hud.destroy()
        for widget in (
            self.diagnostics,
            self.result_icon,
            self.panel_title,
            self.panel_note,
            self.panel_detail,
            self.panel_accent,
            *self.buttons,
            self.panel,
        ):
            widget.destroy()
        self.destroy()
        self._shutdown = True
