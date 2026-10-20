"""方案库内的道路复测内容；顺序关闭原世界、A与B，不叠加物理会话。"""

from datetime import UTC, datetime

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import LineSegs, TextNode

from road_comparison import (
    RoadComparison,
    RoadResults,
    comparison_rows,
    context_mismatches,
    export_comparison,
)
from slalom_lesson import GATES
from ui import theme
from ui.lab_widgets import rounded_panel
from ui.road_review import RoadReviewPanel
from vehicle_parameters import config_from_document
from vehicle_schemes import load_scheme
from vehicle_state import FIXED_DT
from virtual_test_driver import target_x

METRICS = (('valid_seconds', '有效用时', 's'), ('gates', '通过门数', '/6'),
           ('minimum_clearance_m', '最小车身余量', 'm'), ('peak_beta_deg', '峰值侧偏', '°'),
           ('peak_roll_deg', '峰值侧倾', '°'), ('esc_seconds', 'ESC介入', 's'))
RESULT_NOTE = '轨迹与指标截止各自终点/失败步；漏门没有有效用时，玩家成绩独立。'


class VirtualDriverPanel:
    def __init__(self, app, schemes):
        self.app, self.schemes = app, schemes
        self.comparison = None
        self.identities, self.names = None, None
        self.report = None
        self.shown_records = -1
        self.lateral_limit = 4.
        self.root = DirectFrame(parent=schemes.root, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.70, 1.70, -.93, .79), sortOrder=101, state=DGG.NORMAL)
        glyphs = TextNode('virtual-road-button-glyphs')
        glyphs.setFont(app.font)
        glyphs.setText('关闭驾驶B连续过门运行道路AB逐门复盘导出打开报告取消返回方案')
        self.button_glyphs = glyphs
        self.button_geometry = glyphs.generate()
        self.title = app.text("虚拟试车员 · 连续过门 A/B", -1.52, .63, .058, parent=self.root, font=app.heading_font)
        self.close_button = app.button("关闭", 1.42, .66, .28, self.hide, parent=self.root)
        app.text("固定60 km/h · μ=1.1封闭直线 · 同一策略分别纠偏 · 游戏配置与原辅助",
                 -1.52, .51, .035, theme.SEA, parent=self.root)
        self.scheme_names, self.result_labels, self.progress_fills, self.distance_labels = [], [], [], []
        for side, left, color in ((0, -1.50, theme.SEA), (1, .07, theme.ORANGE)):
            rounded_panel(self.root, 'road-status', (left, left+1.43, .18, .43), theme.PAPER)
            name = app.text('', left+.08, .35, .038, color, parent=self.root)
            self.scheme_names.append(name)
            self.result_labels.append(app.text('', left+.08, .255, .045, parent=self.root))
            distance = app.text('', left+1.35, .255, .035, theme.MUTED, parent=self.root)
            distance['align'] = TextNode.ARight
            self.distance_labels.append(distance)
            rounded_panel(self.root, 'road-progress-track', (left+.08, left+1.35, .205, .22), (.80, .85, .83, 1.), .007)
            fill = rounded_panel(self.root, 'road-progress', (0., 1., 0., .015), color, .007)
            fill.setPos(left+.08, 0., .205)
            self.progress_fills.append(fill)
        rounded_panel(self.root, 'road-overview', (-1.50, -.05, -.38, .15), theme.PAPER)
        rounded_panel(self.root, 'road-metrics', (.04, 1.57, -.38, .15), theme.PAPER)
        app.text('实际轨迹', -1.42, .08, .035, parent=self.root)
        app.text('A', -.56, .08, .035, theme.SEA, parent=self.root)
        app.text('B', -.34, .08, .035, theme.ORANGE, parent=self.root)
        app.text('0', -1.42, -.35, .035, theme.MUTED, parent=self.root)
        self.path_legend = app.text('灰线为目标', -1.13, -.35, .035, theme.MUTED, parent=self.root)
        app.text('320m →', -.45, -.35, .035, theme.MUTED, parent=self.root)
        self.lateral_axis = app.text('', -1.43, .014, .035, theme.MUTED, parent=self.root)
        self.lines = self.root.attachNewNode('road-overview-lines')
        self.paths = []
        self.metric_headers = []
        for label, x in (('指标', .12), ('A', .91), ('B', 1.22), ('B−A', 1.50)):
            node = app.text(label, x, .08, .035, theme.MUTED, parent=self.root)
            if x != .12:
                node['align'] = TextNode.ARight
            self.metric_headers.append(node)
        self.metric_rows = []
        for index in range(6):
            row = []
            for x in (.12, .91, 1.22, 1.50):
                node = app.text('', x, .005-index*.063, .035,
                                theme.SEA if x == 1.50 else theme.INK, parent=self.root)
                if x != .12:
                    node['align'] = TextNode.ARight
                row.append(node)
            self.metric_rows.append(row)
        self.progress = app.text("", -1.52, -.45, .037, theme.SEA, parent=self.root)
        self.note = app.text(RESULT_NOTE, -1.52, -.75, .035, theme.SEA, parent=self.root)
        self.note.textNode.setWordwrap(88)
        self.failure = app.text("", -1.52, -.65, .035, theme.FAILURE, parent=self.root)
        self.failure.textNode.setWordwrap(85)
        self.drive_note = app.text("", -1.52, -.54, .035, theme.SEA, parent=self.root)
        self.drive_note.textNode.setWordwrap(52)
        self.drive_button = app.button("驾驶 B 连续过门", 1., -.55, 1.10, self.drive_slalom,
                                       parent=self.root, accent=True)
        self.run_button = app.button("运行道路 A/B", -1.18, -.86, .72, self.start, parent=self.root, accent=True)
        self.review = RoadReviewPanel(app, self)
        self.review_button = app.button("逐门复盘", -.37, -.86, .70, self.review.show, parent=self.root)
        self.report_button = app.button("导出/打开报告", .45, -.86, .73, self.open_report, parent=self.root)
        self.stop_button = app.button("取消/返回方案", 1.24, -.86, .72, self.hide, parent=self.root)
        self.root.hide()

    def set_scheme_names(self):
        for side, node in enumerate(self.scheme_names):
            node.setText(f"{'AB'[side]} · {self.names[side][:24]}")

    def point(self, distance, lateral):
        return (-1.42+distance/320*1.27, 0., -.14+lateral/self.lateral_limit*.15)

    def draw_paths(self, records):
        self.lines.removeNode()
        self.lines = self.root.attachNewNode('road-overview-lines')
        self.paths = []
        self.lateral_limit = max(4., max((abs(row['x']) for record in records for row in record.rows), default=0.))
        self.lateral_axis.setText(f'±{self.lateral_limit:g}m')
        grid = LineSegs()
        grid.setColor(.74, .79, .77, 1.)
        for lateral in (-self.lateral_limit, 0., self.lateral_limit):
            grid.moveTo(*self.point(0., lateral))
            grid.drawTo(*self.point(320., lateral))
        for distance, lateral in GATES:
            grid.moveTo(*self.point(distance, lateral-2.))
            grid.drawTo(*self.point(distance, lateral+2.))
        self.lines.attachNewNode(grid.create())
        target = LineSegs()
        target.setColor(*theme.MUTED)
        target.moveTo(*self.point(0., target_x(0.)))
        for distance in range(2, 321, 2):
            target.drawTo(*self.point(distance, target_x(distance)))
        self.lines.attachNewNode(target.create())
        for record, color in zip(records, (theme.SEA, theme.ORANGE)):
            path = LineSegs()
            path.setColor(*color)
            path.setThickness(2.5)
            path.moveTo(*self.point(0., record.snapshots[0].player.position[0]))
            # 仅概览稀疏采点，末点保留实际停止位置；完整逐拍数据仍属于原记录/复盘。
            for row in record.rows[::12]:
                path.drawTo(*self.point(row['position'], row['x']))
            if record.rows:
                row = record.rows[-1]
                path.drawTo(*self.point(row['position'], row['x']))
            self.paths.append(self.lines.attachNewNode(path.create()))

    def update_cards(self):
        comparison = self.comparison
        records = comparison.records if comparison is not None else ()
        for side in (0, 1):
            position = 0.
            if side < len(records):
                record = records[side]
                metrics = record.metadata['metrics']
                value = (f"已完成 · {metrics['valid_seconds']:.3f}s" if metrics['completed'] else
                         f"未完成 · {metrics['gates']}/6门")
                position = record.rows[-1]['position'] if record.rows else 0.
            elif comparison is not None and not comparison.done and side == comparison.index:
                value = f"试车中 · {comparison.run.lesson.snapshot.gates}/6门"
                position = comparison.run.rows[-1]['position'] if comparison.run.rows else 0.
            else:
                value = '等待试车'
            self.result_labels[side].setText(value)
            self.distance_labels[side].setText(f'{position:.0f} / 320m')
            self.progress_fills[side].setSx(1.27*max(0., min(1., position/320)))

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
            self.paint_records(())
            self.progress.setText("先运行两次实际试车，再比较道路指标。")
            self.failure.setText("")
            self.note.setText(RESULT_NOTE)
        self.set_scheme_names()
        self.run_button['state'] = DGG.NORMAL if self.comparison is None or self.comparison.done else DGG.DISABLED
        self.report_button["state"] = DGG.NORMAL if self.comparison is not None and self.comparison.done else DGG.DISABLED
        self.review_button["state"] = (DGG.NORMAL if self.comparison is not None
            and self.comparison.done and self.comparison.records else DGG.DISABLED)
        self.set_drive_state()
        self.update_cards()
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
        self.set_scheme_names()
        self.note.setText(RESULT_NOTE)
        self.paint_records(())
        self.update_cards()
        self.report_button['state'] = self.review_button['state'] = self.drive_button['state'] = DGG.DISABLED
        self.failure.setText('')
        self.progress.setText('正在准备 A · 原试验记录保留')
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
            self.progress.setText('本轮未开始，方案与原试验记录保留')
            app.show_error("道路试车未开始，原试验保留", error)
            return
        self.run_button["state"] = self.report_button["state"] = DGG.DISABLED
        self.review_button["state"] = DGG.DISABLED
        self.drive_button["state"] = DGG.DISABLED
        self.failure.setText("")
        self.update_cards()
        self.progress.setText("正在运行 A · 离线逐步计算，关闭可取消。")

    def update(self):
        comparison = self.comparison
        if comparison is None or comparison.done:
            return
        try:
            comparison.advance()
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            self.app.show_error("道路试车停止，已完成步保留", error)
        if self.shown_records != len(comparison.records) or comparison.done:
            self.present()
        self.update_cards()
        if comparison.done:
            self.save_report()
        else:
            self.progress.setText(f"正在运行 {'AB'[comparison.index]} · 仿真 {comparison.run.ticks*FIXED_DT:.2f}s"
                                  f" / 计算 {comparison.run.compute_seconds:.2f}s · 20Hz决策/120Hz物理")

    def paint_records(self, records):
        self.shown_records = len(records)
        rows = comparison_rows(records)
        for index, (key, label, unit) in enumerate(METRICS):
            values = [f'{label} ({unit})']
            for side in (0, 1):
                value = records[side].metadata['metrics'][key] if side < len(records) else None
                values.append('待完成' if side >= len(records) else
                              '未完成' if value is None and key == 'valid_seconds' else
                              '—' if value is None else f'{value:g}' if key == 'gates' else f'{value:.3f}')
            delta = rows[index]['delta'] if rows else None
            values.append('—' if delta is None else f'{delta:+.3f}')
            for node, value in zip(self.metric_rows[index], values, strict=True):
                node.setText(value)
        self.draw_paths(records)

    def present(self):
        comparison = self.comparison
        self.set_scheme_names()
        self.paint_records(comparison.records)
        reasons = [f"{'AB'[index]}：{record.metadata['metrics']['reason']}" for index, record in enumerate(comparison.records)
                   if not record.metadata['metrics']['completed']]
        self.failure.setText("\n".join(reasons))
        mismatches = context_mismatches(comparison.records)
        if mismatches:
            self.failure.setText("条件变化，不计算差值："+"、".join(mismatches))
        if comparison.done:
            self.progress.setText({"complete": "两次实际试车已结束", "cancelled": "已取消，当前已完成步保留",
                                   "failed": "物理求解失败，已完成步保留"}[comparison.status])
        self.run_button["state"] = self.report_button["state"] = DGG.NORMAL if comparison.done else DGG.DISABLED
        self.review_button["state"] = DGG.NORMAL if comparison.done and comparison.records else DGG.DISABLED
        self.set_drive_state()
        self.update_cards()

    def set_drive_state(self):
        available = self.comparison is not None and self.comparison.done and len(self.comparison.records) == 2
        self.drive_button["state"] = DGG.NORMAL if available else DGG.DISABLED
        if available:
            friction = self.comparison.records[1].metadata["original_vehicle"]["config"]["road_friction"]
            self.drive_note.setText(f"亲自过门沿用方案路面 μ={friction:g} / 当前输入模式\n虚拟复测基准 μ=1.1，玩家成绩独立记录。")
        else:
            self.drive_note.setText("完成两侧试车后，可用原B硬件亲自练习同一门位。")

    def checked_right(self):
        if self.comparison is None or not self.comparison.done or len(self.comparison.records) != 2:
            raise ValueError("B尚无冻结试车记录")
        item = load_scheme(self.app.scheme_root, self.identities[1])
        item.records()
        original = self.comparison.records[1].metadata["original_vehicle"]
        if (item.vehicle.design_id != original["design_id"]
                or config_from_document(original["config"], item.vehicle.config) != item.vehicle.config):
            raise ValueError("B硬件已经改变，请重新运行道路A/B")
        return item

    def drive_slalom(self):
        try:
            item = self.checked_right()
            item.vehicle.save()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error("B未进入过门课题，原对比保留", error)
            return
        self.app.workspace_vehicle = item.vehicle
        self.app.next_drive = self.app.next_slalom = True
        self.app.back_to_game()

    def load_right(self):
        try:
            item = self.checked_right()
            self.schemes.refresh(item.id)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error("原B方案未载回，对比保留", error)
            return
        self.schemes.load_right()

    def capture(self):
        if self.comparison is None:
            return None
        visible = not self.root.isHidden()
        reviewing = not self.review.root.isHidden()
        position = self.review.slider["value"]
        self.close()
        return {"identities": self.identities, "names": self.names,
            "records": tuple(self.comparison.records), "status": self.comparison.status,
            "report": self.report, "visible": visible, "reviewing": reviewing, "position": position}

    def restore(self, state):
        self.identities, self.names = state["identities"], state["names"]
        self.comparison = RoadResults(state["records"], state["status"])
        self.report = state["report"]
        self.set_scheme_names()
        self.present()
        if state["visible"]:
            self.schemes.show()
            for side, identity in enumerate(self.identities):
                matches = [i for i, item in enumerate(self.schemes.schemes) if item.id == identity]
                if matches:
                    self.schemes.indices[side] = matches[0]
                    self.schemes.build_menu(side)
            self.schemes.present()
            self.root.show()
            if state["reviewing"]:
                self.review.show()
                self.review.slider["value"] = state["position"]
                self.review.seek()

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
