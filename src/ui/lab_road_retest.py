"""道路保存硬件的独立参考复测面板；原工作台A/B和驾驶车保持。"""

from datetime import UTC, datetime
from time import perf_counter

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TransparencyAttrib

from road_retest import RoadRetest, measured
from ui.lab_plot import LabPlot
from ui.lab_widgets import (
    BORDER,
    LAB_ACCENT_A,
    LAB_ACCENT_B,
    LAB_CARD,
    LAB_SURFACE,
    LAB_TEXT,
    LAB_TRACK,
    MUTED,
    rounded_panel,
)


class RoadRetestPanel:
    def __init__(self, app):
        self.app, self.comparison, self.report_path = app, None, None
        self.last_plot = 0.
        self.metrics = []
        self.root = DirectFrame(parent=app.root, frameColor=(.06, .08, .11, .48),
            frameSize=(-1.78, 1.78, -1, 1), sortOrder=120, state=DGG.NORMAL)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        rounded_panel(self.root, 'retest-edge', (-1.704, 1.704, -.864, .794), BORDER, .026)
        rounded_panel(self.root, 'retest-card', (-1.70, 1.70, -.86, .79), LAB_CARD, .024)
        app.text('道路 A/B · 标准复测', -1.52, .64, .060, parent=self.root, font=app.heading_font)
        app.text('保存硬件 → 同工况试验 → 对比收益与代价', -1.52, .54, .035, MUTED, parent=self.root)
        app.button('试验条件', 1.00, .65, .48, self.toggle_details, parent=self.root)
        app.button('关闭', 1.45, .65, .28, self.hide, parent=self.root)
        rounded_panel(self.root, 'protocol', (-1.56, 1.56, .37, .48), LAB_SURFACE)
        self.protocol = app.text('', -1.48, .405, .036, LAB_ACCENT_A, parent=self.root)
        self.cards = []
        for x, color, title in ((-1.56, LAB_ACCENT_A, 'A · 改装前'), (-.50, LAB_ACCENT_B, 'B · 改装后'),
                                (.56, LAB_TEXT, 'B − A · 复测差值')):
            rounded_panel(self.root, 'metric-card', (x, x+1., .07, .33), LAB_SURFACE)
            DirectFrame(parent=self.root, frameColor=color, frameSize=(x, x+.012, .12, .28))
            app.text(title, x+.06, .263, .036, color, parent=self.root)
            value = app.text('—', x+.06, .157, .072, color, parent=self.root, font=app.heading_font)
            detail = app.text('', x+.06, .097, .035, MUTED, parent=self.root)
            self.cards.append((value, detail))
        self.plots = [LabPlot(self.root, app.font, box, key) for box, key in (
            ((-1.56, -.03, -.48, .03), 'speed'), ((.03, 1.56, -.48, .03), 'ax'))]
        self.progress = app.text('', -1.52, -.56, .035, LAB_ACCENT_A, parent=self.root)
        self.bars = []
        for left, right, color in ((-1.52, -.03, LAB_ACCENT_A), (.03, 1.52, LAB_ACCENT_B)):
            DirectFrame(parent=self.root, frameColor=LAB_TRACK, frameSize=(left, right, -.595, -.582))
            self.bars.append(DirectFrame(parent=self.root, frameColor=color,
                frameSize=(0, 0, -.595, -.582), pos=(left, 0, 0)))
        self.result = app.text('', -1.52, -.66, .035, MUTED, parent=self.root)
        self.run_button = app.button('运行参考 A/B', -1.10, -.75, .92, self.start, parent=self.root, accent=True)
        self.export_button = app.button('导出 A/B', 0., -.75, .72, self.export, parent=self.root)
        self.back_button = app.button('返回道路对照', 1.10, -.75, .92, self.back, parent=self.root)
        self.back_button['state'] = DGG.NORMAL if app.on_back is not None else DGG.DISABLED
        self.details = DirectFrame(parent=self.root, frameColor=LAB_CARD,
            frameSize=(-1.57, 1.57, -.49, .48), sortOrder=10, state=DGG.NORMAL)
        app.text('本次标准工况', -1.45, .35, .047, parent=self.details, font=app.heading_font)
        self.info = app.text('', -1.45, .23, .036, MUTED, parent=self.details)
        self.info.textNode.setWordwrap(78)
        app.button('收起条件', 1.15, -.39, .54, self.toggle_details, parent=self.details)
        self.details.hide()
        self.root.hide()

    def prepare(self, pair):
        self.close()
        self.comparison = RoadRetest(pair)
        self.metrics = []
        self.report_path = None
        self.app.road_retest_button['state'] = DGG.NORMAL
        self.show()

    def show(self):
        if self.comparison is None:
            self.app.show_error('请先从道路A/B页带入两套保存硬件。')
            return
        self.app.blur_entries()
        self.app.record_menu.hide()
        if self.app.run_state is not None:
            self.app.run_state.paused = True
        self.app.playing = False
        a, b = self.comparison.options
        braking = a.maneuver == 'braking'
        self.plots[0].keys = ('speed',) if braking else ('path_error',)
        self.plots[1].keys = ('ax',) if braking else ('beta',)
        protocol = '80–0直线停车' if braking else '60km/h · 40m定圆 · 10秒 · 同控制策略'
        self.protocol.setText(f'{protocol} · 平路 μ={a.friction:g}     A 海蓝 / B 橙色')
        self.info.setText(f'{protocol} · 平路μ={a.friction:g}\n'
            '120 Hz参考积分 · 每拍2个机械子步 · 直接执行器命令\n\n'
            f'ABS A{"开" if a.abs_enabled else "关"}/B{"开" if b.abs_enabled else "关"} · '
            f'ESC A{"开" if a.esc_enabled else "关"}/B{"开" if b.esc_enabled else "关"} · 两车路面统一A条件\n'
            f'TCS A{"开" if self.comparison.configs[0].traction.tcs_enabled else "关"}/'
            f'B{"开" if self.comparison.configs[1].traction.tcs_enabled else "关"}\n'
            f'源路面 μ：A {self.comparison.pair["A"]["config"]["road_friction"]:g} / '
            f'B {self.comparison.pair["B"]["config"]["road_friction"]:g}\n\n'
            '硬件来自两份道路保存记录，通用参考外观。\n'
            '新复测单独保留；旧试验、草稿、当前驾驶车与道路成绩保持。\n'
            '导出含完整配置、曲线、快照与改动清单。')
        self.details.hide()
        self.refresh(plots=True)
        self.root.show()

    def toggle_details(self):
        self.details.show() if self.details.isHidden() else self.details.hide()

    def start(self):
        app = self.app
        if app.run_state is not None:
            app.record = app.active_record()
            app.run_state.close()
            app.run_state = None
        self.report_path = None
        self.metrics = []
        try:
            self.comparison.start()
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            self.comparison.cancel('failed')
            app.show_error('参考复测未开始，原工作区保留', error)
        self.refresh(plots=True)

    def update(self):
        if self.comparison is None or self.comparison.status != 'running':
            return
        try:
            self.comparison.advance()
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            self.comparison.cancel('failed')
            self.app.show_error('参考复测失败，完成步与原工作区保留', error)
        self.refresh(plots=perf_counter()-self.last_plot >= .3 or self.comparison.done)

    def refresh(self, *, plots=False):
        comparison = self.comparison
        running = comparison.status == 'running'
        self.run_button['state'] = DGG.DISABLED if running else DGG.NORMAL
        self.export_button['state'] = DGG.NORMAL if comparison.done else DGG.DISABLED
        names = {'ready': '两套硬件已准备 · 点击运行，依次计算 A → B', 'completed': 'A/B 已完成 · 可导出完整记录',
                 'cancelled': '复测已取消，已完成/部分记录保留', 'failed': '复测失败，已完成/部分记录保留'}
        if running:
            elapsed = comparison.run.elapsed if comparison.run is not None else 0.
            self.progress.setText(f'正在计算 {"AB"[len(comparison.records)]} · 仿真 {elapsed:.2f}s · 关闭可取消')
        else:
            self.progress.setText(names[comparison.status])
        records = list(comparison.records)
        if comparison.run is not None:
            records.append(comparison.run)
        elif comparison.partial is not None and len(records) < 2:
            records.append(comparison.partial)
        if plots:
            for plot in self.plots:
                plot.update(tuple(records)+(None,)*(2-len(records)))
            self.last_plot = perf_counter()
        report = comparison.report() if not running else None
        if len(self.metrics) < len(comparison.records):
            self.metrics.extend(measured(record) for record in comparison.records[len(self.metrics):])
        braking = comparison.options[0].maneuver == 'braking'
        for index, (value, detail) in enumerate(self.cards[:2]):
            config = comparison.configs[index]
            detail.setText(f'前制动 {config.front_brake_share:.0%}' if braking else
                           f'前胎侧偏刚度 {config.lateral_stiffness/1000:g}k')
            metric = self.metrics[index] if index < len(self.metrics) else None
            value.setText(f'{metric["primary"]:.3f} m' if metric is not None and metric['valid'] else
                          '未正常结束' if metric is not None else
                          '计算中' if running and index == len(comparison.records) else '—')
            fraction = (1. if index < len(comparison.records) else
                        min(.98, records[index].samples[-1]['time']/comparison.options[index].duration)
                        if index < len(records) else 0.)
            self.bars[index]['frameSize'] = (0, 1.49*fraction, -.595, -.582)
        if comparison.done:
            rows = report['metrics']
            metric = '停车距离' if comparison.options[0].maneuver == 'braking' else '末2秒平均循迹误差'
            self.cards[2][0].setText(f"{report['delta']:+.3f} m" if report['comparable'] else '只并列')
            self.cards[2][1].setText('负值表示B更小' if report['comparable'] else '结束或条件不同')
            if braking:
                costs = [record.metadata['summary']['abs_ticks']/max(1, len(record.samples)-1)*100
                         for record in comparison.records]
                cost = f'ABS介入 A {costs[0]:.1f}% / B {costs[1]:.1f}%'
            else:
                speeds = ['—' if row['max_speed_error_kph'] is None else f"{row['max_speed_error_kph']:.2f}" for row in rows]
                cost = f'末窗速度偏差 A {speeds[0]} / B {speeds[1]} km/h'
            self.result.setText(f'{metric} · {cost}')
        else:
            self.cards[2][0].setText('—')
            self.cards[2][1].setText('两次完成后比较')
            self.result.setText('停车距离 / ABS介入比例 · 直接全制动，无道路驾驶时机差异' if braking else
                                '末2秒循迹误差 / 侧偏曲线 / 速度偏差 · 同一闭环控制策略')

    def export(self):
        folder = self.app.output/('road-retest-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
        try:
            self.report_path = self.comparison.export(folder)
        except (OSError, ValueError, RuntimeError) as error:
            self.app.show_error('复测导出失败，记录保留，可重试', error)
            return
        self.app.notice.setText('新参考A/B已单独导出：'+str(self.report_path))
        self.progress.setText('A/B 已导出 · '+self.report_path.parent.name)

    def hide(self):
        self.close()
        if self.comparison is not None:
            self.refresh(plots=True)
        self.root.hide()

    def close(self):
        if self.comparison is not None:
            self.comparison.cancel()

    def back(self):
        self.hide()
        self.app.back_to_game()

    def capture(self):
        if self.comparison is None:
            return None
        return {'comparison': self.comparison.capture(), 'visible': not self.root.isHidden(), 'report_path': self.report_path}

    def restore(self, state):
        self.comparison = RoadRetest.restore(state['comparison'])
        self.metrics = []
        self.report_path = state['report_path']
        self.app.road_retest_button['state'] = DGG.NORMAL
        if state['visible']:
            self.show()
