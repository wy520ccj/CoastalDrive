"""已完成的参考试验：对照游戏积分配置，保存车辆并进入实际驾驶。"""

from dataclasses import replace
from datetime import UTC, datetime

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, TransparencyAttrib

from lab_game_comparison import (
    GameComparison,
    comparison_report,
    export_comparison,
    reference_vehicle,
)
from lab_records import LabRecord, export_record
from ui import theme
from ui.lab_feedback import error_text, log_error
from ui.lab_widgets import rounded_panel


class DesignLoopPanel:
    def __init__(self, app):
        self.app = app
        self.comparison = None
        self.completed_records = None
        self.record = None
        self.report_path = None
        self.root = DirectFrame(parent=app.root, frameColor=(.04, .10, .14, .55),
                                frameSize=(-1.78, 1.78, -1, 1), sortOrder=85, state=DGG.NORMAL)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        # 动态指标更新时保留固定操作的字形，避免仍显示的按钮文字被回收。
        glyphs = TextNode('game-link-button-glyphs')
        glyphs.setFont(app.font)
        glyphs.setText('关闭返回工作台运行游戏对照保存车辆并试驾打开报告重试导出')
        self.button_geometry = glyphs.generate()
        DirectFrame(parent=self.root, frameColor=theme.PAPER_LIGHT, frameSize=(-1.70, 1.70, -.86, .79))
        app.text("把试验接到驾驶", -1.52, .64, .060, parent=self.root, font=app.heading_font)
        self.close_button = app.button("关闭", 1.50, .65, .27, self.hide, parent=self.root)
        self.info = app.text("", -1.52, .49, .036, theme.MUTED, parent=self.root)
        for x, title, note in ((-1.56, '01 · 对照计算配置', '同一工况与直接命令\n游戏每拍1次机械求解'),
                               (.04, '02 · 保存这次试验的车', '保留本次完整硬件\n进入滨海公路辅助驾驶')):
            rounded_panel(self.root, 'link-action', (x, x+1.52, -.06, .32), theme.PAPER)
            app.text(title, x+.08, .23, .044, parent=self.root, font=app.heading_font)
            app.text(note, x+.08, .14, .035, theme.MUTED, parent=self.root)
        self.compare_button = app.button("运行游戏对照", -.80, .005, 1.10, self.start_comparison, parent=self.root)
        self.drive_button = app.button("保存车辆并试驾", .80, .005, 1.24, self.drive, parent=self.root, accent=True)
        self.values, self.metric_titles = [], []
        for x, color in ((-1.56, theme.SEA), (-.50, theme.ORANGE), (.56, theme.INK)):
            rounded_panel(self.root, 'link-metric', (x, x+1., -.31, -.10), theme.PAPER)
            self.metric_titles.append(app.text('', x+.06, -.17, .035, color, parent=self.root))
            self.values.append(app.text('—', x+.06, -.27, .060, color, parent=self.root, font=app.heading_font))
        self.caption = app.text('', -1.52, -.38, .035, theme.MUTED, parent=self.root)
        self.progress = app.text('', -1.52, -.49, .035, theme.SEA, parent=self.root)
        self.progress.textNode.setWordwrap(86)
        DirectFrame(parent=self.root, frameColor=theme.PAPER, frameSize=(-1.52, 1.52, -.60, -.58))
        self.progress_bar = DirectFrame(parent=self.root, frameColor=theme.SEA,
            frameSize=(0., 0., -.60, -.58), pos=(-1.52, 0, 0))
        app.text('始终使用打开时的试验记录；编辑参数需重新试验后生效。', -1.52, -.66, .035,
                 theme.MUTED, parent=self.root)
        self.report_button = app.button("打开报告", -.98, -.75, .90, self.open_report, parent=self.root)
        self.retry_button = app.button('重试导出', .08, -.75, .90, self.export_completed, parent=self.root)
        self.back_button = app.button('返回工作台', 1.15, -.75, .90, self.hide, parent=self.root)
        self.report_button["state"] = DGG.DISABLED
        self.retry_button['state'] = DGG.DISABLED
        self.present_metrics()
        self.root.hide()

    def show(self):
        app = self.app
        app.blur_entries()
        for panel in (app.advanced_panel, app.manual_panel, app.details_panel, app.record_menu,
                      app.parameter_help.root, app.engineering_panel.root):
            panel.hide()
        if self.comparison is None:
            record = app.active_record()
            try:
                if record is None:
                    raise ValueError("请先完成一次参考试验，再打开游戏试驾与对照。")
                vehicle = reference_vehicle(record)
            except (ValueError, KeyError, TypeError) as error:
                app.show_error("暂无可应用车辆", error)
                return
            if app.run_state is not None:
                app.run_state.paused = True
            if record is not self.record:
                self.completed_records = None
                self.report_path = None
                self.progress['fg'] = theme.SEA
                self.progress.setText('选择计算对照，或保存这次试验的车去实际驾驶。')
            self.record = record
            summary = self.record.metadata["summary"]
            self.info.setText(f"{self.record.metadata['vehicle_name']} · 已完成 {summary['simulation_seconds']:.2f} s · "
                              f"参考每拍{vehicle.config.tire_substeps}个机械子步\n"
                              f"质量 {vehicle.config.mass:g} kg · 质心高度 {vehicle.config.center_of_mass_height:g} m · "
                              f"轮胎参考载荷 {vehicle.config.tire_reference_load:g} N")
            self.present_metrics()
            self.refresh_buttons()
        self.root.show()

    def hide(self):
        if self.comparison is not None:
            self.close()
            self.progress.setText("本次对照已停止，参考试验保留；可以重新运行。")
        self.root.hide()

    def folder(self, suffix):
        return self.app.output/(datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")+suffix)

    def start_comparison(self):
        if self.comparison is not None:
            return
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
        self.retry_button['state'] = DGG.DISABLED
        self.completed_records, self.report_path = None, None
        self.present_metrics()
        self.progress['fg'] = theme.SEA
        self.progress.setText("正在计算游戏积分配置；关闭面板会停止本次对照。")

    def update(self):
        comparison = self.comparison
        if comparison is None:
            return
        try:
            comparison.advance()
            self.progress.setText(f"游戏对照 {comparison.run.elapsed:.2f} s / "
                                  f"参考 {self.record.samples[-1]['time']:.2f} s")
            duration = self.record.samples[-1]['time']
            self.progress_bar['frameSize'] = (0., 3.04*min(.98, comparison.run.elapsed/duration), -.60, -.58)
            if not comparison.done:
                return
            self.completed_records = self.record, LabRecord.from_run(comparison.run)
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            self.progress.setText('对照计算失败，参考记录保留；可重新运行。')
            self.app.show_error("游戏对照失败，参考记录仍保留", error)
        comparison.close()
        self.comparison = None
        self.refresh_buttons()
        self.present_metrics()
        if self.completed_records is not None:
            self.export_completed()

    def export_completed(self):
        if self.completed_records is None:
            return
        try:
            path = export_comparison(*self.completed_records, self.folder('-game-comparison'))
        except (OSError, ValueError, RuntimeError) as error:
            message = '导出失败，完成数据已保留；点“重试导出”。'
            self.progress['fg'] = theme.FAILURE
            self.progress.setText(message+'\n'+error_text(error))
            self.app.notice.setText(message)
            log_error('对照未导出，完成记录保留', error)
            self.refresh_buttons()
            return
        self.app.last_report = self.report_path = path
        self.app.notice.dismiss()
        self.app.notice.setText('游戏对照已导出，完整记录保留；可在游戏联动页打开报告。')
        self.progress['fg'] = theme.SEA
        self.progress.setText('对照已保存 · 打开报告查看完整条件、曲线与差异。')
        self.refresh_buttons()

    def refresh_buttons(self):
        running = self.comparison is not None
        self.compare_button['state'] = self.drive_button['state'] = DGG.DISABLED if running else DGG.NORMAL
        self.report_button['state'] = DGG.NORMAL if self.report_path is not None else DGG.DISABLED
        self.retry_button['state'] = (DGG.NORMAL if not running and self.completed_records is not None
                                      and self.report_path is None else DGG.DISABLED)

    def present_metrics(self):
        if self.completed_records is None:
            for title, value, label in zip(self.metric_titles, self.values, ('参考记录', '游戏记录', '游戏 − 参考'), strict=True):
                title.setText(label)
                value.setText('—')
            self.caption.setText('对照完成后显示实际指标；两份完整记录单独保留。')
            self.progress_bar['frameSize'] = (0., 0., -.60, -.58)
            return
        report = comparison_report(*self.completed_records)
        metric = report['metrics'][0] if report['metrics'][0]['delta'] is not None else report['metrics'][1]
        for title, value, label, key in zip(self.metric_titles, self.values,
                ('参考 · '+metric['label'], '游戏 · '+metric['label'], '游戏 − 参考'),
                ('reference', 'game', 'delta'), strict=True):
            title.setText(label)
            value.setText('—' if metric[key] is None else f"{metric[key]:+.3f} m" if key == 'delta' else f"{metric[key]:.3f} m")
        self.caption.setText(f"公共命令 {report['common_seconds']:.3f}s · 参考{report['reference_ticks']}拍 / "
                             f"游戏{report['game_ticks']}拍 · 尚未设置合格线")
        self.progress_bar['frameSize'] = (0., 3.04, -.60, -.58)

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
        self.refresh_buttons()
