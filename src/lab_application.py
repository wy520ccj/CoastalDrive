"""车辆实验视图：使用主窗口的渲染环境，持有自己的离线试验与分析。"""

import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import simplepbr
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import (
    DirectButton,
    DirectEntry,
    DirectFrame,
    OnscreenText,
)
from direct.showbase.DirectObject import DirectObject
from direct.showbase.ShowBase import ShowBase
from panda3d.core import GraphicsWindow, TextNode, TransparencyAttrib, loadPrcFileData

from lab_experiment import MANEUVERS, LabExperiment, LabOptions
from lab_inputs import MANEUVER_HINTS, LabInputError, active_fields, read_number
from lab_records import LabRecord, changed_conditions, export_record, load_record, recalculate
from lab_scene import LabScene
from paths import user_data
from suspension_bench import fit_bench
from suspension_bench import validate_metadata as validate_suspension_metadata
from tire_calibration import validate_fit_metadata
from ui import theme
from ui.lab_feedback import error_text, log_error
from ui.lab_widgets import MUTED, LabOptionMenu, button_textures
from vehicle_designs import DESIGN_VEHICLES, vehicle_design
from vehicle_parameters import config_from_document, load_vehicle_config, save_vehicle_config
from vehicle_state import VehicleCommand

INK = theme.INK
ACCENT = theme.SEA
PANEL = theme.PAPER_LIGHT
BUTTON = theme.PAPER
DISABLED_FIELD = (.88, .90, .88, 1)
DISABLED_INK = (.43, .49, .49, 1)


