"""车辆动力学实验室窗口：配置、离线运行、真实曲线与记录分析。"""

import json
import math
import os
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
from direct.showbase.ShowBase import ShowBase
from panda3d.core import TextNode, TransparencyAttrib, loadPrcFileData

from lab_experiment import MANEUVERS, LabExperiment, LabOptions
from lab_records import LabRecord, changed_conditions, export_record, load_record, recalculate
from lab_scene import LabScene
from paths import user_data
from tire_calibration import validate_fit_metadata
from ui import theme
from ui.lab_widgets import MUTED, LabOptionMenu, button_textures
from vehicle_designs import DESIGN_VEHICLES, vehicle_design
from vehicle_parameters import config_from_document, load_vehicle_config
from vehicle_state import VehicleCommand

INK = theme.INK
ACCENT = theme.SEA
PANEL = theme.PAPER_LIGHT
BUTTON = theme.PAPER


class VehicleLab(ShowBase):
    def __init__(self, *, offscreen=False, output=None, render_size=(1280, 720)):
        loadPrcFileData("vehicle-lab", "\n".join(("window-title CoastalDrive · Vehicle Dynamics Lab",
            f"win-size {render_size[0]} {render_size[1]}", "sync-video 1", "threading-model /Draw",
            "window-type offscreen" if offscreen else "window-type onscreen", "audio-library-name null")))
        super().__init__()
        self.disableMouse()
        self.setBackgroundColor(*theme.PAPER)
        self.pipeline = simplepbr.init(enable_shadows=True, max_lights=1, msaa_samples=4, shadow_bias=.0007)
        self.camLens.setNearFar(.1, 1500)
        self.font = theme.load_font("fonts/SourceHanSansSC-Bold.otf")
        # 正文按小字分辨率生成字形，避免160像素字形过度缩小时笔画忽细忽粗。
        self.font.setPixelsPerUnit(48)
        self.heading_font = theme.load_font()
        self.display_font = theme.load_font(theme.DISPLAY_FONT_FILE)
        self.root = DirectFrame(parent=self.aspect2d, frameColor=(0, 0, 0, 0), relief=None,
                                frameSize=(-1.78, 1.78, -1, 1), state=DGG.DISABLED)
        self.output = Path(output) if output else user_data()/"experiments"
        self.next_workspace = None
        self.run_state = None
        self.engineered_config = None
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
        self.timeline_hover = False
        self.timeline_target = 0.
        self.entries = {}
        self.hovered_parameter = None
        self.focused_parameter = "speed"
        self.scene = LabScene(self)
        self.build_ui()
        self.scene.set_vehicle(vehicle_design("reference-rwd"))
        self.camera.setPos(102, -10, 5)
        self.camera.lookAt(95, 0, .45)
        self.accept("escape", self.escape)
        self.accept("space", self.hotkey, [self.toggle_pause])
        self.accept("period", self.hotkey, [self.single_step])
        self.accept("f1", self.show_parameter_help)
        self.accept("mouse1", self.set_pointer, [True])
        self.accept("mouse1-up", self.set_pointer, [False])
        self.taskMgr.add(self.update, "lab-update")
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
        self.text(label, x, z, .039, MUTED, parent=parent)
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
            widget["focusInExtraArgs"] = [key]

    def enter_parameter(self, key, event=None):
        self.hovered_parameter = key

    def leave_parameter(self, key, event=None):
        if self.hovered_parameter == key:
            self.hovered_parameter = None

    def focus_parameter(self, key):
        self.focused_parameter = key

    def show_parameter_help(self):
        key = self.hovered_parameter or self.focused_parameter
        for menu in (self.vehicle_menu, self.maneuver_menu, self.abs_menu, self.esc_menu, self.plot_menu):
            menu.hidePopupMenu()
        self.parameter_help.show(key)

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
            popupMarkerBorder=(0, 0))
        if parameter is not None:
            self.bind_parameter(menu, parameter)
        return menu

    def build_ui(self):
        from ui.lab_workbench import build_workbench

        build_workbench(self)

    def read_options(self):
        return LabOptions(vehicle_id=DESIGN_VEHICLES[self.vehicle_menu.selectedIndex].id,
            maneuver=tuple(MANEUVERS)[self.maneuver_menu.selectedIndex],
            speed_kph=float(self.entries["speed"].get()), friction=float(self.entries["mu"].get()),
            duration=float(self.entries["duration"].get()), steering_deg=float(self.entries["steer"].get()),
            onset=float(self.entries["onset"].get()), radius_m=float(self.entries["radius"].get()),
            right_friction=float(self.entries["right_mu"].get()),
            bump_height_m=float(self.entries["bump_height"].get()),
            bump_length_m=float(self.entries["bump_length"].get()),
            bump_distance_m=float(self.entries["bump_distance"].get()),
            cg_height=float(self.entries["cg"].get()) if self.entries["cg"].get().strip() else None,
            tire_reference_load=float(self.entries["tire_load"].get()) if self.entries["tire_load"].get().strip() else None,
            abs_enabled=self.abs_menu.selectedIndex == 0, esc_enabled=self.esc_menu.selectedIndex == 1)

    def choose_vehicle(self, label):
        self.engineered_config = None
        self.parameter_metadata = None

    def import_engineering(self, path):
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
            design = DESIGN_VEHICLES[self.vehicle_menu.selectedIndex]
            config = config_from_document(document, design.config)
            metadata = document.get("metadata", {})
            validate_fit_metadata(metadata)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.notice.setText(f"工程配置载入失败：{error}")
            return
        self.engineered_config, self.parameter_metadata = config, metadata
        self.entries["mu"].enterText(str(config.road_friction))
        self.entries["cg"].enterText("")
        self.entries["tire_load"].enterText("")
        basis = metadata.get("basis", "导入工程配置，来源按文件声明")
        self.model_note.setText(f"{design.name} · 导入工程模型")
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

    def set_options(self, options):
        self.vehicle_menu.set(next(i for i, design in enumerate(DESIGN_VEHICLES) if design.id == options.vehicle_id))
        self.maneuver_menu.set(tuple(MANEUVERS).index(options.maneuver))
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

    def start_experiment(self):
        try:
            options = self.read_options()
        except ValueError as error:
            self.notice.setText(str(error))
            return
        if self.run_state is not None:
            self.run_state.close()
            self.run_state = None
        self.record = None
        self.playing = False
        self.advanced_panel.hide()
        self.details_panel.hide()
        self.record_menu.hide()
        try:
            self.run_state = LabExperiment(options, config=self.engineered_config,
                                           parameter_metadata=self.parameter_metadata)
        except (ArithmeticError, ValueError, RuntimeError, OSError) as error:
            self.status.setText("初始化失败")
            self.notice.setText(str(error))
            return
        self.run_state.paused = False
        self.scene.set_vehicle(self.run_state.design, self.run_state.config)
        self.scene.set_trial(options, self.run_state.snapshots[0].player)
        basis = "工程初值" if options.vehicle_id.startswith("gr86") else "设计模型"
        if self.engineered_config is not None:
            basis = "导入工程模型（来源见F1）"
        self.model_note.setText(f"{self.run_state.design.name} · {basis}")
        self.notice.setText("离线计算真实固定步；暂停后可拖动时间轴分析")
        self.manual_panel.show() if options.maneuver == "manual" else self.manual_panel.hide()
        self.manual_button.show() if options.maneuver == "manual" else self.manual_button.hide()
        if options.maneuver == "manual":
            self.apply_manual()
        self.refresh_plots()
        self.show_sample(0)

    def apply_preset(self, selection):
        mode = tuple(MANEUVERS)[tuple(MANEUVERS.values()).index(selection)]
        if mode in ("constant_radius", "double_lane_change"):
            self.entries["speed"].enterText("60")
            self.entries["duration"].enterText("12")
            self.set_plot_group("路径跟踪")
        elif mode in ("braking", "split_braking"):
            self.entries["speed"].enterText("100")
            self.set_plot_group("制动响应")
        elif mode=="ride_bump":
            self.entries["speed"].enterText("18")
            self.entries["duration"].enterText("3")
            self.set_plot_group("车身 / 轮心振动")
        elif mode=="ride_braking":
            self.entries["speed"].enterText("30")
            self.entries["duration"].enterText("3")
            self.entries["onset"].enterText("0.6")
            self.set_plot_group("制动响应")
        else:
            self.set_plot_group("转向响应")

    def toggle_pause(self):
        if self.run_state is not None and not self.run_state.done:
            self.run_state.paused = not self.run_state.paused
            self.playing = False
            if not self.run_state.paused:
                self.record = None

    def single_step(self):
        if self.run_state is None or self.run_state.done:
            return
        self.run_state.paused = True
        self.playing = False
        self.record = None
        try:
            self.run_state.step()
        except (ArithmeticError, ValueError, RuntimeError) as error:
            self.notice.setText(f"物理求解失败：{error}")
        self.refresh_plots()
        self.show_sample(len(self.run_state.samples)-1)

    def apply_manual(self):
        if self.run_state is None or self.run_state.options.maneuver != "manual":
            return
        try:
            values = {key: float(entry.get()) for key, entry in self.manual_entries.items()}
            steering = float(self.entries["steer"].get())
            if (any(not math.isfinite(value) for value in (*values.values(), steering))
                or any(not 0 <= values[key] <= 100 for key in ("throttle", "brake", "clutch"))
                or abs(steering) > self.run_state.config.steering_degrees
                or values["gear"] not in range(-1, len(self.run_state.config.gear_ratios)+1)):
                raise ValueError("踏板0～100%，挡位R=-1/N=0，转角须在车型范围内")
            self.run_state.manual_command = VehicleCommand(steering=steering,
                throttle=values["throttle"]/100, brake=values["brake"]/100,
                gear=int(values["gear"]), clutch=values["clutch"]/100)
            self.notice.setText("执行器请求已更新；仪表分别显示请求与实际响应")
            self.manual_panel.hide()
        except ValueError as error:
            self.notice.setText(str(error))

    def show_manual(self):
        if self.run_state is not None and self.run_state.options.maneuver == "manual":
            self.manual_panel.show()

    def toggle_advanced(self):
        self.advanced_panel.show() if self.advanced_panel.isHidden() else self.advanced_panel.hide()

    def toggle_details(self):
        self.details_panel.show() if self.details_panel.isHidden() else self.details_panel.hide()

    def show_engineering(self):
        self.engineering_panel.show()

    def toggle_record_menu(self):
        self.record_menu.show() if self.record_menu.isHidden() else self.record_menu.hide()

    def hotkey(self, action):
        if not any(entry["focus"] for entry in (*self.entries.values(), *self.manual_entries.values())):
            action()

    def escape(self):
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
            return
        if self.run_state is not None and not self.run_state.paused:
            self.notice.setText("先暂停或完成实验，再固定基线 A")
            return
        self.baseline = record
        self.notice.setText(f"A 已固定：μ={record.metadata['summary']['options']['friction']:.2f}；修改配置后开始 B")
        self.refresh_plots()

    def clear_baseline(self):
        self.baseline = None
        self.refresh_plots()

    def refresh_plots(self):
        # 运行中直接读取数组，避免10Hz重复生成完整配置/源码摘要。
        active = self.record if self.record is not None else self.run_state
        records = tuple(record for record in (self.baseline, active) if record is not None)
        for plot in self.plots:
            plot.update(records)
        if active is not None:
            duration = active.samples[-1]["time"]
            self.timeline["range"] = (0, max(duration, 1/120))
            snapshots = active.snapshots
            self.scene.trajectory(snapshots)

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
        self.timeline_target = row["time"]
        self.timeline["value"] = row["time"]
        self._seeking = False
        self.cursor_label.setText(f"t = {row['time']:.3f} s")

    def seek(self):
        # PGSlider的程序写值也会延迟发ADJUST；只有实际拖动才是分析输入。
        if self._seeking or not self.pointer_pressed:
            return
        if self.run_state is not None and not self.run_state.paused:
            self.run_state.paused = True
        self.playhead = self.timeline["value"]
        self.show_sample(round(self.playhead*120))

    def set_pointer(self, pressed):
        self.pointer_pressed = pressed and self.timeline_hover

    def set_timeline_hover(self, hovered, event):
        self.timeline_hover = hovered

    def toggle_playback(self):
        active = self.record if self.record is not None else self.run_state
        if active is None:
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
        self.show_sample(self.view_index)

    def export(self):
        record = self.active_record()
        if record is None:
            return
        try:
            folder = self.output/datetime.now(UTC).astimezone().strftime("%Y%m%d-%H%M%S-%f")
            self.last_report = export_record(record, folder, self.baseline)
            self.notice.setText("已导出 CSV 和报告，可从“记录”菜单打开")
        except (OSError, ValueError) as error:
            self.notice.setText(f"导出失败：{error}")

    def open_report(self):
        self.record_menu.hide()
        if self.last_report is not None:
            try:
                os.startfile(self.last_report)
            except OSError as error:
                self.notice.setText(str(error))

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
            self.notice.setText(f"载入失败：{error}")
            return
        if self.run_state is not None:
            self.run_state.close()
            self.run_state = None
        self.record = record
        self.playing = False
        self.manual_panel.hide()
        self.set_options(options)
        self.engineered_config = config
        self.parameter_metadata = record.metadata.get("parameter_metadata")
        self.scene.set_vehicle(design, config)
        self.scene.set_trial(options, record.snapshots[0].player)
        basis = "工程初值" if options.vehicle_id.startswith("gr86") else "设计模型"
        self.model_note.setText(f"{record.metadata['vehicle_name']} · {basis}")
        self.status.setText("记录分析")
        self.present_summary(record.metadata["summary"])
        self.refresh_plots()
        self.show_sample(0)

    def recalculate_record(self):
        self.record_menu.hide()
        record = self.active_record()
        if record is None:
            return
        if self.run_state is not None and not self.run_state.paused:
            self.notice.setText("先暂停或完成实验再复算")
            return
        self.record = record
        if self.run_state is not None:
            self.run_state.close()
            self.run_state = None
        try:
            actual = recalculate(record)
        except (ArithmeticError, ValueError, RuntimeError, OSError) as error:
            self.notice.setText(f"复算失败：{error}")
            return
        self.baseline, self.record = record, actual
        exact = record.samples == actual.samples
        self.notice.setText("逐拍真实信号完全一致" if exact else "复算存在信号差异，A/B已保留")
        self.status.setText("复算分析")
        self.present_summary(actual.metadata["summary"])
        self.refresh_plots()
        self.show_sample(0)

    def resize(self):
        from ui.lab_workbench import VIEWPORT

        aspect = self.getAspectRatio()
        scale = min(1., aspect/(16/9))
        self.root.setScale(scale)
        view = self.cam.node().getDisplayRegion(0)
        left, right, bottom, top = VIEWPORT
        view.setDimensions(.5+left*scale/(2*aspect), .5+right*scale/(2*aspect),
                           .5+bottom*scale/2, .5+top*scale/2)
        self.camLens.setAspectRatio((right-left)/(top-bottom))

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
            self.result.setText(f"Δ (B − A)   {value-old_value:+.2f} m")
        self.timing.setText(f"仿真  {summary['simulation_seconds']:.2f} s\n计算  {summary['compute_seconds']:.2f} s")

    def update(self, task):
        self.resize()
        run = self.run_state
        if run is not None:
            if not run.paused and not run.done:
                try:
                    run.advance()
                except (ArithmeticError, ValueError, RuntimeError) as error:
                    self.notice.setText(f"物理求解失败，已停止并保留记录：{error}")
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
            self.playhead += self.clock.getDt()*self.play_speed
            self.show_sample(round(self.playhead*120))
            if self.playhead >= active.samples[-1]["time"]:
                self.playing = False
        return task.cont

    def back_to_game(self):
        self.next_workspace = "game"
        self.userExit()

    def finalizeExit(self):
        self.taskMgr.stop()

    def close_game(self):
        if self._closed:
            return
        self.taskMgr.remove("lab-update")
        self.taskMgr.remove("simplepbr update")
        self.ignoreAll()
        if self.run_state is not None:
            self.run_state.close()
        self.scene.close()
        self.root.destroy()
        self.destroy()
        self._closed = True
