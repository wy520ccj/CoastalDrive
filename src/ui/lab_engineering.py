"""工程指标按需显示，消费同一实验记录；不参与物理推进。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TransparencyAttrib

from lab_metrics import engineering_analysis
from ui import theme
from ui.lab_widgets import MUTED, rounded_panel


class EngineeringPanel:
    def __init__(self, app):
        self.app = app
        self.root = DirectFrame(parent=app.root, frameColor=(.04, .10, .14, .55),
                                frameSize=(-1.78, 1.78, -1, 1), sortOrder=100, state=DGG.NORMAL)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        rounded_panel(self.root, "engineering-card", (-1.48, 1.55, -.76, .74), theme.PAPER_LIGHT)
        app.text("工程指标", -1.35, .63, .048, parent=self.root, font=app.heading_font)
        app.button("关闭 · Esc", 1.27, .65, .40, self.hide, parent=self.root)
        self.basis = app.text("", -1.35, .52, .034, MUTED, parent=self.root)
        self.rows = [app.text("", -1.35+(index//5)*1.43, .35-(index%5)*.155, .036,
                              parent=self.root) for index in range(10)]
        self.notes = app.text("", -1.35, -.54, .032, MUTED, parent=self.root)
        self.notes.textNode.setWordwrap(79)
        for index, key in enumerate(("mfdd", "yaw_gain", "beta", "roll", "ltr_front", "ltr_rear",
                                      "utilization_fl", "utilization_fr", "utilization_rl", "utilization_rr")):
            target = DirectFrame(parent=self.root, relief=None, state=DGG.NORMAL,
                                 frameColor=(0, 0, 0, 0), frameSize=(0, 1.2, -.035, .05),
                                 pos=(-1.35+(index//5)*1.43, 0, .35-(index%5)*.155))
            app.bind_parameter(target, "metric."+key)
        app.text("完整计算区间与未满足条件原因随报告导出；关闭后可继续分析曲线。", -1.35, -.68,
                 .033, MUTED, parent=self.root)
        self.root.hide()

    def hide(self):
        self.root.hide()

    def show(self):
        record = self.app.active_record()
        if record is None:
            self.basis.setText("尚无真实试验记录")
            for row in self.rows:
                row.setText("")
            self.notes.setText("运行工况后查看；参数输入本身不生成工程结果。")
        else:
            summary = record.metadata["summary"]
            analysis = engineering_analysis(record.samples, record.snapshots, summary["options"], summary["reason"])
            baseline = self.app.baseline
            old = (engineering_analysis(baseline.samples, baseline.snapshots,
                                        baseline.metadata["summary"]["options"], baseline.metadata["summary"]["reason"])
                   if baseline is not None else None)
            self.basis.setText(f"{record.metadata['vehicle_name']} · 已完成 {summary['simulation_seconds']:.3f} s · "
                               + ("A 基线 / B 当前" if old else "当前记录"))
            for index, (text, item) in enumerate(zip(self.rows, analysis["metrics"], strict=True)):
                unit = "" if item["unit"] == "1" else " "+item["unit"]
                value = f"{item['value']:.3f}{unit}" if item["value"] is not None else "— 未满足工况条件"
                if old is not None:
                    previous = old["metrics"][index]["value"]
                    a = f"{previous:.3f}" if previous is not None else "—"
                    b = f"{item['value']:.3f}" if item["value"] is not None else "—"
                    value = f"A {a}    B {b}{unit}"
                text.setText(f"{item['label']}\n{value}")
            mfdd, gain = analysis["metrics"][:2]
            lines = ["MFDD："+mfdd["note"], "横摆增益："+gain["note"],
                     "附着利用率使用末子步实际力和同阶段预算；完成步轮荷用于左右转移分析。"]
            self.notes.setText("\n".join(lines))
        self.root.show()
