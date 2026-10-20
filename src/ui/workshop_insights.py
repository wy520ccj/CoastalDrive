"""工坊A/B收益、预算与观察代价；操作仍交给原工坊。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode

from ui import theme
from ui.lab_widgets import rounded_panel


class WorkshopInsightsPanel:
    def __init__(self, workshop):
        app = workshop.app
        self.data = None
        self.root = DirectFrame(parent=workshop.root, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.70, 1.70, -.95, .79), sortOrder=110, state=DGG.NORMAL)
        self.labels = [app.text('A/B 试验解读', -1.52, .66, .063, parent=self.root, font=app.heading_font)]
        self.outcome = app.text('', -1.52, .55, .038, theme.SEA, parent=self.root)
        for left, right in ((-1.52, -.30), (-.24, .42), (.48, 1.52)):
            rounded_panel(self.root, 'insight-card', (left, right, .10, .48), theme.PAPER)
        self.primary = app.text('', -1.44, .39, .038, parent=self.root)
        self.labels.extend(app.text(label, x, .30, .035, theme.MUTED, parent=self.root)
                           for label, x in (('A 原车', -1.44), ('B 方案', -.90)))
        self.primary_values = [app.text('', x, .22, .048, color, parent=self.root)
                               for x, color in ((-1.44, theme.INK), (-.90, theme.SEA))]
        self.improvement = app.text('', -1.44, .14, .035, theme.SEA, parent=self.root)
        self.labels.append(app.text('改装预算', -.16, .39, .038, parent=self.root))
        self.budget = app.text('', -.16, .29, .050, parent=self.root)
        self.budget_bars = [rounded_panel(self.root, 'budget-point',
            (-.16+i*.16, -.03+i*.16, .21, .24), theme.MUTED, .008) for i in range(3)]
        self.budget_note = app.text('', -.16, .14, .035, parent=self.root)
        self.labels.append(app.text('硬件改动', .56, .39, .038, parent=self.root))
        self.changes = app.text('', .56, .30, .035, parent=self.root)
        self.changes.textNode.setWordwrap(25)

        rounded_panel(self.root, 'insight-metrics', (-1.52, 1.52, -.39, .055), theme.PAPER)
        self.metric_headers = []
        for label, x in (('观察与代价', -1.44), ('A 原车', -.10), ('B 方案', .65), ('B−A', 1.42)):
            text = app.text(label, x, -.025, .035, theme.MUTED, parent=self.root)
            if x != -1.44:
                text['align'] = TextNode.ARight
            self.metric_headers.append(text)
        self.metric_rows = []
        for index in range(4):
            z = -.12-index*.075
            if index % 2 == 0:
                rounded_panel(self.root, 'insight-row', (-1.47, 1.47, z-.024, z+.037), theme.PAPER_LIGHT, .008)
            row = []
            for x in (-1.44, -.10, .65, 1.42):
                text = app.text('', x, z, .035, theme.INK if x != 1.42 else theme.SEA, parent=self.root)
                if x != -1.44:
                    text['align'] = TextNode.ARight
                row.append(text)
            self.metric_rows.append(row)
        self.attribution = app.text('', -1.52, -.46, .035, theme.SEA, parent=self.root)
        self.attribution.textNode.setWordwrap(87)
        self.next = app.text('', -1.52, -.55, .035, parent=self.root)
        self.next.textNode.setWordwrap(87)
        self.basis = app.text('', -1.52, -.71, .035, theme.MUTED, parent=self.root)
        self.basis.textNode.setWordwrap(87)
        self.prepare = app.button('准备下一次B', -1.03, -.86, .86, workshop.prepare_next_trial, parent=self.root, accent=True)
        self.export = app.button('导出本次解读', 0., -.86, .86, workshop.export_interpretation, parent=self.root)
        self.back = app.button('返回工坊', 1.03, -.86, .86, self.hide, parent=self.root)
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
        self.improvement.setText(f"改善 {data['improvement_pct']:+.2f}%")
        over = data['cost'] > data['budget']
        color = theme.FAILURE if over else theme.SEA
        self.budget.setText(f"{data['cost']} / {data['budget']} 点")
        self.budget['fg'] = self.budget_note['fg'] = color
        self.budget_note.setText(f"超出 {data['cost']-data['budget']} 点" if over else '预算内')
        for index, bar in enumerate(self.budget_bars):
            bar.setColor(*(color if index < data['cost'] else (.78, .83, .81, 1.)))
        self.changes.setText('\n'.join(data['changes']))
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
        self.next.setText('下一步：'+data['next']['text'])
        self.basis.setText(data['basis'])
        self.prepare['state'] = DGG.NORMAL if data['next']['selection'] is not None else DGG.DISABLED
        self.root.show()

    def hide(self):
        self.root.hide()
