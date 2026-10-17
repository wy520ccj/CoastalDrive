"""已完成的参考试验：对照游戏积分配置，保存车辆并进入实际驾驶。"""

from dataclasses import replace
from datetime import UTC, datetime

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TransparencyAttrib

from lab_game_comparison import GameComparison, reference_vehicle
from lab_records import export_record
from ui import theme


class DesignLoopPanel:
    def __init__(self, app):
        self.app = app
        self.comparison = None
        self.record = None
        self.report_path = None
        self.root = DirectFrame(parent=app.root, frameColor=(.04, .10, .14, .55),
                                frameSize=(-1.78, 1.78, -1, 1), sortOrder=85, state=DGG.NORMAL)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        DirectFrame(parent=self.root, frameColor=theme.PAPER_LIGHT, frameSize=(-.94, 1.72, -.46, .76))
        app.text("实验车辆 → 游戏", -.80, .63, .05, parent=self.root, font=app.heading_font)
        app.button("关闭", 1.50, .65, .27, self.hide, parent=self.root)
        self.info = app.text("", -.80, .48, .038, parent=self.root)
        self.info.textNode.setWordwrap(60)
        app.text("对照：同一工况与直接命令，仅游戏采用每拍一次机械求解。\n"
                 "试驾：保存这次试验的车辆参数，进入滨海公路辅助驾驶。\n"
                 "修改面板后需重新试验；此处始终使用打开时的试验记录。",
                 -.80, .15, .035, parent=self.root)
        self.progress = app.text("", -.80, -.05, .035, theme.SEA, parent=self.root)
        self.compare_button = app.button("运行游戏对照", -.43, -.30, .66, self.start_comparison, parent=self.root)
        self.drive_button = app.button("保存车辆并试驾", .40, -.30, .82, self.drive, parent=self.root, accent=True)
        self.report_button = app.button("打开报告", 1.23, -.30, .50, self.open_report, parent=self.root)
        self.report_button["state"] = DGG.DISABLED
        self.root.hide()

    def show(self):
        app = self.app
        app.blur_entries()
        for panel in (app.advanced_panel, app.manual_panel, app.details_panel, app.record_menu,
                      app.parameter_help.root, app.engineering_panel.root):
            panel.hide()
        if self.comparison is None:
            self.record = app.active_record()
            try:
                if self.record is None:
                    raise ValueError("请先完成一次参考试验，再打开游戏试驾与对照。")
                vehicle = reference_vehicle(self.record)
            except (ValueError, KeyError, TypeError) as error:
                app.show_error("暂无可应用车辆", error)
                return
            if app.run_state is not None:
                app.run_state.paused = True
            summary = self.record.metadata["summary"]
            self.info.setText(f"{self.record.metadata['vehicle_name']} · 已完成 {summary['simulation_seconds']:.2f} s\n"
                              f"质量 {vehicle.config.mass:g} kg · 质心高度 {vehicle.config.center_of_mass_height:g} m\n"
                              f"轮胎参考载荷 {vehicle.config.tire_reference_load:g} N")
            self.progress.setText("游戏对照将生成两份完整记录和差异报告。")
            self.report_path = None
            self.report_button["state"] = DGG.DISABLED
        self.root.show()

    def hide(self):
        if self.comparison is not None:
            self.close()
            self.progress.setText("本次对照已停止，参考试验保留；可以重新运行。")
        self.root.hide()

    def folder(self, suffix):
        return self.app.output/(datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")+suffix)

    def start_comparison(self):
        if self.app.run_state is not None:
            self.app.record = self.record
            self.app.run_state.close()
            self.app.run_state = None
        try:
            self.comparison = GameComparison(self.record)
        except (OSError, ArithmeticError, ValueError, RuntimeError, KeyError, TypeError) as error:
            self.app.show_error("游戏对照未开始", error)
            return
        self.compare_button["state"] = DGG.DISABLED
        self.drive_button["state"] = DGG.DISABLED
        self.report_button["state"] = DGG.DISABLED
        self.progress.setText("正在计算游戏积分配置；关闭面板会停止本次对照。")

    def update(self):
        comparison = self.comparison
        if comparison is None:
            return
        try:
            comparison.advance()
            self.progress.setText(f"游戏对照 {comparison.run.elapsed:.2f} s / "
                                  f"参考 {self.record.samples[-1]['time']:.2f} s")
            if not comparison.done:
                return
            path = comparison.export(self.folder("-game-comparison"))
            self.app.last_report = path
            self.report_path = path
            self.report_button["state"] = DGG.NORMAL
            self.progress.setText(f"对照已保存 · 游戏终止：{comparison.run.reason or '参考命令结束'}\n"
                                  "点击打开报告查看差异；尚未设置合格阈值。")
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            self.app.show_error("游戏对照失败，参考记录仍保留", error)
        else:
            if not comparison.done:
                return
        comparison.close()
        self.comparison = None
        self.compare_button["state"] = DGG.NORMAL
        self.drive_button["state"] = DGG.NORMAL

    def open_report(self):
        self.app.last_report = self.report_path
        self.app.open_report()

    def drive(self):
        try:
            vehicle = reference_vehicle(self.record)
            report = export_record(self.record, self.folder("-applied-vehicle"), baseline=self.app.baseline)
            vehicle = replace(vehicle, report_path=str(report))
            vehicle.save()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error("车辆未应用，当前试验保留", error)
            return
        self.app.workspace_vehicle = vehicle
        self.app.next_drive = True
        self.app.back_to_game()

    def close(self):
        if self.comparison is not None:
            self.comparison.close()
            self.comparison = None
        self.compare_button["state"] = DGG.NORMAL
        self.drive_button["state"] = DGG.NORMAL