class VehicleLab(DirectObject):
    def __init__(self, *, offscreen=False, output=None, render_size=(1280, 720), workspace_vehicle=None, lab_workspace=None, engine=None, on_back=None, activate=True):
        self.owns_window = engine is None
        self.on_back = on_back
        if self.owns_window:
            loadPrcFileData("vehicle-lab", "\n".join(("window-title CoastalDrive · Vehicle Dynamics Lab",
            f"win-size {render_size[0]} {render_size[1]}", "sync-video 1", "threading-model /Draw",
            "window-type offscreen" if offscreen else "window-type onscreen", "audio-library-name null")))
        self.engine = ShowBase() if engine is None else engine
        if self.owns_window:
            self.engine.finalizeExit = self.engine.taskMgr.stop
        self.engine.disableMouse()
        self.engine.setBackgroundColor(*theme.PAPER)
        self.pipeline = (simplepbr.init(enable_shadows=True, max_lights=1, msaa_samples=4, shadow_bias=.0007)
                         if self.owns_window else engine.pipeline)
        self.engine.camLens.setNearFar(.1, 1500)
        self.font = theme.load_font("fonts/SourceHanSansSC-Bold.otf")
        # 正文按小字分辨率生成字形，避免160像素字形过度缩小时笔画忽细忽粗。
        self.font.setPixelsPerUnit(48)
        self.heading_font = theme.load_font()
        self.display_font = theme.load_font(theme.DISPLAY_FONT_FILE)
        self.root = DirectFrame(parent=self.engine.aspect2d, frameColor=(0, 0, 0, 0), relief=None,
                                frameSize=(-1.78, 1.78, -1, 1), state=DGG.DISABLED)
        self.output = Path(output) if output else user_data()/"experiments"
        self.next_workspace = None
        self.next_drive = False
        self.workspace_vehicle = workspace_vehicle
        self.run_state = None
        self.engineered_config = None
        self.engineered_vehicle_id = None
        self.parameter_metadata = None
        self.record = None
        self.baseline = None
        self.playing = False
        self.playhead = 0.
        self.play_speed = 1.
        self.view_index = 0
        self.last_plot = 0.
        self.last_report = None
        self._closed = False
        self._seeking = False
        self.pointer_pressed = False
        self.entries = {}
        self.field_labels = {}
        self.hovered_parameter = None
        self.focused_parameter = "speed"
        self.scene = LabScene(self.engine)
        self.build_ui()
        self.refresh_parameter_availability()
        self.scene.set_vehicle(vehicle_design("reference-rwd"))
        if lab_workspace is None and workspace_vehicle is not None:
            config = workspace_vehicle.config
            self.set_options(LabOptions(vehicle_id=workspace_vehicle.design_id, friction=config.road_friction,
                                        abs_enabled=config.braking.abs_enabled, esc_enabled=config.stability.esc_enabled))
            self.engineered_config = config
            self.engineered_vehicle_id = workspace_vehicle.design_id
            self.parameter_metadata = workspace_vehicle.parameter_metadata
            self.refresh_configuration_note()
            self.scene.set_vehicle(vehicle_design(workspace_vehicle.design_id), config)
            self.model_note.setText(f"{vehicle_design(workspace_vehicle.design_id).name} · 当前驾驶车辆")
            self.notice.setText("已带入当前驾驶车辆；完成试验后可对照游戏积分配置，或保存车辆并试驾。")
        self.engine.camera.setPos(102, -10, 5)
        self.engine.camera.lookAt(95, 0, .45)
        if lab_workspace is not None:
            lab_workspace.restore(self)
        elif workspace_vehicle is not None and workspace_vehicle.report_path is not None:
            folder = Path(workspace_vehicle.report_path).parent
            self.import_record(folder)
            self.last_report = Path(workspace_vehicle.report_path)
            if self.record is not None and (folder/"baseline-A").is_dir():
                try:
                    self.baseline = load_record(folder/"baseline-A")
                except (OSError, ValueError, KeyError, TypeError) as error:
                    self.show_error("A基线载入失败，当前B记录已恢复", error)
                self.present_summary(self.record.metadata["summary"])
                self.refresh_plots()
        if activate:
            self.activate()
        else:
            self.root.hide()

    def activate(self):
        self.root.show()
        self.accept("escape", self.escape)
        self.accept("space", self.hotkey, [self.toggle_pause])
        self.accept("period", self.hotkey, [self.single_step])
        self.accept("tab", self.cycle_entry, [1])
        self.accept("shift-tab", self.cycle_entry, [-1])
        self.accept("f1", self.show_parameter_help)
        self.accept("wheel_up", self.scroll_parameter_help, [-1])
        self.accept("wheel_down", self.scroll_parameter_help, [1])
        self.accept("mouse1-up", self.set_pointer, [False])
        self.engine.taskMgr.add(self.update, "lab-update")
        self.resize()

    def text(self, value, x, z, scale=.034, color=INK, parent=None, font=None):
        scale = max(.035, scale)
        return OnscreenText(parent=parent or self.root, text=value, font=font or self.font, fg=color,
            pos=(x, z), scale=scale, align=TextNode.ALeft, mayChange=True)

    def button(self, label, x, z, width, action, parent=None, accent=False):
        button = DirectButton(parent=parent or self.root, text=label, text_font=self.font,
            text_scale=.035, text_fg=(1, 1, 1, 1) if accent else INK, text_pos=(0, -.012),
            frameColor=(1, 1, 1, 1), frameTexture=button_textures(accent),
            frameSize=(-width/2, width/2, -.045, .045), borderWidth=(0, 0),
            relief=DGG.FLAT, pos=(x, 0, z), command=action, pressEffect=False)
        button.setTransparency(TransparencyAttrib.MAlpha)
        return button

    def field(self, key, label, value, z, *, x=-1.61, width=.30, parent=None):
        self.field_labels[key] = self.text(label, x, z, .039, MUTED, parent=parent)
        target = DirectFrame(parent=parent or self.root, frameColor=(0, 0, 0, 0), relief=None,
                             frameSize=(0, .31, -.015, .045), pos=(x, 0, z), state=DGG.NORMAL)
        self.bind_parameter(target, key)
        entry = DirectEntry(parent=parent or self.root, initialText=str(value), text_font=self.font,
            text_fg=INK, scale=.038, width=width/.038, numLines=1, focus=0,
            frameColor=(.94, .95, .92, 1), pos=(x+.34, 0, z-.003), relief=DGG.FLAT)
        self.entries[key] = entry
        self.bind_parameter(entry, key, focus=True)
        return entry

    def bind_parameter(self, widget, key, *, focus=False):
        widget.bind(DGG.ENTER, self.enter_parameter, [key])
        widget.bind(DGG.EXIT, self.leave_parameter, [key])
        if focus:
            widget["focusInCommand"] = self.focus_parameter
            widget["focusInExtraArgs"] = [key, widget]
            widget["focusOutCommand"] = self.blur_parameter
            widget["focusOutExtraArgs"] = [widget, widget["frameColor"]]
            widget.bind(DGG.B1PRESS, self.click_parameter, [key, widget])

    def click_parameter(self, key, entry, event=None):
        # 已有焦点时再点击不会触发focusIn，仍需重启数值编辑的窗口状态。
        self.focus_parameter(key, entry)

    def enter_parameter(self, key, event=None):
        self.hovered_parameter = key

    def leave_parameter(self, key, event=None):
        if self.hovered_parameter == key:
            self.hovered_parameter = None

    def focus_parameter(self, key, entry):
        if entry["state"] == DGG.DISABLED:
            entry["focus"] = 0
            return
        self.focused_parameter = key
        # 数值框不需要中文组词；IME开启时窗口会过滤普通字符消息。
        if isinstance(self.engine.win, GraphicsWindow):
            self.engine.win.closeIme()
        entry["frameColor"] = (.86, .93, .94, 1)

    def blur_parameter(self, entry, color):
        entry["frameColor"] = DISABLED_FIELD if entry["state"] == DGG.DISABLED else color

    def blur_entries(self):
        for entry in (*self.entries.values(), *self.manual_entries.values()):
            entry["focus"] = 0

    def cycle_entry(self, direction):
        if any(not panel.isHidden() for panel in (self.parameter_help.root, self.engineering_panel.root,
                                                  self.design_loop.root)):
            return
        entries = [entry for entry in (*self.entries.values(), *self.manual_entries.values())
                   if not entry.isHidden() and entry.guiItem.getActive()]
        focused = next((i for i, entry in enumerate(entries) if entry.guiItem.getFocus()), None)
        index = (focused+direction)%len(entries) if focused is not None else (0 if direction > 0 else -1)
        self.blur_entries()
        entries[index]["focus"] = 1

    def show_parameter_help(self):
        key = self.hovered_parameter or self.focused_parameter
        self.blur_entries()
        for menu in (self.vehicle_menu, self.maneuver_menu, self.abs_menu, self.esc_menu, self.plot_menu):
            menu.hidePopupMenu()
        try:
            self.parameter_help.show(key)
        except OSError as error:
            self.show_error("参数说明资源未能打开", error)

    def scroll_parameter_help(self, direction):
        if not self.parameter_help.root.isHidden():
            bar = self.parameter_help.content_scroll.verticalScroll
            bar["value"] = min(1., max(0., bar["value"]+direction*.12))

    def option(self, labels, x, z, width, command=None, parent=None, parameter=None):
        menu = LabOptionMenu(parent=parent or self.root, items=labels, text_font=self.font,
            item_text_font=self.font, item_text_scale=.038, item_text_fg=INK,
            item_text_pos=(.025, -.013), item_frameSize=(0, width, -.04, .04),
            item_frameColor=PANEL, item_relief=DGG.FLAT, item_borderWidth=(0, 0),
            item_pad=(0, 0), item_pressEffect=False,
            popupMenu_relief=DGG.FLAT, popupMenu_frameColor=(.68, .75, .75, 1),
            popupMenu_borderWidth=(0, 0),
            text_scale=.038, text_fg=INK, text_align=TextNode.ALeft, text_pos=(.025, -.013),
            frameSize=(0, width, -.04, .04), frameColor=BUTTON, relief=DGG.FLAT,
            pos=(x, 0, z), command=command, highlightColor=(.85, .91, .91, 1),
            popupMarker_pos=(width-.025, 0, 0), popupMarker_scale=.03,
            popupMarker_relief=DGG.FLAT, popupMarker_frameColor=(0, 0, 0, 0),
            popupMarker_text="▼", popupMarker_text_font=self.font,
            popupMarker_text_fg=MUTED, popupMarker_text_scale=.7,
            popupMarkerBorder=(0, 0), before_popup=self.blur_entries)
        if parameter is not None:
            self.bind_parameter(menu, parameter)
        return menu

    def build_ui(self):
        from ui.lab_workbench import build_workbench

        build_workbench(self)

    def read_options(self):
        config = self.engineered_config or DESIGN_VEHICLES[self.vehicle_menu.selectedIndex].config
        mode = tuple(MANEUVERS)[self.maneuver_menu.selectedIndex]
        defaults = self.default_options(mode)
        available = active_fields(mode, finite_drivetrain=config.finite_drivetrain)

        def read(key, default, **kwargs):
            return self.read_field(key, **kwargs) if key in available else default

        options = LabOptions(vehicle_id=defaults.vehicle_id, maneuver=mode,
            speed_kph=self.read_field("speed"), friction=self.read_field("mu"), duration=self.read_field("duration"),
            steering_deg=read("steer", defaults.steering_deg,
                              bounds=(-config.steering_degrees, config.steering_degrees)),
            onset=read("onset", defaults.onset), radius_m=read("radius", defaults.radius_m),
            right_friction=read("right_mu", defaults.right_friction),
            bump_height_m=read("bump_height", defaults.bump_height_m),
            bump_length_m=read("bump_length", defaults.bump_length_m),
            bump_distance_m=read("bump_distance", defaults.bump_distance_m),
            cg_height=self.read_field("cg", optional=True),
            tire_reference_load=self.read_field("tire_load", optional=True),
            abs_enabled=self.abs_menu.selectedIndex == 0, esc_enabled=self.esc_menu.selectedIndex == 1)
        if "onset" in available and options.onset >= options.duration:
            raise LabInputError("onset", "输入起始须小于试验时长，否则试验结束前不会施加输入。")
        return options

    def refresh_parameter_availability(self):
        mode = tuple(MANEUVERS)[self.maneuver_menu.selectedIndex]
        config = self.engineered_config or DESIGN_VEHICLES[self.vehicle_menu.selectedIndex].config
        available = active_fields(mode, finite_drivetrain=config.finite_drivetrain)
        for key, entry in (*self.entries.items(), *(("manual."+key, entry)
                            for key, entry in self.manual_entries.items())):
            enabled = key in available
            if not enabled:
                entry["focus"] = 0
            entry["state"] = DGG.NORMAL if enabled else DGG.DISABLED
            entry["frameColor"] = ((.86, .93, .94, 1) if entry.guiItem.getFocus()
                                    else (.94, .95, .92, 1)) if enabled else DISABLED_FIELD
            entry["text_fg"] = INK if enabled else DISABLED_INK
            # PGEntry持有各状态TextNode的副本，组件颜色更改后需同步到这些副本。
            for state in range(entry["numStates"]):
                entry.guiItem.setTextDef(state, entry.onscreenText.textNode)
            self.field_labels[key].setFg(MUTED if enabled else DISABLED_INK)
        self.field_labels["speed"].setText("目标车速 km/h" if mode in (
            "constant_radius", "double_lane_change") else "初速 km/h")
        self.parameter_hint.setText(MANEUVER_HINTS[mode]+"\n灰色项不参与本工况；质心/轮胎基准留空采用模型值。")
        ready = mode not in ("ride_bump", "ride_braking") or config.unsprung_enabled
        self.start_button["state"] = DGG.NORMAL if ready else DGG.DISABLED
        self.start_button["text"] = "开始试验" if ready else "需导入独立轮心模型"
        self.manual_button.show() if mode == "manual" else self.manual_button.hide()
        if mode != "manual":
            self.manual_panel.hide()

    def read_field(self, key, **options):
        return read_number(self.entries[key].get(), key, **options)

    def show_error(self, message, error=None):
        """外部输入错误就地定位；旧试验数据保留，物理失败记录另由运行状态管理。"""
        if error is not None:
            log_error(message, error)
            message += "："+error_text(error)
        if isinstance(error, LabInputError):
            self.blur_entries()
            if error.key.startswith("manual."):
                self.advanced_panel.hide()
                self.manual_panel.show()
                entry = self.manual_entries[error.key.split(".")[1]]
            else:
                self.manual_panel.hide()
                if error.key not in ("speed", "mu"):
                    self.advanced_panel.show()
                entry = self.entries[error.key]
            entry["focus"] = 1
        self.notice.error(message)

    def choose_vehicle(self, label):
        imported = self.engineered_config is not None
        if imported and DESIGN_VEHICLES[self.vehicle_menu.selectedIndex].id == self.engineered_vehicle_id:
            self.refresh_configuration_note()
            return
        self.engineered_config = None
        self.engineered_vehicle_id = None
        self.parameter_metadata = None
        self.refresh_configuration_note()
        self.notice.setText("车型已切换，原导入工程配置已解除；凸起试验需重新导入独立轮心工程模型"
                            if imported else "已选择车型；凸起试验需导入独立轮心工程模型")

    def refresh_configuration_note(self):
        config = self.engineered_config or DESIGN_VEHICLES[self.vehicle_menu.selectedIndex].config
        source = "工程模型" if self.engineered_config is not None else "车型默认"
        self.configuration_note.setText(f"{source} · 独立轮心" if config.unsprung_enabled
                                       else f"{source} · 无独立轮心")
        self.refresh_parameter_availability()

    def import_engineering(self, path):
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            design = DESIGN_VEHICLES[self.vehicle_menu.selectedIndex]
            config = config_from_document(document, design.config)
            metadata = document.get("metadata", {})
            if not isinstance(metadata, dict):
                raise TypeError("工程文件metadata须为对象，不能是数组或空值")
            validate_fit_metadata(metadata)
            validate_suspension_metadata(metadata)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.show_error("工程配置载入失败，原配置未更改", error)
            return
        self.notice.dismiss()
        self.engineered_config, self.parameter_metadata = config, metadata
        self.engineered_vehicle_id = design.id
        self.refresh_configuration_note()
        self.entries["mu"].enterText(str(config.road_friction))
        self.entries["cg"].enterText("")
        self.entries["tire_load"].enterText("")
        basis = metadata.get("basis", "导入工程配置，来源按文件声明")
        if self.run_state is None and self.record is None:
            self.model_note.setText(f"{design.name} · 导入工程模型")
        else:
            basis += "；将用于下次试验，当前结果仍使用原配置。"
        self.notice.setText(basis)
        self.record_menu.hide()

    def open_engineering(self):
        import tkinter as tk
        from tkinter import filedialog

        dialog = tk.Tk()
        dialog.withdraw()
        try:
            path = filedialog.askopenfilename(title="导入完整车辆工程模型", filetypes=[("车辆工程JSON", "*.json")])
        finally:
            dialog.destroy()
        if path:
            self.import_engineering(path)

    def import_suspension_bench(self, path):
        """对当前选定硬件换算部件数据；不触碰已运行记录或物理世界。"""
        try:
            raw = Path(path).read_bytes()
            base = self.engineered_config or DESIGN_VEHICLES[self.vehicle_menu.selectedIndex].config
            config, report = fit_bench(json.loads(raw), base)
            folder = self.output/("suspension-bench-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
            folder.mkdir(parents=True, exist_ok=False)
            (folder/"input.json").write_bytes(raw)
            save_vehicle_config(folder/"base-vehicle.json", base, metadata=self.parameter_metadata)
            (folder/"fit-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                          allow_nan=False), encoding="utf-8")
            if not report["passed"]:
                self.show_error("部件数据不符合当前线性本构，未应用；验证误差见台架报告。")
                return
            metadata = dict(self.parameter_metadata or {})
            metadata["suspension_calibration"] = report
            metadata["basis"] = ("悬架合成数据验证，非实测；其他硬件沿用当前模型" if report["input"]["source_kind"] == "synthetic"
                                 else "悬架台架拟合与安装运动比换算；其他硬件沿用当前模型")
            save_vehicle_config(folder/"candidate-vehicle.json", config, metadata=metadata)
            self.import_engineering(folder/"candidate-vehicle.json")
            self.advanced_panel.hide()
        except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as error:
            self.show_error("悬架台架载入失败，原配置未更改", error)

    def open_suspension_bench(self):
        import tkinter as tk
        from tkinter import filedialog

        dialog = tk.Tk()
        dialog.withdraw()
        try:
            path = filedialog.askopenfilename(title="导入悬架部件台架数据", filetypes=[("悬架台架JSON", "*.json")])
        finally:
            dialog.destroy()
        if path:
            self.import_suspension_bench(path)

    def set_options(self, options):
        self.vehicle_menu.set(next(i for i, design in enumerate(DESIGN_VEHICLES) if design.id == options.vehicle_id))
        self.blur_entries()
        self.maneuver_menu.set(tuple(MANEUVERS).index(options.maneuver), fCommand=0)
        self.select_maneuver_plot(options.maneuver)
        for key, value in (("speed", options.speed_kph), ("mu", options.friction),
                           ("duration", options.duration), ("steer", options.steering_deg),
                           ("onset", options.onset), ("radius", options.radius_m), ("right_mu", options.right_friction),
                           ("bump_height", options.bump_height_m), ("bump_length", options.bump_length_m),
                           ("bump_distance", options.bump_distance_m)):
            self.entries[key].enterText(str(value))
        self.abs_menu.set(0 if options.abs_enabled else 1)
        self.esc_menu.set(1 if options.esc_enabled else 0)
        self.entries["cg"].enterText("" if options.cg_height is None else str(options.cg_height))
        self.entries["tire_load"].enterText("" if options.tire_reference_load is None else str(options.tire_reference_load))
        self.refresh_parameter_availability()

    def start_experiment(self):
        try:
            options = self.read_options()
            config = self.engineered_config or vehicle_design(options.vehicle_id).config
            if options.maneuver in ("ride_bump", "ride_braking") and not config.unsprung_enabled:
                self.show_error("新试验未开始：当前车型没有独立轮心模型，请从“记录 → 导入工程模型”载入；已有结果保留。")
                return
            manual_command = self.read_manual_command(config) if options.maneuver == "manual" else None
        except ValueError as error:
            self.show_error("新试验未开始，已有结果仍属上次试验", error)
            return
        self.notice.dismiss()
        if self.run_state is not None:
            self.run_state.close()
            self.run_state = None
        self.record = None
        self.playing = False
        self.blur_entries()
        self.advanced_panel.hide()
        self.manual_panel.hide()
        self.details_panel.hide()
        self.record_menu.hide()
        self.clear_current_result()
        try:
            self.run_state = LabExperiment(options, config=self.engineered_config,
                                           parameter_metadata=self.parameter_metadata)
        except (ArithmeticError, ValueError, RuntimeError, OSError) as error:
            self.status.setText("初始化失败")
            self.show_error("试验初始化失败；工程模型入口：记录 → 导入工程模型"
                                if options.maneuver in ("ride_bump", "ride_braking")
                                and not (self.engineered_config or vehicle_design(options.vehicle_id).config).unsprung_enabled
                                else "试验初始化失败", error)
            return
        self.run_state.paused = False
        self.scene.set_vehicle(self.run_state.design, self.run_state.config)
        self.scene.set_trial(options, self.run_state.snapshots[0].player)
        basis = "工程初值" if options.vehicle_id.startswith("gr86") else "设计模型"
        if self.engineered_config is not None:
            basis = "导入工程模型"
        self.model_note.setText(f"{self.run_state.design.name} · {basis}")
        self.notice.setText("离线计算真实固定步；暂停后可拖动时间轴分析")
        self.manual_panel.show() if options.maneuver == "manual" else self.manual_panel.hide()
        self.manual_button.show() if options.maneuver == "manual" else self.manual_button.hide()
        if options.maneuver == "manual":
            self.run_state.manual_command = manual_command
        self.refresh_plots()
        self.show_sample(0)

    def apply_preset(self, selection):
        self.blur_entries()
        mode = tuple(MANEUVERS)[tuple(MANEUVERS.values()).index(selection)]
        options = self.default_options(mode)
        for key, value in (("speed", options.speed_kph), ("duration", options.duration),
                           ("onset", options.onset)):
            self.entries[key].enterText(str(value))
        self.select_maneuver_plot(mode)
        self.refresh_parameter_availability()

    def default_options(self, mode):
        design = DESIGN_VEHICLES[self.vehicle_menu.selectedIndex]
        config = self.engineered_config or design.config
        options = LabOptions(vehicle_id=design.id, maneuver=mode, friction=config.road_friction)
        if mode in ("constant_radius", "double_lane_change"):
            return replace(options, speed_kph=60.)
        if mode == "ride_bump":
            return replace(options, speed_kph=18., duration=3.)
        if mode == "ride_braking":
            return replace(options, speed_kph=30., duration=3., onset=.6)
        return options

    def reset_parameters(self):
        mode = tuple(MANEUVERS)[self.maneuver_menu.selectedIndex]
        self.set_options(self.default_options(mode))
        for key, value in (("throttle", "0"), ("brake", "0"), ("gear", "1"), ("clutch", "100")):
            self.manual_entries[key].enterText(value)
        self.notice.dismiss()
        self.notice.setText("已重置当前工况参数；工程模型、已有结果和A保留，重新开始试验后生效。")

    def select_maneuver_plot(self, mode):
        if mode in ("constant_radius", "double_lane_change"):
            self.set_plot_group("路径跟踪")
        elif mode in ("braking", "split_braking"):
            self.set_plot_group("制动响应")
        elif mode=="ride_bump":
            self.set_plot_group("车身 / 轮心振动")
        elif mode=="ride_braking":
            self.set_plot_group("制动响应")
        else:
            self.set_plot_group("转向响应")

    def toggle_pause(self):
        if self.playing:
            self.playing = False
            return
        if self.run_state is not None and not self.run_state.done:
            self.run_state.paused = not self.run_state.paused
            self.playing = False
            if not self.run_state.paused:
                self.record = None

    def single_step(self):
        if self.run_state is None:
            if self.record is not None:
                self.playing = False
                self.show_sample(self.view_index+1)
                self.playhead = self.record.samples[self.view_index]["time"]
            else:
                self.show_error("尚无试验数据，请先开始试验。")
            return
        if self.run_state.done:
            return
        self.run_state.paused = True
        self.playing = False
        self.record = None
        try:
            self.run_state.step()
        except (ArithmeticError, ValueError, RuntimeError) as error:
            self.show_error("物理求解失败，已保留完成部分", error)
        self.refresh_plots()
        self.show_sample(len(self.run_state.samples)-1)

    def apply_manual(self):
        if tuple(MANEUVERS)[self.maneuver_menu.selectedIndex] != "manual":
            self.show_error("当前工况不使用手动执行器，请先选择“执行器输入”。")
            return
        design = DESIGN_VEHICLES[self.vehicle_menu.selectedIndex]
        run = self.run_state
        live = (run is not None and not run.done and run.options.maneuver == "manual"
                and run.options.vehicle_id == design.id)
        config = run.config if live else self.engineered_config or design.config
        try:
            command = self.read_manual_command(config)
            if live:
                run.manual_command = command
                self.record = None
            self.notice.dismiss()
            self.notice.setText("执行器请求已更新；仪表分别显示请求与实际响应" if live
                                else "初始执行器输入已确认，开始新试验后生效；已有结果保留。")
            self.blur_entries()
            self.manual_panel.hide()
        except ValueError as error:
            self.show_error("执行器输入未应用，原请求保持", error)

    def read_manual_command(self, config):
        values = {key: read_number(entry.get(), "manual."+key,
                    **({"bounds": (-1, len(config.gear_ratios))} if key == "gear" else {}))
                  for key, entry in self.manual_entries.items()
                  if config.finite_drivetrain or key not in ("gear", "clutch")}
        steering = self.read_field("steer", bounds=(-config.steering_degrees, config.steering_degrees))
        return VehicleCommand(steering=steering, throttle=values["throttle"]/100,
                              brake=values["brake"]/100,
                              direction=0 if config.finite_drivetrain else 1,
                              gear=int(values["gear"]) if config.finite_drivetrain else None,
                              clutch=values["clutch"]/100 if config.finite_drivetrain else None)

    def show_manual(self):
        if tuple(MANEUVERS)[self.maneuver_menu.selectedIndex] == "manual":
            self.blur_entries()
            self.advanced_panel.hide()
            self.details_panel.hide()
            self.record_menu.hide()
            self.manual_panel.show()

    def toggle_advanced(self):
        self.blur_entries()
        self.manual_panel.hide()
        self.details_panel.hide()
        self.record_menu.hide()
        self.advanced_panel.show() if self.advanced_panel.isHidden() else self.advanced_panel.hide()

    def toggle_details(self):
        self.blur_entries()
        self.advanced_panel.hide()
        self.manual_panel.hide()
        self.record_menu.hide()
        self.details_panel.show() if self.details_panel.isHidden() else self.details_panel.hide()

    def show_engineering(self):
        self.blur_entries()
        self.engineering_panel.show()

    def toggle_record_menu(self):
        self.blur_entries()
        self.advanced_panel.hide()
        self.manual_panel.hide()
        self.details_panel.hide()
        self.record_menu.show() if self.record_menu.isHidden() else self.record_menu.hide()

    def hotkey(self, action):
        # DirectEntry的focus选项不随鼠标聚焦同步，必须读取PGEntry实际状态。
        if any(not panel.isHidden() for panel in (self.advanced_panel, self.manual_panel,
                self.details_panel, self.record_menu, self.parameter_help.root, self.engineering_panel.root,
                self.design_loop.root, self.notice.root)):
            return
        if not any(entry.guiItem.getFocus() and not entry.isHidden()
                   for entry in (*self.entries.values(), *self.manual_entries.values())):
            action()

    def escape(self):
        if not self.notice.root.isHidden():
            self.notice.dismiss()
            return
        self.blur_entries()
        if not self.design_loop.root.isHidden():
            self.design_loop.hide()
            return
        if not self.parameter_help.root.isHidden():
            self.parameter_help.hide()
            return
        if not self.engineering_panel.root.isHidden():
            self.engineering_panel.hide()
            return
        for panel in (self.manual_panel, self.details_panel, self.advanced_panel, self.record_menu):
            if not panel.isHidden():
                panel.hide()
                return
        self.back_to_game()

    def active_record(self):
        if self.record is not None:
            return self.record
        return LabRecord.from_run(self.run_state) if self.run_state is not None else None

    def pin_baseline(self):
        record = self.active_record()
        if record is None:
            self.show_error("尚无试验结果，请先开始试验。")
            return
        if self.run_state is not None and not self.run_state.paused:
            self.show_error("先暂停或完成实验，再固定基线 A。")
            return
        self.notice.dismiss()
        self.baseline = record
        self.notice.setText(f"A 已固定：μ={record.metadata['summary']['options']['friction']:.2f}；修改配置后开始 B")
        self.refresh_plots()
        self.present_summary(record.metadata["summary"])

    def clear_baseline(self):
        self.baseline = None
        self.notice.dismiss()
        self.notice.setText("已清除基线 A；当前 B 结果保留。")
        self.refresh_plots()
        active = self.record if self.record is not None else self.run_state
        if active is not None:
            summary = active.metadata["summary"] if self.record is not None else active.summary()
            self.present_summary(summary)
        else:
            self.baseline_value.setText("—")
            self.result.setText("固定 A 后比较")

    def refresh_plots(self):
        # 运行中直接读取数组，避免10Hz重复生成完整配置/源码摘要。
        active = self.record if self.record is not None else self.run_state
        for plot in self.plots:
            plot.update((self.baseline, active))
        if active is not None:
            duration = active.samples[-1]["time"]
            self.timeline["range"] = (0, max(duration, 1/120))
            self.timeline["pageSize"] = max(duration, 1/120)
            snapshots = active.snapshots
            self.scene.trajectory(snapshots)

    def clear_current_result(self):
        """新试验尚无有效B；A基线仍保留供后续比较。"""
        self.view_index = 0
        self.playhead = 0.
        self.metric_label.setText("试验结果")
        self.metric.setText("—")
        self.candidate_value.setText("—")
        self.timing.setText("仿真  —\n计算  —")
        self.result.setText("等待有效 B" if self.baseline is not None else "固定 A 后比较")
        self.telemetry.setText("等待真实实验信号")
        self.wheel_telemetry.setText("")
        self.model_note.setText("等待新试验初始化")
        self._seeking = True
        self.timeline["range"] = (0, 1)
        self.timeline["value"] = 0
        self._seeking = False
        self.cursor_label.setText("t = —")
        self.refresh_plots()
        for plot in self.plots:
            plot.seek(0.)
        self.scene.clear_trial()

    def set_plot_group(self, selection):
        self.plot_menu.set(self.plot_menu["items"].index(selection), fCommand=0)
        names = ("制动响应", "转向响应",
                 "四轮法向载荷", "四轮滑移率", "轮胎力 / 轮速", "路径跟踪", "执行器响应",
                 "轮胎侧偏角", "附着利用率", "车身侧偏 / 侧倾", "左右载荷转移", "轮胎回正力矩",
                 "质心运动", "车身 / 轮心振动", "悬架行程 / 速度", "轮胎径向压缩")
        groups = ((("speed",), ("ax",)), (("yaw",), ("steering_request", "steering")),
                  (("sample_load_fl", "sample_load_fr"), ("sample_load_rl", "sample_load_rr")),
                  (("kappa_fl", "kappa_fr"), ("kappa_rl", "kappa_rr")),
                  (("fx_fl", "fy_fl"), ("omega_fl", "omega_rl")), (("path_error",), ("speed",)),
                  (("throttle_request", "engine_throttle"), ("brake_request", "pressure_fl")),
                  (("alpha_fl", "alpha_fr"), ("alpha_rl", "alpha_rr")),
                  (("utilization_fl", "utilization_fr"), ("utilization_rl", "utilization_rr")),
                  (("beta",), ("roll",)), (("ltr_front",), ("ltr_rear",)),
                  (("mz_fl", "mz_fr"), ("mz_rl", "mz_rr")),
                  (("cg_ax", "cg_ay"), ("cg_beta",)),
                  (("sprung_az",), ("hub_az_fl", "hub_az_rl")),
                  (("travel_fl", "travel_rl"), ("travel_rate_fl", "travel_rate_rl")),
                  (("radial_fl", "force_radial_fl"), ("radial_rl", "force_radial_rl")))
        for plot, keys in zip(self.plots, groups[names.index(selection)]):
            plot.keys = keys
        self.refresh_plots()
        for plot in self.plots:
            plot.seek(self.view_index/120)

    def show_sample(self, index):
        active = self.record if self.record is not None else self.run_state
        if active is None:
            return
        self.view_index = max(0, min(index, len(active.samples)-1))
        row = active.samples[self.view_index]
        snapshot = active.snapshots[self.view_index]
        self.scene.apply(snapshot)
        slips = ["—" if row[f"kappa_{wheel}"] is None else f"{row[f'kappa_{wheel}']:+.3f}"
                 for wheel in ("fl", "fr", "rl", "rr")]
        loads = [f"{row[f'load_{wheel}']:.0f}" for wheel in ("fl", "fr", "rl", "rr")]
        abs_state = "/".join("●" if row[f"abs_{wheel}"] else "○" for wheel in ("fl", "fr", "rl", "rr"))
        clutch = "—" if row["clutch"] is None else f"{row['clutch']:.0%}"
        clutch_request = "自动" if row["clutch_request"] is None else f"{row['clutch_request']:.0%}"
        gear_request = "自动" if row["gear_request"] is None else str(row["gear_request"])
        engine_throttle = "—" if row["engine_throttle"] is None else f"{row['engine_throttle']:.0%}"
        self.telemetry.setText(f"t  {row['time']:.3f} s   #{row['tick']}\n"
            f"车速     {row['speed']:7.2f} km/h\n"
            f"纵向     {row['ax']:+7.3f} m/s²\n"
            f"横向     {row['ay']:+7.3f} m/s²\n"
            f"横摆     {row['yaw']:+7.3f} rad/s\n"
            f"转角 请求 / 实际\n{row['steering_request']:+.2f}° / {row['steering']:+.2f}°\n"
            f"油门请求 {row['throttle_request']:.0%} / 响应 {engine_throttle}\n"
            f"制动请求 {row['brake_request']:.0%}\n"
            f"挡位 {gear_request} / {row['gear']}\n离合 {clutch_request} / {clutch}\n"
            f"转速 {row['rpm']:.0f} rpm")
        self.wheel_telemetry.setText(f"四轮接触信号\nABS  {abs_state}\n\n"
            f"滑移 FL/FR  {slips[0]} / {slips[1]}\n"
            f"       RL/RR  {slips[2]} / {slips[3]}\n"
            f"\n"
            f"施力轮荷 FL/FR  {loads[0]} / {loads[1]} N\n"
            f"       RL/RR  {loads[2]} / {loads[3]} N\n\n"
            f"压力 FL/FR  {row['pressure_fl']:.0%} / {row['pressure_fr']:.0%}\n"
            f"       RL/RR  {row['pressure_rl']:.0%} / {row['pressure_rr']:.0%}")
        for plot in self.plots:
            plot.seek(row["time"])
        self._seeking = True
        self.timeline["value"] = row["time"]
        self._seeking = False
        self.cursor_label.setText(f"t = {row['time']:.3f} s")

    def seek(self):
        # PGSlider的程序写值也会延迟发ADJUST；只有实际拖动才是分析输入。
        if self._seeking or not self.pointer_pressed:
            return
        self.playing = False
        if self.run_state is not None and not self.run_state.paused:
            self.run_state.paused = True
        self.playhead = self.timeline.getValue()
        self.show_sample(round(self.playhead*120))

    def set_pointer(self, pressed, event=None):
        # DirectGUI会屏蔽全局mouse1；按下从滑块自身进入，释放前消费最后位置。
        if not pressed:
            self.seek()
        self.pointer_pressed = pressed

    def toggle_playback(self):
        active = self.record if self.record is not None else self.run_state
        if active is None:
            self.show_error("尚无可回放数据，请先运行或载入试验。")
            return
        if self.run_state is not None:
            self.run_state.paused = True
        self.playing = not self.playing
        self.playhead = active.samples[self.view_index]["time"]
        if self.playhead >= active.samples[-1]["time"]:
            self.playhead = 0.

    def set_play_speed(self, selection):
        self.play_speed = {"1×": 1., "0.25×": .25, "0.5×": .5, "2×": 2.}[selection]

    def cycle_camera(self):
        self.scene.camera_mode = (self.scene.camera_mode+1)%3
        if self.run_state is None and self.record is None:
            self.scene.frame_vehicle()
        else:
            self.show_sample(self.view_index)

    def export(self):
        record = self.active_record()
        if record is None:
            self.show_error("尚无可导出数据，请先运行试验。")
            return
        try:
            folder = self.output/datetime.now(UTC).astimezone().strftime("%Y%m%d-%H%M%S-%f")
            self.last_report = export_record(record, folder, self.baseline)
            self.notice.dismiss()
            self.notice.setText("已导出 CSV 和报告，可从“记录”菜单打开")
        except (OSError, ValueError) as error:
            self.show_error("导出失败，请重试；未覆盖以前的导出", error)

    def open_report(self):
        self.record_menu.hide()
        if self.last_report is not None:
            try:
                os.startfile(self.last_report)
            except OSError as error:
                self.show_error("报告未能打开", error)
        else:
            self.show_error("尚无已导出报告，请先导出CSV和报告。")

    def open_record(self):
        import tkinter
        from tkinter import filedialog

        self.record_menu.hide()
        dialog = tkinter.Tk()
        dialog.withdraw()
        try:
            path = filedialog.askopenfilename(title="选择实验记录", filetypes=[("实验记录", "experiment.json")])
        finally:
            dialog.destroy()
        if path:
            self.import_record(Path(path).parent)

    def import_record(self, folder):
        try:
            record = load_record(folder)
            options = LabOptions(**record.metadata["summary"]["options"])
            design = vehicle_design(options.vehicle_id)
            config = load_vehicle_config(Path(folder)/"vehicle.json", design.config)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.show_error("记录载入失败，当前试验仍保留", error)
            return
        if self.run_state is not None:
            self.run_state.close()
            self.run_state = None
        self.record = record
        self.playing = False
        self.blur_entries()
        self.advanced_panel.hide()
        self.details_panel.hide()
        self.notice.dismiss()
        self.manual_panel.hide()
        self.set_options(options)
        self.engineered_config = config
        self.engineered_vehicle_id = design.id
        self.parameter_metadata = record.metadata.get("parameter_metadata")
        self.refresh_configuration_note()
        self.scene.set_vehicle(design, config)
        self.scene.set_trial(options, record.snapshots[0].player)
        self.model_note.setText(f"{record.metadata['vehicle_name']} · 已保存试验模型")
        self.status.setText("记录分析")
        self.notice.setText("已载入保存的试验；回放只读取记录，点击“开始试验”可按当前配置重新运行。")
        self.present_summary(record.metadata["summary"])
        self.refresh_plots()
        self.show_sample(0)

    def recalculate_record(self):
        self.record_menu.hide()
        record = self.active_record()
        if record is None:
            self.show_error("尚无可复算记录，请先运行或载入试验。")
            return
        if self.run_state is not None and not self.run_state.paused:
            self.show_error("先暂停或完成实验再复算。")
            return
        self.playing = False
        self.record = record
        if self.run_state is not None:
            self.run_state.close()
            self.run_state = None
        try:
            actual = recalculate(record)
        except (ArithmeticError, ValueError, RuntimeError, OSError) as error:
            self.show_error("复算失败，原记录仍可查看和导出", error)
            return
        self.notice.dismiss()
        self.baseline, self.record = record, actual
        exact = record.samples == actual.samples
        self.notice.setText("逐拍真实信号完全一致" if exact else "复算存在信号差异，A/B已保留")
        self.status.setText("复算分析")
        self.present_summary(actual.metadata["summary"])
        self.refresh_plots()
        self.show_sample(0)

    def resize(self):
        from ui.lab_workbench import VIEWPORT

        aspect = self.engine.getAspectRatio()
        scale = min(1., aspect/(16/9))
        self.root.setScale(scale)
        view = self.engine.cam.node().getDisplayRegion(0)
        left, right, bottom, top = VIEWPORT
        view.setDimensions(.5+left*scale/(2*aspect), .5+right*scale/(2*aspect),
                           .5+bottom*scale/2, .5+top*scale/2)
        self.engine.camLens.setAspectRatio((right-left)/(top-bottom))

    def present_summary(self, summary):
        distance = summary["stopping_distance_m"]
        value = distance if distance is not None else summary["distance_m"]
        self.metric_label.setText("停车距离" if distance is not None else "行驶距离")
        self.metric.setText(f"{value:.2f} m")
        self.candidate_value.setText(f"{value:.2f} m")
        self.baseline_value.setText("—")
        self.result.setText("固定 A 后比较")
        if self.baseline is not None:
            old_summary = self.baseline.metadata["summary"]
            old = old_summary["stopping_distance_m"]
            old_value = old if old is not None else old_summary["distance_m"]
            self.baseline_value.setText(f"{old_value:.2f} m")
            comparable = (old_summary["options"]["maneuver"] == summary["options"]["maneuver"]
                          and (old is None) == (distance is None))
            self.result.setText(f"Δ (B − A)   {value-old_value:+.2f} m" if comparable
                                else "工况或距离定义不同，仅并列展示")
        self.timing.setText(f"仿真  {summary['simulation_seconds']:.2f} s\n计算  {summary['compute_seconds']:.2f} s")

    def update(self, task):
        self.resize()
        self.design_loop.update()
        run = self.run_state
        if run is not None:
            if not run.paused and not run.done:
                try:
                    run.advance()
                except (ArithmeticError, ValueError, RuntimeError) as error:
                    self.show_error("物理求解失败，已停止并保留记录", error)
                self.show_sample(len(run.samples)-1)
            labels = {"stopped": "制动完成", "time_limit": "时长完成", "collision": "碰撞终止",
                      "reset": "复位终止", "failed": "求解失败"}
            self.status.setText(labels[run.reason] if run.done else "已暂停" if run.paused else "离线计算中")
            summary = run.summary()
            self.present_summary(summary)
            if run.done and self.record is None:
                self.record = LabRecord.from_run(run)
                if self.baseline is not None:
                    changes = changed_conditions(self.baseline, self.record)
                    self.notice.setText(f"B 已完成；与 A 的条件差异 {len(changes)} 项，可导出核对")
                self.refresh_plots()
        if perf_counter()-self.last_plot >= .1:
            if run is not None and not run.paused:
                self.refresh_plots()
            self.last_plot = perf_counter()
        if self.playing:
            active = self.record if self.record is not None else run
            self.playhead += self.engine.clock.getDt()*self.play_speed
            self.show_sample(round(self.playhead*120))
            if self.playhead >= active.samples[-1]["time"]:
                self.playing = False
        return task.cont

    def back_to_game(self):
        self.next_workspace = "game"
        if self.on_back is None:
            self.userExit()
        else:
            self.on_back()

    def capture_workspace(self):
        from ui.lab_workspace import LabWorkspace

        return LabWorkspace.capture(self)

    def run(self):
        self.engine.run()

    def userExit(self):
        self.engine.taskMgr.stop()

    def close_game(self):
        if self._closed:
            return
        self.engine.taskMgr.remove("lab-update")
        if self.owns_window:
            self.engine.taskMgr.remove("simplepbr update")
        self.ignoreAll()
        self.design_loop.close()
        if self.run_state is not None:
            self.run_state.close()
        self.scene.close()
        self.root.destroy()
        if self.owns_window:
            self.engine.destroy()
        self._closed = True
