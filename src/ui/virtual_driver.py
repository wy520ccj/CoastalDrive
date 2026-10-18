"""方案库内的道路复测内容；顺序关闭原世界、A与B，不叠加物理会话。"""

from datetime import UTC, datetime

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame

from road_comparison import RoadComparison, comparison_rows, context_mismatches, export_comparison
from ui import theme
from ui.road_review import RoadReviewPanel
from vehicle_schemes import load_scheme
from vehicle_state import FIXED_DT


class VirtualDriverPanel:
    def __init__(self, app, schemes):
        self.app, self.schemes = app, schemes
        self.comparison = None
        self.identities, self.names = None, None
        self.report = None
        self.root = DirectFrame(parent=schemes.root, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.70, 1.70, -.86, .79), sortOrder=101, state=DGG.NORMAL)
        app.text("虚拟试车员 · 连续过门 A/B", -1.52, .63, .058, parent=self.root, font=app.heading_font)
        app.button("关闭", 1.42, .66, .28, self.hide, parent=self.root)
        app.text("固定目标60km/h · 同一闭环策略，按各车状态分别纠偏\n"
                 "μ=1.1封闭直线 / 游戏配置与原辅助 / 不更新玩家奖牌或最佳",
                 -1.52, .47, .036, theme.SEA, parent=self.root)
        self.scheme_names = app.text("", -1.52, .30, .037, parent=self.root)
        self.scheme_names.textNode.setWordwrap(80)
        self.progress = app.text("", -1.52, .17, .037, theme.SEA, parent=self.root)
        self.columns = [app.text("", x, .03, .037, parent=self.root) for x in (-1.52, -.30, .43, 1.13)]
        self.note = app.text("余量/侧偏按各自实际完成步统计；漏门方案没有有效用时。", -1.52, -.47,
                             .033, theme.SEA, parent=self.root)
        self.note.textNode.setWordwrap(88)
        self.failure = app.text("", -1.52, -.57, .031, theme.FAILURE, parent=self.root)
        self.failure.textNode.setWordwrap(85)
        self.run_button = app.button("运行道路 A/B", -1.18, -.73, .72, self.start, parent=self.root, accent=True)
        self.review = RoadReviewPanel(app, self)
        self.review_button = app.button("逐门复盘", -.37, -.73, .70, self.review.show, parent=self.root)
        self.report_button = app.button("导出/打开报告", .45, -.73, .73, self.open_report, parent=self.root)
        self.stop_button = app.button("取消/返回方案", 1.24, -.73, .72, self.hide, parent=self.root)
        self.root.hide()

    def show(self):
        self.app.blur_entries()
        self.schemes.name_entry["focus"] = 0
        try:
            items = (self.schemes.selected(0), self.schemes.selected(1))
        except ValueError as error:
            self.app.show_error("先保存两套方案再比较道路表现", error)
            return
        identities = tuple(item.id for item in items)
        if identities != self.identities:
            self.close()
            self.identities, self.names = identities, tuple(item.name for item in items)
            self.comparison, self.report = None, None
            for column in self.columns:
                column.setText("")
            self.progress.setText("先运行两次实际试车，再比较道路指标。")
            self.failure.setText("")
        self.scheme_names.setText(f"A：{self.names[0]}\nB：{self.names[1]}")
        self.report_button["state"] = DGG.NORMAL if self.comparison is not None and self.comparison.done else DGG.DISABLED
        self.review_button["state"] = (DGG.NORMAL if self.comparison is not None
            and self.comparison.done and self.comparison.records else DGG.DISABLED)
        self.root.show()

    def start(self):
        try:
            items = tuple(load_scheme(self.app.scheme_root, identity) for identity in self.identities)
            for item in items:
                item.records()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error("原始方案未通过校验，未开始道路试车", error)
            return
        self.close()
        self.comparison, self.report = None, None
        self.names = tuple(item.name for item in items)
        self.scheme_names.setText(f"A：{self.names[0]}\nB：{self.names[1]}")
        app = self.app
        # 保留原试验与草稿，只关闭其物理世界；道路复测不成为第二个同时运行的世界。
        if app.run_state is not None:
            app.record = app.active_record()
            app.run_state.close()
            app.run_state = None
        app.playing = False
        try:
            self.comparison = RoadComparison(items[0].vehicle, items[1].vehicle)
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            app.show_error("道路试车未开始，原试验保留", error)
            return
        self.run_button["state"] = self.report_button["state"] = DGG.DISABLED
        self.review_button["state"] = DGG.DISABLED
        self.failure.setText("")
        for column in self.columns:
            column.setText("")
        self.progress.setText("正在运行 A · 离线逐步计算，关闭可取消。")

    def update(self):
        comparison = self.comparison
        if comparison is None or comparison.done:
            return
        try:
            comparison.advance()
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            self.app.show_error("道路试车停止，已完成步保留", error)
        self.progress.setText(f"正在运行 {'AB'[comparison.index]} · 仿真 {comparison.run.ticks*FIXED_DT:.2f}s"
                              f" / 计算 {comparison.run.compute_seconds:.2f}s · 20Hz决策/120Hz物理")
        if comparison.done:
            self.present()
            self.save_report()

    def present(self):
        comparison = self.comparison
        rows = comparison_rows(comparison.records)
        if rows:
            self.columns[0].setText("指标\n"+"\n".join(row["label"]+" / "+row["unit"] for row in rows))
            for column, key in zip(self.columns[1:], ("A", "B", "delta"), strict=True):
                values = ["未完成" if row[key] is None else f"{row[key]:+.3f}" if key == "delta"
                          else f"{row[key]:.3f}" for row in rows]
                column.setText(("B−A" if key == "delta" else key)+"\n"+"\n".join(values))
        else:
            self.columns[0].setText("仅保留已完成的部分记录；B尚未完成，不生成A/B差值。")
        reasons = [f"{'AB'[index]}：{record.metadata['metrics']['reason']}" for index, record in enumerate(comparison.records)]
        self.failure.setText("\n".join(reasons))
        mismatches = context_mismatches(comparison.records)
        if mismatches:
            self.failure.setText("条件变化，不计算差值："+"、".join(mismatches))
        self.progress.setText({"complete": "两次实际试车已结束", "cancelled": "已取消，当前已完成步保留",
                               "failed": "物理求解失败，已完成步保留"}[comparison.status])
        self.run_button["state"] = self.report_button["state"] = DGG.NORMAL
        self.review_button["state"] = DGG.NORMAL if comparison.records else DGG.DISABLED

    def save_report(self):
        if self.comparison is None or not self.comparison.done:
            return False
        try:
            folder = self.app.output/(datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")+"-virtual-road")
            self.report = export_comparison(self.comparison, folder, self.names)
        except (OSError, ValueError, TypeError) as error:
            self.app.show_error("道路报告未保存，内存结果保留；可点击报告重试", error)
            return False
        self.note.setText("报告已保存；余量/侧偏截止各自终点或失败步，先看是否完成再比较。")
        return True

    def open_report(self):
        if self.report is None and not self.save_report():
            return
        self.app.last_report = self.report
        self.app.open_report()

    def close(self):
        self.review.hide()
        if self.comparison is not None:
            try:
                self.comparison.close()
            except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
                self.app.show_error("道路试车已关闭，部分记录整理失败", error)

    def escape(self):
        self.hide() if self.review.root.isHidden() else self.review.hide()

    def hide(self):
        self.close()
        if self.comparison is not None:
            self.present()
        self.root.hide()
