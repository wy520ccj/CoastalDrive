"""两道工坊的只读解读面板；准备/导出动作交给原工坊。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame

from ui import theme
from workshop_insights import row_text


class WorkshopInsightsPanel:
    def __init__(self, workshop):
        app = workshop.app
        self.data = None
        self.root = DirectFrame(parent=workshop.root, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.70, 1.70, -.86, .79), sortOrder=110, state=DGG.NORMAL)
        app.text('A/B 试验解读', -1.52, .64, .063, parent=self.root, font=app.heading_font)
        self.outcome = app.text('', .55, .64, .038, theme.SEA, parent=self.root)
        self.primary = app.text('', -1.52, .47, .038, parent=self.root)
        self.budget = app.text('', -1.52, .37, .034, theme.SEA, parent=self.root)
        app.text('改了什么', -1.52, .24, .041, parent=self.root)
        app.text('观察与代价 · A → B', -.05, .24, .041, parent=self.root)
        self.changes = app.text('', -1.52, .15, .034, parent=self.root)
        self.changes.textNode.setWordwrap(40)
        self.metrics = app.text('', -.05, .15, .031, parent=self.root)
        self.metrics.textNode.setWordwrap(49)
        self.attribution = app.text('', -1.52, -.24, .032, theme.SEA, parent=self.root)
        self.attribution.textNode.setWordwrap(92)
        self.next = app.text('', -1.52, -.37, .031, parent=self.root)
        self.next.textNode.setWordwrap(97)
        self.basis = app.text('', -1.52, -.58, .025, theme.MUTED, parent=self.root)
        self.basis.textNode.setWordwrap(121)
        self.prepare = app.button('准备下一次B', -1.03, -.74, .86, workshop.prepare_next_trial, parent=self.root, accent=True)
        app.button('导出本次解读', 0., -.74, .86, workshop.export_interpretation, parent=self.root)
        app.button('返回工坊', 1.03, -.74, .86, self.hide, parent=self.root)
        self.root.hide()

    def show(self, data):
        self.data = data
        self.outcome.setText(data['outcome'])
        self.outcome.textNode.setWordwrap(28)
        self.primary.setText(row_text(data['primary']))
        self.budget.setText(f"改善{data['improvement_pct']:+.2f}% · 预算{data['cost']}/{data['budget']}")
        self.changes.setText('\n'.join(data['changes']))
        self.metrics.setText('\n'.join(f'{label}\nA {a:.3f} → B {b:.3f} {unit}（{b-a:+.3f}）'
            if a is not None and b is not None else label+'：旧快照未定义' for label, a, b, unit in data['rows']))
        self.attribution.setText(data['attribution'])
        self.next.setText('下一步：'+data['next']['text'])
        self.basis.setText(data['basis'])
        self.prepare['state'] = DGG.NORMAL if data['next']['selection'] is not None else DGG.DISABLED
        self.root.show()

    def hide(self):
        self.root.hide()
