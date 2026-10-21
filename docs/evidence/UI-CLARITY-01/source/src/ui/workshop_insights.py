"""工坊A/B收益、预算与观察代价；操作仍交给原工坊。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode

from ui import theme
from ui.lab_diagrams import lengths
from ui.lab_widgets import rounded_panel


class WorkshopInsightsPanel:
    def __init__(self, workshop):
        app = workshop.app
        self.data = None
        self.root = DirectFrame(parent=workshop.root, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.78, 1.78, -1.5, 1.5), sortOrder=110, state=DGG.NORMAL)
        self.labels = [app.text('试验结果', -1.49, .65, .062, parent=self.root, font=app.heading_font)]
        self.outcome = app.text('', -1.49, .53, .040, theme.SEA, parent=self.root)
        app.button('返回改装', 1.21, .66, .54, self.hide, parent=self.root)
        rounded_panel(self.root, 'result-diagram', (-1.51, .43, -.15, .43), theme.PAPER)
        self.primary = app.text('', -1.40, .33, .040, theme.MUTED, parent=self.root)
        self.diagram = self.root.attachNewNode('result-lengths')
        self.labels.extend(app.text(label, -1.40, z, .040, color, parent=self.root)
                           for label, z, color in (('原装', .20, theme.SEA), ('改装后', -.05, theme.ORANGE)))
        self.primary_values = [app.text('', -.92, z, .043, color, parent=self.root)
                               for z, color in ((.20, theme.SEA), (-.05, theme.ORANGE))]
        self.improvement = app.text('', .59, .24, .070, theme.SEA, parent=self.root)
        app.text('改善幅度', .59, .36, .040, theme.MUTED, parent=self.root)
        self.budget = app.text('', .59, .09, .044, parent=self.root)
        self.budget_bars = [rounded_panel(self.root, 'budget-point',
            (.59+i*.20, .75+i*.20, .015, .04), theme.MUTED, .008) for i in range(3)]
        self.budget_note = app.text('', .59, -.09, .040, parent=self.root)
        app.text('改装项目', -1.49, -.28, .042, theme.MUTED, parent=self.root)
        self.changes = app.text('', -1.49, -.38, .042, parent=self.root)
        self.changes.textNode.setWordwrap(76)
        self.next = app.text('', -1.49, -.56, .042, parent=self.root)
        self.next.textNode.setWordwrap(76)
        self.details = DirectFrame(parent=self.root, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.78, 1.78, -1, .48), sortOrder=112, state=DGG.NORMAL)
        app.text('详细数据', -1.47, .35, .047, parent=self.details)
        self.metric_headers = []
        for label, x in (('指标', -1.44), ('原装', -.10), ('改装后', .65), ('变化', 1.42)):
            text = app.text(label, x, .22, .040, theme.MUTED, parent=self.details)
            if x != -1.44:
                text['align'] = TextNode.ARight
            self.metric_headers.append(text)
        self.metric_rows = []
        for index in range(4):
            z = .11-index*.09
            row = []
            for x in (-1.44, -.10, .65, 1.42):
                text = app.text('', x, z, .040, theme.INK if x != 1.42 else theme.SEA, parent=self.details)
                if x != -1.44:
                    text['align'] = TextNode.ARight
                row.append(text)
            self.metric_rows.append(row)
        self.attribution = app.text('', -1.47, -.30, .040, theme.SEA, parent=self.details)
        self.attribution.textNode.setWordwrap(80)
        self.basis = app.text('', -1.47, -.48, .040, theme.MUTED, parent=self.details)
        self.basis.textNode.setWordwrap(80)
        app.button('收起', 1.12, -.83, .48, self.details.hide, parent=self.details)
        self.details.hide()
        app.button('完整数据 ›', -1.12, -.83, .73, self.toggle_details, parent=self.root)
        self.prepare = app.button('调整参数', -.24, -.83, .80, workshop.prepare_next_trial, parent=self.root)
        self.export = app.button('导出报告', .60, -.83, .68, workshop.export_interpretation, parent=self.root)
        self.drive = app.button('保存并试驾', 1.16, -.68, .73, workshop.drive, parent=self.root, accent=True)
        self.back = app.button('返回工坊', 1.27, -.83, .55, self.hide, parent=self.root)
        glyphs = TextNode('insight-button-glyphs')
        glyphs.setFont(app.font)
        glyphs.setText('准备下一次B导出本次解读返回工坊')
        self.button_geometry = glyphs.generate()
        self.root.hide()

    def show(self, data):
        self.data = data
        self.outcome.setText(data['outcome'])
        self.outcome['fg'] = theme.SUCCESS if data['passed'] else theme.FAILURE
        label, a, b, unit = data['primary']
        self.primary.setText(label)
        for node, value in zip(self.primary_values, (a, b), strict=True):
            node.setText(f'{value:.3f} {unit}' if value is not None else '未定义')
        self.improvement.setText(f"{data['improvement_pct']:+.2f}%")
        self.diagram.removeNode()
        self.diagram = self.root.attachNewNode('result-lengths')
        if a is not None and b is not None:
            lengths(self.diagram, a, b, left=-1.30, right=.23, top=.14, gap=.25, vehicles=not data['topic'])
        self.drive['state'] = DGG.NORMAL if data['passed'] else DGG.DISABLED
        self.details.hide()
        over = data['cost'] > data['budget']
        color = theme.FAILURE if over else theme.SEA
        self.budget.setText(f"{data['cost']} / {data['budget']} 点")
        self.budget['fg'] = self.budget_note['fg'] = color
        self.budget_note.setText(f"超出 {data['cost']-data['budget']} 点" if over else '预算内')
        for index, bar in enumerate(self.budget_bars):
            bar.setColor(*(color if index < data['cost'] else (.78, .83, .81, 1.)))
        self.changes.setText(' · '.join(data['changes']))
        for index, nodes in enumerate(self.metric_rows):
            if index >= len(data['rows']):
                values = ('', '', '', '')
            else:
                label, a, b, unit = data['rows'][index]
                digits = 5 if unit == 'rad/s' else 3
                values = (f'{label} / {unit}', f'{a:.{digits}f}' if a is not None else '未定义',
                          f'{b:.{digits}f}' if b is not None else '未定义',
                          f'{b-a:+.{digits}f}' if a is not None and b is not None else '—')
            for node, value in zip(nodes, values, strict=True):
                node.setText(value)
        self.attribution.setText(data['attribution'])
        self.next.setText('方案已通过，可保存并试驾。' if data['passed'] else '调整参数后可重新试验。')
        self.basis.setText(data['basis'])
        self.prepare['state'] = DGG.NORMAL if data['next']['selection'] is not None else DGG.DISABLED
        self.root.show()

    def escape(self):
        self.hide() if self.details.isHidden() else self.details.hide()

    def toggle_details(self):
        self.details.show() if self.details.isHidden() else self.details.hide()

    def hide(self):
        self.details.hide()
        self.root.hide()
