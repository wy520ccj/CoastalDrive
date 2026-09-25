import json
import logging
import math

import simplepbr
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, OnscreenText
from direct.gui.OnscreenImage import OnscreenImage
from direct.showbase.ShowBase import ShowBase
from panda3d.core import Filename, SamplerState, TextNode, Vec3, WindowProperties, loadPrcFileData

import ui_theme as theme
from chase_camera import ChaseCamera
from controls import ConstantController
from garage import GaragePreview
from highway_map import HIGHWAY_LENGTH
from highway_run import TRAFFIC_DENSITIES
from paths import resource_root, user_data
from race import BestTimes, GameMode
from scene import Scene
from session import Phase, Session
from settings import AppearanceStore, AudioSettingsStore
from simulation import Control
from skins import MODELS, SKINS, apply_skin
from soundscape import Soundscape
from ui_components import Canvas, UiSkin
from ui_layout import MainMenuPage, MessagePage


class CoastalDrive(ShowBase):
    def __init__(self, *, smoke=False, onscreen=False, output=None, seed=0, track="coastal",
                 road_shape="straight", render_size=(1280, 720), new_ui=False,
                 driver=True):
        loadPrcFileData(
            "coastaldrive",
            "\n".join(
                [
                    "window-title CoastalDrive 0.8.3 Impact Audio",
                    f"win-size {render_size[0]} {render_size[1]}",
                    "sync-video 1",
                    "window-type offscreen" if smoke and not onscreen else "window-type onscreen",
                    "audio-library-name null" if smoke else "audio-library-name p3openal_audio",
                ]
            ),
        )
        super().__init__()
        icon = resource_root() / "assets/game/ui/coastal-drive.ico"
        properties = WindowProperties()
        properties.setIconFilename(Filename.fromOsSpecific(str(icon)))
        if hasattr(self.win, "requestProperties"):
            self.win.requestProperties(properties)
        self.disableMouse()
        # The default bias detaches contact shadows at our light's depth range.
        self.pipeline = simplepbr.init(enable_shadows=True, msaa_samples=4, shadow_bias=0.0007)
        self.camLens.setFov(68)
        self.camLens.setNearFar(0.15, 1500)
        self.smoke = smoke
        self.onscreen = onscreen
        self.new_ui = new_ui
        self.menu_page = None
        self.page = None
        self.page_name = None
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
        # driver=False 用于离屏截图：停在菜单上，不接管驾驶也不提交 smoke 报告
        if smoke and driver:
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
        ui_assets = resource_root() / "assets/game/ui"
        font_path = ui_assets / "fonts/fusion-pixel-12px-proportional-zh_hans.ttf"
        self.ui_font = self.loader.loadFont(Filename.fromOsSpecific(str(font_path)).getFullpath())
        self.ui_font.setPixelsPerUnit(32)
        self.ui_font.setMinfilter(SamplerState.FTNearest)
        self.ui_font.setMagfilter(SamplerState.FTNearest)
        text_style = {"fg": (0.07, 0.17, 0.23, 1), "font": self.ui_font}
        self.panel_texture = self.loader.loadTexture(
            Filename.fromOsSpecific(str(ui_assets / "panel.png"))
        )
        self.wide_texture = self.loader.loadTexture(
            Filename.fromOsSpecific(str(ui_assets / "panel-wide.png"))
        )
        self.button_texture = self.loader.loadTexture(
            Filename.fromOsSpecific(str(ui_assets / "button.png"))
        )
        self.button_hover_texture = self.loader.loadTexture(
            Filename.fromOsSpecific(str(ui_assets / "button-hover.png"))
        )
        self.button_pressed_texture = self.loader.loadTexture(
            Filename.fromOsSpecific(str(ui_assets / "button-pressed.png"))
        )
        self.button_primary_texture = self.loader.loadTexture(
            Filename.fromOsSpecific(str(ui_assets / "button-primary.png"))
        )
        for texture in (
            self.panel_texture, self.wide_texture, self.button_texture,
            self.button_hover_texture, self.button_pressed_texture,
            self.button_primary_texture,
        ):
            texture.setMinfilter(SamplerState.FTNearest)
            texture.setMagfilter(SamplerState.FTNearest)
        self.menu_art = OnscreenImage(
            image=self.loader.loadTexture(Filename.fromOsSpecific(str(ui_assets / "coastal-drive-icon.png"))),
            pos=(0.94, 0, -0.10), scale=0.67,
        )
        self.menu_art.setTransparency(True)
        self.speed_frame = DirectFrame(
            frameColor=(0.055, 0.13, 0.18, 0.94),
            frameSize=(0, 0.62, -0.35, 0), pos=(1.08, 0, -0.54),
        )
        self.telemetry_frame = DirectFrame(
            frameColor=(1, 0.74, 0.21, 1),
            frameSize=(0, 0.17, -0.16, 0), pos=(1.49, 0, -0.60),
        )
        self.speed_accent = DirectFrame(
            parent=self.speed_frame, frameColor=(1, 0.65, 0.15, 1),
            frameSize=(0.03, 0.58, -0.02, -0.012),
        )
        self.speed = OnscreenText(
            **text_style, parent=self.speed_frame, text="", pos=(0.24, -0.245),
            scale=0.16, align=TextNode.ACenter, mayChange=True,
        )
        self.speed["fg"] = (0.99, 0.98, 0.93, 1)
        self.speed_unit = OnscreenText(
            **text_style, parent=self.speed_frame, text="km/h", pos=(0.48, -0.24),
            scale=0.033, align=TextNode.ACenter,
        )
        self.speed_unit["fg"] = (0.95, 0.95, 0.91, 1)
        self.gear_rpm = OnscreenText(
            **text_style, parent=self.telemetry_frame, text="", pos=(0.085, -0.11),
            scale=0.065, align=TextNode.ACenter, mayChange=True,
        )
        self.rpm_track = DirectFrame(
            parent=self.speed_frame, frameColor=(0.36, 0.43, 0.48, 1),
            frameSize=(0.04, 0.58, -0.32, -0.29),
        )
        self.rpm_bar = DirectFrame(
            parent=self.speed_frame, frameColor=(1, 0.71, 0.18, 1),
            frameSize=(0.04, 0.04, -0.32, -0.29),
        )
        self.status_frame = DirectFrame(
            frameColor=(1, 1, 1, 1), frameTexture=self.wide_texture,
            frameSize=(0, 0.83, -0.27, 0), pos=(-1.71, 0, 0.91),
        )
        self.status_accent = DirectFrame(
            parent=self.status_frame, frameColor=(0.96, 0.49, 0.14, 1),
            frameSize=(0, 0.008, -0.27, 0),
        )
        self.status = OnscreenText(
            **text_style, parent=self.status_frame, text="", pos=(0.05, -0.085),
            scale=0.041, align=TextNode.ALeft, mayChange=True,
        )
        self.status_notice = OnscreenText(
            **text_style, parent=self.status_frame, text="", pos=(0.05, -0.21),
            scale=0.037, align=TextNode.ALeft, mayChange=True,
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
        self.help["fg"] = (0.99, 0.98, 0.93, 1)
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
            frameColor=(1, 1, 1, 1), frameTexture=self.wide_texture,
            frameSize=(-0.8, 0.8, -0.80, 0.68)
        )
        self.panel_accent = DirectFrame(
            parent=self.panel, frameColor=(0.96, 0.49, 0.14, 1),
            frameSize=(-0.55, 0.55, -0.005, 0.005), pos=(0, 0, 0.61),
        )
        self.panel_title = OnscreenText(
            **text_style, parent=self.panel, text="", pos=(0, 0.46), scale=0.07, mayChange=True
        )
        self.panel_note = OnscreenText(
            **text_style, parent=self.panel, text="", pos=(0, 0.29), scale=0.040, mayChange=True
        )
        self.result_card = DirectFrame(
            parent=self.panel, frameColor=(1, 1, 1, 0.95),
            frameTexture=self.wide_texture,
            frameSize=(-0.79, 0.79, -0.16, 0.16), pos=(0, 0, -0.18),
        )
        self.panel_detail = OnscreenText(
            **text_style, parent=self.panel, text="", pos=(0, 0.12),
            scale=0.055, mayChange=True,
        )
        self.hero_label = OnscreenText(
            **text_style, text="COASTAL DRIVE", pos=(0.28, 0.71),
            scale=0.074, align=TextNode.ALeft,
        )
        self.hero_title = OnscreenText(
            **text_style, text="沿着海岸\n驶向远方", pos=(0.25, 0.19),
            scale=0.125, align=TextNode.ALeft,
        )
        self.hero_note = OnscreenText(
            **text_style, text="竞速 · 巡航 · 无限高速", pos=(0.28, -0.29),
            scale=0.042, align=TextNode.ALeft,
        )
        self.hero_line = DirectFrame(
            frameColor=(0.96, 0.49, 0.14, 1),
            frameSize=(0, 0.85, -0.005, 0.005), pos=(0.28, 0, -0.20),
        )
        self.menu_divider = OnscreenText(
            **text_style, parent=self.panel, text="其他", pos=(0, -0.255), scale=0.028,
        )
        self.menu_divider["fg"] = (0.37, 0.46, 0.49, 1)
        self.menu_rule_left = DirectFrame(
            parent=self.panel, frameColor=(0.38, 0.47, 0.50, 0.65),
            frameSize=(-0.36, -0.07, -0.002, 0.002), pos=(0, 0, -0.26),
        )
        self.menu_rule_right = DirectFrame(
            parent=self.panel, frameColor=(0.38, 0.47, 0.50, 0.65),
            frameSize=(0.07, 0.36, -0.002, 0.002), pos=(0, 0, -0.26),
        )
        self.buttons = [
            DirectButton(
                parent=self.panel,
                text="",
                scale=0.055,
                pos=(0, 0, 0.12 - i * 0.145),
                frameSize=(-6.5, 6.5, -0.7, 1.25),
                frameColor=(1, 1, 1, 1),
                frameTexture=(
                    self.button_texture, self.button_hover_texture,
                    self.button_pressed_texture, self.button_texture,
                ),
                text_fg=(0.07, 0.17, 0.23, 1),
                text_font=self.ui_font,
                relief=DGG.FLAT,
            )
            for i in range(6)
        ]
        if self.new_ui:
            self.canvas = Canvas(self)
            self.skin = UiSkin(self.loader)

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
        self.panel["frameSize"] = (-0.61, 0.61, -0.80, 0.68)
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
        self.panel["frameSize"] = (-0.8, 0.8, -0.80, 0.68)
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

    def _show_main_menu(self, notice):
        """主菜单页面；入口与操作在 MainMenuPage.ENTRIES 中声明。"""
        return MainMenuPage(self.aspect2d, self.canvas, self.skin, self, notice=notice)

    def _page_results(self):
        if self.session.simulation.track == "endless":
            return self._page_results_highway()
        return self._page_results_coastal()

    def _page_results_highway(self):
        snapshot = self.session.highway.snapshot
        if snapshot.challenge:
            title = "挑战成功" if snapshot.succeeded else "挑战失败"
            status = snapshot.reason
            tint = theme.GREEN if snapshot.succeeded else theme.RED
        else:
            title = "驾驶结束"
            status = "无限高速自由驾驶"
            tint = theme.INK
        rows = (
            ("road", "行驶距离", f"{snapshot.distance / 1000:.1f} km"),
            ("clock", "用时", f"{snapshot.elapsed:.2f} s"),
            ("collision", "碰撞", f"{snapshot.collisions} 次"),
        )
        return MessagePage(
            self.aspect2d, self.canvas, self.skin, title, (), rows,
            (("继续驾驶", self.session.start, True, "wheel"),
             ("返回主菜单", self.session.menu, False, "home")),
            tint=tint, status=status,
        )

    def _page_results_coastal(self):
        race = self.session.race.snapshot
        rows = ()
        buttons = (("继续驾驶", self.session.start, True, "wheel"),
                   ("返回主菜单", self.session.menu, False, "home"))
        if race.finished and race.last_lap is not None:
            title = "挑战失败" if race.invalidated else "挑战成功"
            status = f"圈速无效：{race.invalid_reason}" if race.invalidated else "有效完成计时挑战"
            rows = (("clock", "本圈", f"{race.last_lap:.3f} s"),
                    ("trophy", "最佳", f"{race.best_lap:.3f} s" if race.best_lap else "暂无"))
            tint = theme.RED if race.invalidated else theme.GREEN
            if race.save_error:
                status = f"{status} · {race.save_error}"
        elif self.session.mode == GameMode.FREE_DRIVE:
            title, status, tint = "驾驶结束", "滨海自由驾驶", theme.INK
            buttons = (("重新出发", self.session.start, True, "wheel"),
                       ("返回主菜单", self.session.menu, False, "home"))
        else:
            title, status, tint = "挑战失败", "挑战提前结束，本次不记录圈速", theme.RED
        return MessagePage(self.aspect2d, self.canvas, self.skin, title, (), rows, buttons,
                           tint=tint, status=status)

    def _hide_old_panel(self):
        """像素界面接管菜单时收起旧底板与驾驶 HUD；两套界面不叠在一起。"""
        self.panel.hide()
        self.result_card.hide()
        self.speed_frame.hide()
        self.telemetry_frame.hide()
        self.status_frame.hide()
        self.help_frame.hide()
        for item in (self.hero_label, self.hero_title, self.hero_note, self.hero_line,
                     self.menu_art, self.panel_accent, self.menu_divider,
                     self.menu_rule_left, self.menu_rule_right):
            item.hide()
        for button in self.buttons:
            button.hide()

    def _use_pixel_menu(self, phase):
        """主菜单走独立页面；车库预览仍在旧面板上编辑。"""
        return (
            self.new_ui
            and phase == Phase.MENU
            and self.garage is None
            and not self.highway_menu
            and not self.audio_settings_page
        )

    def _show_pixel_page(self, phase):
        """像素界面接管除车库外的所有页面；返回 False 表示该状态仍用旧界面。

        驾驶态没有像素页面，此时必须把已有页面收掉：否则从暂停恢复驾驶后，
        暂停页还留在屏幕上，和重新打开的旧 HUD 叠成一团。
        """
        if not self.new_ui:
            return False
        if self.garage is not None:
            # 车库预览仍在旧面板上编辑，同样不能让像素页面留在屏幕上
            self._hide_pixel_page()
            self.page_name = None
            return False
        page = None
        if phase == Phase.MENU and not self.highway_menu and not self.audio_settings_page:
            notice = self.appearance.notice
            self.appearance.notice = ""
            page = ("menu", lambda: self._show_main_menu(notice))
        elif phase == Phase.PAUSED:
            page = ("pause", self._page_pause)
        elif phase == Phase.RESULTS:
            page = ("results", self._page_results)
        elif phase == Phase.MENU and self.audio_settings_page:
            page = ("audio", self._page_audio)
        elif phase == Phase.MENU and self.highway_menu:
            page = ("highway", self._page_highway)
        if page is None:
            self._hide_pixel_page()
            self.page_name = None
            return False
        self._hide_old_panel()
        self._show_page(*page)
        return True

    def _show_page(self, name, build):
        """同一页面只在切换时重建：重建前收起上一个，点完按钮也收起。"""
        if self.page_name == name:
            return
        self._hide_pixel_page()
        self.page_name = name
        self.page = build()

    def _hide_pixel_page(self):
        if self.page is not None:
            self.page.destroy()
            self.page = None

    def _page_pause(self):
        self.driving_keys_held.clear()
        return MessagePage(
            self.aspect2d, self.canvas, self.skin, "已暂停",
            ("游戏已暂停",),
            (),
            (
                ("继续驾驶", self.session.resume, True, "wheel"),
                ("重新开始", self.session.start, False, "restart"),
                ("声音设置", self.choose_audio_settings, False, "volume"),
                ("返回主菜单", self.session.menu, False, "home"),
            ),
        )

    def _page_audio(self):
        settings = self.audio_settings
        return MessagePage(
            self.aspect2d, self.canvas, self.skin, "声音设置",
            (),
            (("volume", "主音量", f"{settings.master_volume}%"),
             ("note", "效果音量", f"{settings.effects_volume}%")),
            (
                ("主音量 -10%", lambda: self.adjust_audio_volume("master", -10), True, "volume"),
                ("主音量 +10%", lambda: self.adjust_audio_volume("master", 10), False, "volume"),
                ("效果音量 -10%", lambda: self.adjust_audio_volume("effects", -10), False, "note"),
                ("效果音量 +10%", lambda: self.adjust_audio_volume("effects", 10), False, "note"),
                ("返回", self.back_from_audio_settings, False, "arrow"),
            ),
            status=settings.notice or None,
        )

    def _page_highway(self):
        density = self.highway_density_keys[self.highway_density_index]
        shape = "弯坡高速" if self.highway_shape == "hills" else "直线高速"
        return MessagePage(
            self.aspect2d, self.canvas, self.skin, "无限高速",
            ("选择道路形态与车流密度后出发",),
            (("road", "道路", shape), ("car", "车流", TRAFFIC_DENSITIES[density].label)),
            (
                ("切换道路形态", self.cycle_highway_shape, False, "road"),
                ("切换车流密度", self.cycle_highway_density, False, "car"),
                ("自由驾驶", lambda: self.start_highway(self.highway_shape), True, "road"),
                ("5 公里无碰撞挑战",
                 lambda: self.start_highway(self.highway_shape,
                                            mode=GameMode.DISTANCE_CHALLENGE),
                 False, "flag"),
                ("返回", self.back_to_modes, False, "arrow"),
            ),
        )

    def refresh_panel(self):
        phase = self.session.phase
        panel_state = (phase, self.garage is not None, self.highway_menu,
                       self.audio_settings_page)
        if panel_state == self._shown_phase:
            return
        self._shown_phase = panel_state
        if self._show_pixel_page(phase):
            return
        if phase in (Phase.MENU, Phase.PAUSED, Phase.RESULTS):
            self.speed_frame.hide()
            self.telemetry_frame.hide()
            self.status_frame.hide()
            self.help_frame.hide()
        else:
            self.speed_frame.show()
            self.telemetry_frame.show()
            self.status_frame.show()
            self.help_frame.show()
        for button in self.buttons:
            button.hide()
        self.panel.show()
        self.panel_title.setText("COASTAL DRIVE")
        self.panel_note.setText("滨海环路 · 4 个检查点\n按 Enter 开始计时挑战")
        self.panel_detail.setText("")
        self.result_card.hide()
        self.menu_art.hide()
        for item in (self.hero_label, self.hero_title, self.hero_note, self.hero_line):
            item.hide()
        self.panel_title["fg"] = (0.07, 0.17, 0.23, 1)
        self.panel_title.setScale(0.07)
        self.panel_note.setScale(0.040)
        self.panel_note.setPos(0, 0.29)
        self.panel_detail.setPos(0, 0.10)
        self.panel["frameColor"] = (1, 1, 1, 1)
        self.panel_accent.hide()
        for item in (self.menu_divider, self.menu_rule_left, self.menu_rule_right):
            item.hide()
        appearance_notice = ""
        if phase == Phase.MENU and self.garage is None and not self.highway_menu and self.appearance.notice:
            appearance_notice = self.appearance.notice
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
            self.hero_label.show()
            self.hero_label.setPos(-1.43, 0.84)
            self.hero_label.setScale(0.066)
            for item in (self.menu_divider, self.menu_rule_left, self.menu_rule_right):
                item.show()
            self.panel_title.setText("选择驾驶")
            self.panel_note.setText("选择模式，出发上路" + (f"\n{appearance_notice}" if appearance_notice else ""))
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
            self.result_card.show()
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
                self.panel_title["fg"] = (0.13, 0.40, 0.29, 1)
            elif self.panel_title.getText() == "挑战失败":
                self.panel_title["fg"] = (0.58, 0.17, 0.08, 1)
            else:
                self.panel_title["fg"] = (0.07, 0.17, 0.23, 1)
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
        note_width = 0.92 if self.garage is not None else 1.80 if phase == Phase.RESULTS else 1.37
        self.panel_note.setText(self.fit_lines(self.panel_note.getText(), note_width, 0.040))
        self.panel_detail.setText(self.fit_lines(self.panel_detail.getText(), 1.50, 0.055))
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
            button["frameColor"] = (1, 1, 1, 1)
            if index == 0 and self.garage is None and not self.audio_settings_page:
                button["frameTexture"] = (
                    self.button_primary_texture, self.button_hover_texture,
                    self.button_pressed_texture, self.button_primary_texture,
                )
                button["text_fg"] = (1, 1, 0.97, 1)
            else:
                button["frameTexture"] = (
                    self.button_texture, self.button_hover_texture,
                    self.button_pressed_texture, self.button_texture,
                )
                button["text_fg"] = (0.07, 0.17, 0.23, 1)
        for button, (label, action) in zip(self.buttons, options):
            button["text"] = label
            button["command"] = action
            button.show()
        self.layout_panel(phase, len(options))

    def layout_panel(self, phase, option_count):
        """每个页面复用按钮与文字，但使用独立的游戏界面构图。"""
        if phase == Phase.MENU and self.garage is None and not self.highway_menu and not self.audio_settings_page:
            self.panel.setPos(-0.91, 0, 0)
            self.panel["frameSize"] = (-0.67, 0.67, -0.89, 0.89)
            self.panel["frameTexture"] = self.panel_texture
            self.panel_title.setPos(0, 0.67)
            self.panel_title.setScale(0.092)
            self.panel_note.setPos(0, 0.51)
            self.panel_accent.setPos(0, 0, 0.83)
            self.menu_divider.setPos(0, -0.21)
            self.menu_rule_left.setPos(0, 0, -0.215)
            self.menu_rule_right.setPos(0, 0, -0.215)
            for i in range(option_count):
                self.buttons[i].setPos(0, 0, 0.30 - i * 0.18 if i < 3 else -0.36 - (i - 3) * 0.18)
        elif self.garage is not None:
            self.panel.setPos(0.98, 0, 0)
            self.panel["frameSize"] = (-0.66, 0.66, -0.89, 0.89)
            self.panel["frameTexture"] = self.panel_texture
            self.panel_title.setPos(0, 0.67)
            self.panel_title.setScale(0.10)
            self.panel_note.setPos(0, 0.47)
            self.panel_accent.setPos(0, 0, 0.83)
            for i in range(option_count):
                self.buttons[i].setPos(0, 0, -0.02 - i * 0.16)
        elif phase == Phase.RESULTS:
            self.panel.setPos(0, 0, 0)
            self.panel["frameSize"] = (-1.03, 1.03, -0.63, 0.63)
            self.panel["frameTexture"] = self.wide_texture
            self.panel_accent.setPos(0, 0, 0.57)
            self.panel_accent["frameSize"] = (-0.88, 0.88, -0.005, 0.005)
            self.panel_title.setPos(0, 0.35)
            self.panel_title.setScale(0.145)
            self.panel_note.setPos(0, 0.16)
            self.result_card.setPos(0, 0, -0.12)
            self.result_card["frameSize"] = (-0.78, 0.78, -0.125, 0.125)
            self.panel_detail.setPos(0, -0.072)
            for i in range(option_count):
                self.buttons[i].setPos(-0.64 + i * 0.64, 0, -0.42)
        else:
            self.panel.setPos(0, 0, 0)
            self.panel["frameSize"] = (-0.85, 0.85, -0.80, 0.80)
            self.panel["frameTexture"] = self.wide_texture
            self.panel_accent.setPos(0, 0, 0.74)
            self.panel_accent["frameSize"] = (-0.62, 0.62, -0.005, 0.005)
            self.panel_title.setPos(0, 0.57)
            self.panel_title.setScale(0.10)
            self.panel_note.setPos(0, 0.39)
            for i in range(option_count):
                self.buttons[i].setPos(0, 0, -0.02 - i * 0.155)

    def update(self, task):
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
        gear = "R" if state.player.gear < 0 else f"D{state.player.gear}"
        surface = "柏油" if state.player.surface == "asphalt" else "路肩 / 草地"
        race = self.session.race.snapshot
        if race.mode == GameMode.TIME_TRIAL:
            race_line = f"计时挑战   {race.elapsed:06.3f} s\n检查点 {race.checkpoints}/4"
            if race.invalidated:
                notice = f"圈速无效：{race.invalid_reason}"
            else:
                target = "终点" if race.checkpoints == 4 else f"检查点 {race.next_checkpoint}"
                race_line += f"   下一目标 {target}"
                notice = ""
        else:
            race_line = "滨海自由驾驶"
            notice = ""
            if self.session.simulation.track == "highway":
                race_line += f"\n距终点 {max(0, HIGHWAY_LENGTH - position.y):.0f} m"
            elif self.session.simulation.track == "endless":
                highway_snapshot = self.session.highway.snapshot
                title = "5公里无碰撞挑战" if highway_snapshot.challenge else "无限高速自由驾驶"
                distance = (
                    f"{highway_snapshot.distance:.0f} / {highway_snapshot.target:.0f} m"
                    if highway_snapshot.challenge else f"{highway_snapshot.distance / 1000:.2f} km"
                )
                race_line = f"{title}\n距离 {distance}   用时 {highway_snapshot.elapsed:.1f} s"
                notice = f"碰撞 {highway_snapshot.collisions} 次"
        self.speed.setText(f"{abs(state.player.speed) * 3.6:03.0f}")
        self.gear_rpm.setText(gear)
        self.rpm_bar["frameSize"] = (
            0.04, 0.04 + 0.54 * min(state.player.rpm / 6500, 1), -0.32, -0.29,
        )
        task_text = self.fit_lines(race_line, 0.68, 0.040)
        notice_text = self.fit_lines(
            " · ".join(item for item in (countdown, notice, self.session.notice) if item),
            0.68, 0.037,
        )
        self.status.setText(task_text)
        notice_y = -0.10 - 0.055 * (task_text.count("\n") + 1) - 0.03
        self.status_notice.setPos(0.05, notice_y)
        self.status_notice.setText(notice_text)
        bottom = min(-0.27, notice_y - 0.055 * (notice_text.count("\n") + 1) - 0.025)
        self.status_frame["frameSize"] = (0, 0.83, bottom, 0)
        self.status_accent["frameSize"] = (0, 0.008, bottom, 0)
        self.diagnostics.setText(
            f"Tick {self.session.current.tick}   Simulation 120 Hz\n"
            f"转速 {state.player.rpm:.0f} rpm\n"
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
        for widget in (
            self.speed_unit,
            self.speed,
            self.gear_rpm,
            self.rpm_track,
            self.rpm_bar,
            self.speed_accent,
            self.speed_frame,
            self.telemetry_frame,
            self.status,
            self.status_notice,
            self.status_frame,
            self.status_accent,
            self.help,
            self.help_frame,
            self.diagnostics,
            self.panel_title,
            self.panel_note,
            self.panel_detail,
            self.result_card,
            self.hero_label,
            self.hero_title,
            self.hero_note,
            self.hero_line,
            self.menu_art,
            self.menu_divider,
            self.menu_rule_left,
            self.menu_rule_right,
            self.panel_accent,
            *self.buttons,
            self.panel,
        ):
            widget.destroy()
        self.destroy()
        self._shutdown = True
