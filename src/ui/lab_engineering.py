"""工程指标按需显示，消费同一实验记录；不参与物理推进。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TransparencyAttrib

from lab_metrics import engineering_analysis
from ui.lab_widgets import BORDER, LAB_ACCENT_A, LAB_CARD, MUTED, rounded_panel
from vehicle_designs import vehicle_design
from vehicle_parameters import config_from_document

ENGINEERING_GROUPS = ("操稳 / 制动", "乘坐 / 接地", "ISO 平顺性", "理论—仿真对账")


def _analyze_record(record):
    summary = record.metadata["summary"]
    options = summary["options"]
    config = config_from_document(record.metadata["vehicle_config"], vehicle_design(options["vehicle_id"]).config)
    return engineering_analysis(record.samples, record.snapshots, options, summary["reason"], config=config)


class EngineeringPanel:
    def __init__(self, app):
        self.app = app
        self.root = DirectFrame(parent=app.root, frameColor=(.06, .08, .11, .45),
                                frameSize=(-1.78, 1.78, -1, 1), sortOrder=100, state=DGG.NORMAL)
        self.root.setTransparency(TransparencyAttrib.MAlpha)
        rounded_panel(self.root, "engineering-edge", (-1.484, 1.484, -.764, .744), BORDER, .028)
        rounded_panel(self.root, "engineering-card", (-1.48, 1.48, -.76, .74), LAB_CARD, .026)
        DirectFrame(parent=self.root, frameColor=LAB_ACCENT_A, frameSize=(-1.39, -1.38, .616, .674))
        app.text("工程指标", -1.34, .631, .048, parent=self.root, font=app.heading_font)
        app.button("关闭 · Esc", 1.19, .645, .36, self.hide, parent=self.root)
        self.group_menu = app.option(list(ENGINEERING_GROUPS), -.38, .645, .60,
                                     lambda selection: self.show(group=selection), parent=self.root)
        self.basis = app.text("", -1.34, .52, .034, MUTED, parent=self.root)
        self.rows = [app.text("", -1.34+(index//5)*1.38, .36-(index%5)*.155, .035,
                              parent=self.root) for index in range(10)]
        for row in self.rows:
            row.textNode.setWordwrap(35)
        self.notes = app.text("", -1.34, -.49, .032, MUTED, parent=self.root)
        self.notes.textNode.setWordwrap(78)
        self.targets = []
        for index, key in enumerate(("mfdd", "yaw_gain", "beta", "roll", "ltr_front", "ltr_rear",
                                      "utilization_fl", "utilization_fr", "utilization_rl", "utilization_rr")):
            target = DirectFrame(parent=self.root, relief=None, state=DGG.NORMAL,
                                 frameColor=(0, 0, 0, 0), frameSize=(0, 1.24, -.045, .045),
                                 pos=(-1.34+(index//5)*1.38, 0, .36-(index%5)*.155))
            app.bind_parameter(target, "metric."+key)
            self.targets.append(target)
        app.text("各指标的统计窗口与适用状态随报告完整导出。", -1.34, -.68,
                 .033, MUTED, parent=self.root)
        self.root.hide()

    def hide(self):
        self.root.hide()

    def show(self, *, group=None):
        record = self.app.active_record()
        if record is None:
            self.basis.setText("暂无试验记录")
            for row, target in zip(self.rows, self.targets, strict=True):
                row.setText("")
                target.hide()
            self.notes.setText("完成一次试验后即可查看工程分析指标。")
        else:
            summary = record.metadata["summary"]
            analysis = _analyze_record(record)
            baseline = self.app.baseline
            old = _analyze_record(baseline) if baseline is not None else None
            maneuver = summary["options"]["maneuver"]
            if group is None:
                if maneuver in ("ride_bump", "ride_braking"):
                    group = "乘坐 / 接地"
                elif maneuver == "iso_rough_road":
                    group = "ISO 平顺性"
                elif maneuver == "quasi_steady_circle":
                    group = "理论—仿真对账"
                else:
                    group = "操稳 / 制动"
            self.group_menu.set(ENGINEERING_GROUPS.index(group), fCommand=0)
            selector = {
                "操稳 / 制动": lambda data: data["metrics"],
                "乘坐 / 接地": lambda data: data["ride"]["metrics"],
                "ISO 平顺性": lambda data: data["iso_ride"]["metrics"],
                "理论—仿真对账": lambda data: data["theory"]["metrics"],
            }[group]
            items = selector(analysis)
            previous_items = selector(old) if old else None
            from lab_application import control_mode_label

            a_tag = control_mode_label(baseline.metadata["summary"]["options"]) if baseline is not None else None
            b_tag = control_mode_label(summary["options"])
            compare_text = (f"A {a_tag or '基线'} / B {b_tag or '当前'}" if old
                            else f"当前记录{f' · {b_tag}' if b_tag else ''}")
            self.basis.setText(f"{record.metadata['vehicle_name']} · 已完成 {summary['simulation_seconds']:.3f} s · "
                               + compare_text)
            rows_per_col = max(3, (len(items) + 1) // 2)
            for index, text in enumerate(self.rows):
                if index >= len(items):
                    text.setText("")
                    self.targets[index].hide()
                    continue
                col, row_i = divmod(index, rows_per_col)
                pos_x, pos_z = -1.34 + col * 1.38, .36 - row_i * .155
                text.setPos(pos_x, pos_z)
                self.targets[index].setPos(pos_x, 0, pos_z)
                item = items[index]
                unit = "" if item["unit"] == "1" else " " + item["unit"]
                value = f"{item['value']:.4g}{unit}" if item["value"] is not None else "— 当前工况不适用"
                if old is not None:
                    previous = previous_items[index]["value"]
                    a = f"{previous:.4g}" if previous is not None else "—"
                    b = f"{item['value']:.4g}" if item["value"] is not None else "—"
                    value = f"A {a}  ·  B {b}{unit}"
                text.setText(f"{item['label']}\n{value}")
                self.targets[index].show()
                self.app.bind_parameter(self.targets[index], "metric."+item["key"])
            if group == "乘坐 / 接地":
                lines = ["垂向加速度基于世界 Z 轴簧上质心惯性加速度计算（未加权）。",
                         "统计区间覆盖全部仿真步；对比不同配置时应保持路面几何、初速与时长一致。",
                         "零轮荷采样占比表示离散采样步中四轮法向载荷为零的比例。"]
            elif group == "ISO 平顺性":
                lines = [analysis["iso_ride"]["notes"]]
                if old is not None and old["iso_ride"]["discomfort_level"] is not None:
                    lines.append(f"对照 A 主观舒适度：{old['iso_ride']['discomfort_level']}；"
                                 f"本次 B：{analysis['iso_ride']['discomfort_level'] or '—'}。")
                lines.append("车身偏频搜 0.5–4.0 Hz；车轮跳动频峰 6.0–25.0 Hz 需启用独立轮心。")
            elif group == "理论—仿真对账":
                lines = [analysis["theory"]["notes"],
                         "解析基线按整车参数与当前附着计算；K_sim 需运行准稳态定圆扫点工况。"]
            else:
                mfdd, gain = analysis["metrics"][:2]
                lines = ["MFDD："+mfdd["note"], "横摆增益："+gain["note"],
                         "附着利用率使用末子步实际力和同阶段预算；完成步轮荷用于左右转移分析。"]
            self.notes.setText("\n".join(lines))
        self.root.show()
