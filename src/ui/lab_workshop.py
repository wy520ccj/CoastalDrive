"""有限预算改装、固定条件A/B与道路试驾的单个教学内容。"""

import json
from datetime import UTC, datetime

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame

import workshop_cornering as cornering
from lab_records import export_record
from ui import theme
from ui.lab_diagrams import car, course, lengths
from ui.lab_widgets import button_textures, rounded_panel
from ui.workshop_insights import WorkshopInsightsPanel
from vehicle_workspace import WorkspaceVehicle
from workshop import BASE_CONFIG, BUDGET, OPTIONS, build_config, cost, evaluate
from workshop_insights import describe, export_insights


class WorkshopPanel:
    def __init__(self, app):
        self.app = app
        self.phase = None
        self.topic = 0
        self.baseline = self.candidate = self.result = None
        self.root = DirectFrame(parent=app.root, frameColor=theme.PAPER_LIGHT,
                                frameSize=(-1.78, 1.78, -1.5, 1.5), sortOrder=95, state=DGG.NORMAL)
        DirectFrame(parent=self.root, frameColor=theme.PAPER_LIGHT,
                    frameSize=(-1.70, 1.70, -.86, .79))
        self.title = app.text("制动改装", -1.49, .63, .066, parent=self.root, font=app.heading_font)
        self.topic_menu = app.option(["制动改装", "弯道改装"], .27, .66, .59,
                                     self.choose_topic, parent=self.root)
        app.button("我的方案", 1.05, .66, .34, lambda: app.schemes.show(), parent=self.root)
        app.button("关闭", 1.46, .66, .25, self.hide, parent=self.root)
        self.description = app.text("1 选择改装    —    2 对比结果    —    3 试驾", -1.49, .51, .040,
                                    theme.SEA, parent=self.root)
        rounded_panel(self.root, 'workshop-visual', (-1.51, .48, -.17, .42), theme.PAPER)
        self.diagram = self.root.attachNewNode('workshop-diagram')
        self.diagram_note = app.text('', -1.38, .30, .040, theme.MUTED, parent=self.root)
        self.diagram_values = [app.text('', -1.38, z, .040, color, parent=self.root)
                               for z, color in ((.18, theme.SEA), (-.09, theme.ORANGE))]
        rounded_panel(self.root, 'workshop-goal', (.55, 1.51, -.49, .42), theme.PAPER)
        app.text("试验目标", .65, .30, .042, parent=self.root)
        self.goal = app.text("停车距离缩短10%", .65, .18, .058, theme.SEA, parent=self.root)
        self.goal_note = app.text("80 km/h 刹停\n还要保持方向稳定", .65, .055, .040, parent=self.root)
        self.budget = app.text("已用 0 / 3 点", .65, -.16, .046, parent=self.root)
        self.budget_bars = [rounded_panel(self.root, 'budget-token',
            (.65+i*.23, .82+i*.23, -.25, -.225), (.78, .83, .81, 1), .012) for i in range(3)]
        self.details_button = app.button("规则与条件 ›", 1.01, -.40, .70, self.toggle_details, parent=self.root)
        self.first_label = app.text("前轮制动力占比", -1.49, -.27, .042, parent=self.root)
        self.share = app.option(["45% 原装 · 0点", "60% · 1点", "70% · 1点", "80% · 1点"],
                               -1.49, -.38, .82, self.changed, parent=self.root)
        self.second_label = app.text("制动器", -.54, -.27, .042, parent=self.root)
        self.brakes = app.option(["保持原装 · 0点", "制动力+40% · 3点"], -.54, -.38, .93, self.changed, parent=self.root)
        self.third_label = app.text("降低重心", .60, -.27, .042, parent=self.root)
        self.lower_cg = app.option(["原装 · 0点", "降至0.32m · 3点"], .60, -.38, .90, self.changed, parent=self.root)
        self.third_label.hide()
        self.lower_cg.hide()
        self.feedback = app.text("选择改装后，点击开始试验。", -1.49, -.57, .042, parent=self.root)
        self.feedback.textNode.setWordwrap(47)
        self.run_button = app.button("开始试验", 1.12, -.73, .80, self.start, parent=self.root, accent=True)
        self.analyze_button = app.button("详细曲线", -1.13, -.73, .64, self.hide, parent=self.root)
        self.insight_button = app.button("查看结果", -.37, -.73, .64, self.show_insights, parent=self.root)
        self.drive_button = app.button("保存并试驾", 1.12, -.73, .80, self.drive, parent=self.root, accent=True)
        self.drive_button.hide()
        self.drive_button["state"] = DGG.DISABLED
        self.insight_button['state'] = DGG.DISABLED
        self.details = DirectFrame(parent=self.root, frameColor=theme.PAPER_LIGHT,
            frameSize=(-1.78, 1.78, -1, .43), sortOrder=105, state=DGG.NORMAL)
        app.text("完整规则与试验条件", -1.45, .28, .049, parent=self.details)
        self.rules = app.text("", -1.45, .14, .042, parent=self.details)
        self.rules.textNode.setWordwrap(75)
        self.hint = app.text("", -1.45, -.25, .040, theme.SEA, parent=self.details)
        self.hint.textNode.setWordwrap(75)
        app.button("返回改装", 1.17, -.78, .65, self.details.hide, parent=self.details)
        self.details.hide()
        self.insights = WorkshopInsightsPanel(self)
        self.set_topic(0)
        self.root.hide()

    def escape(self):
        if not self.insights.root.isHidden():
            self.insights.escape()
        elif not self.details.isHidden():
            self.details.hide()
        else:
            self.hide()

    def toggle_details(self):
        self.details.show() if self.details.isHidden() else self.details.hide()

    def refresh_diagram(self):
        self.diagram.removeNode()
        self.diagram = self.root.attachNewNode('workshop-diagram')
        for node, z, color in zip(self.diagram_values, (.18, -.09), (theme.SEA, theme.ORANGE), strict=True):
            node.setText('')
            node.setPos(-1.38, z)
            node['fg'] = color
        if self.result is not None:
            if self.topic:
                a, b = (self.result[key]['mean_error_m'] for key in ('baseline_metrics', 'candidate_metrics'))
                self.diagram_note.setText('平均路线偏差')
            else:
                a, b = self.result['baseline_m'], self.result['candidate_m']
                self.diagram_note.setText('停车距离对比（同一起点）')
            lengths(self.diagram, a, b, left=-1.05, right=.23, top=.12, gap=.24, vehicles=not self.topic)
            for node, label, value in zip(self.diagram_values, ('原装', '改装后'), (a, b), strict=True):
                node.setText(f'{label}  {value:.2f} m')
        elif self.topic:
            self.diagram_note.setText('课题示意 · 沿目标弯道行驶，减少偏离')
            course(self.diagram, (-1.32, .22, -.12, .25), 'corner')
        else:
            self.diagram_note.setText('教学示意 · 橙色为前轮制动力')
            car(self.diagram, -.50, .02, 1.12)
            share = (45, 60, 70, 80)[self.share.selectedIndex]
            rounded_panel(self.diagram, 'brake-balance', (-1.20, .20, -.085, -.045), theme.SEA, .016)
            rounded_panel(self.diagram, 'front-balance', (-1.20, -1.20+1.4*share/100, -.085, -.045), theme.ORANGE, .016)
            self.diagram_values[0].setPos(-1.20, -.14)
            self.diagram_values[0]['fg'] = theme.ORANGE
            self.diagram_values[0].setText(f'前轮 {share}%')
            self.diagram_values[1].setPos(-.10, -.14)
            self.diagram_values[1]['fg'] = theme.SEA
            self.diagram_values[1].setText(f'后轮 {100-share}%')
        complete = self.result is not None and self.result['passed']
        self.drive_button.show() if complete else self.drive_button.hide()
        self.run_button.setX(-1.13 if complete else 1.12)
        half_width = .32 if complete else .40
        self.run_button['frameSize'] = (-half_width, half_width, -.045, .045)
        self.run_button['text'] = '重新试验' if self.result is not None else '开始试验'
        self.run_button['frameTexture'] = button_textures(not complete)
        self.run_button['text_fg'] = theme.INK if complete else (1, 1, 1, 1)
        self.analyze_button.setX(-.38 if complete else -1.13)
        self.insight_button.setX(.37 if complete else -.37)

    def selection(self):
        if self.topic == 1:
            return self.share.selectedIndex, self.brakes.selectedIndex == 1, self.lower_cg.selectedIndex == 1
        return self.share.selectedIndex, self.brakes.selectedIndex == 1

    def selected_config(self):
        return cornering.build_config(*self.selection()) if self.topic == 1 else build_config(*self.selection())

    def selected_cost(self):
        return cornering.cost(*self.selection()) if self.topic == 1 else cost(*self.selection())

    def evaluate_records(self):
        return (cornering.evaluate(self.baseline, self.candidate, *self.selection()) if self.topic == 1
                else evaluate(self.baseline, self.candidate, *self.selection()))

    def choose_topic(self, label):
        self.set_topic(self.topic_menu.selectedIndex)

    def set_topic(self, topic):
        if type(topic) is not int or topic not in (0, 1):
            raise ValueError("未知工坊题目")
        if self.phase is not None:
            self.cancel()
        self.topic = topic
        self.topic_menu.set(topic, fCommand=0)
        if topic == 1:
            self.title.setText("弯道改装")
            self.goal.setText("偏离减少50%")
            self.goal_note.setText("60 km/h 沿弯道行驶\n平均偏离不超过1.6米")
            self.rules.setText("任务  末2秒平均循迹误差≤1.6m且减少≥50% · 预算3点\n"
                "虚构教学RWD · 目标60km/h / 半径40m / 10秒 / μ=1.1 / ESC关\n"
                "末窗车速60±1.2km/h · 全程峰值侧偏≤4° / 侧倾≤3°\n"
                "金：改善≥65%且≤2点；银：改善≥55%；铜：达到全部目标。")
            self.first_label.setText("前轮侧向刚度")
            self.second_label.setText("车身支撑分配")
            first_items = ["原装35k · 0点", "45k · 1点", "50k · 2点", "70k · 2点"]
            second_items = ["偏前支撑 · 0点", "偏后支撑 · 1点"]
            self.second_label.setX(-.54)
            self.third_label.show()
            self.third_label.setPos(.60, -.54)
            self.lower_cg.setPos(.60, 0, -.65)
            self.lower_cg.show()
            self.budget.setPos(.65, -.16)
            self.hint.setText("轮胎数值为前轴侧偏刚度（N/rad）。前/后防倾为28/2或8/22 kN/m，总刚度不变。\n"
                              "观察循迹、实际转角与侧偏；侧倾更小也要看是否解决本题问题。")
        else:
            self.title.setText("制动改装")
            self.goal.setText("停车距离缩短10%")
            self.goal_note.setText("80 km/h 刹停\n还要保持方向稳定")
            self.rules.setText("任务  80–0 停车距离缩短 ≥10% · 峰值横摆 ≤0.05 rad/s · 预算3点\n"
                "虚构教学车：参考后驱 / 初始前制动45% / ABS开 / ESC关 / 平路 μ=1.1\n"
                "同条件比较原装与改装，只改变本页两项。\n"
                "金：改善≥12%且只用1点；银：改善≥12%；铜：达到全部目标。")
            self.first_label.setText("前轮制动力占比")
            self.second_label.setText("制动器")
            first_items = ["45% 原装 · 0点", "60% · 1点", "70% · 1点", "80% · 1点"]
            second_items = ["保持原装 · 0点", "制动力+40% · 3点"]
            self.second_label.setX(-.54)
            self.third_label.hide()
            self.lower_cg.hide()
            self.budget.setPos(.65, -.16)
            self.hint.setText("提示：制动时前后轮荷不同，分配不合适可能让某一轴先用满附着。\n"
                              "查看四轮滑移与ABS介入，比较不同方案的轮胎利用情况。")
        # DirectOptionMenu重设items会丢失已消费的item字体/尺寸选项；选题时重建这两个控件。
        for menu in (self.share, self.brakes):
            menu.hidePopupMenu()
            menu.destroy()
        self.share = self.app.option(first_items, -1.49, -.38, .82,
                                     self.changed, parent=self.root)
        self.brakes = self.app.option(second_items, -.54, -.38, .93,
                                      self.changed, parent=self.root)
        self.lower_cg.set(0, fCommand=0)
        self.changed("")
        self.feedback.setText("选择改装后，点击开始试验。")

    def refresh_budget(self):
        points = self.selected_cost()
        self.budget.setText(f"已用 {points} / {BUDGET} 点" + (" · 超支" if points > BUDGET else ""))
        for index, bar in enumerate(self.budget_bars):
            bar.setColor(*(theme.FAILURE if points > BUDGET else theme.SEA) if index < points else (.78, .83, .81, 1))

    def changed(self, label):
        self.insights.hide()
        self.insights.data = None
        self.insight_button['state'] = DGG.DISABLED
        self.result = None
        self.drive_button["state"] = DGG.DISABLED
        self.refresh_budget()
        self.refresh_diagram()
        self.feedback.setText("改装已更改，需要重新试验。旧曲线仍可查看。")

    def show(self):
        app = self.app
        app.blur_entries()
        app.design_loop.hide()
        for panel in (app.advanced_panel, app.manual_panel, app.details_panel, app.record_menu,
                      app.parameter_help.root, app.engineering_panel.root):
            panel.hide()
        if app.run_state is not None and self.phase is None:
            app.run_state.paused = True
        self.root.show()

    def hide(self):
        self.details.hide()
        self.insights.hide()
        if self.phase is not None:
            self.cancel()
        self.share.hidePopupMenu()
        self.brakes.hidePopupMenu()
        self.lower_cg.hidePopupMenu()
        self.topic_menu.hidePopupMenu()
        self.root.hide()

    def cancel(self):
        self.insights.hide()
        self.insight_button['state'] = DGG.DISABLED
        if self.app.run_state is not None:
            self.app.run_state.paused = True
        self.phase = None
        self.result = None
        self.set_running(False)
        self.feedback.setText("已停止。原曲线保留。")
        self.refresh_diagram()

    def set_running(self, running):
        self.insights.hide()
        self.insight_button['state'] = DGG.DISABLED
        for widget in (self.share, self.brakes, self.lower_cg, self.topic_menu, self.run_button):
            widget["state"] = DGG.DISABLED if running else DGG.NORMAL
        self.drive_button["state"] = DGG.DISABLED

    def begin_trial(self, config):
        app = self.app
        options = cornering.OPTIONS if self.topic == 1 else OPTIONS
        app.set_options(options)
        app.engineered_config, app.engineered_vehicle_id = config, options.vehicle_id
        app.parameter_metadata = {"basis": "海岸操稳工坊虚构教学车；同驾驶员定圆循迹" if self.topic == 1 else "海岸制动工坊虚构教学车；非实车标定"}
        app.refresh_configuration_note()
        app.start_experiment()
        if app.run_state is None:
            raise RuntimeError("工坊试验初始化失败")

    def start(self):
        self.app.design_loop.hide()
        self.result = self.baseline = self.candidate = None
        self.refresh_diagram()
        self.set_running(True)
        self.phase = "A"
        try:
            self.begin_trial(cornering.BASE_CONFIG if self.topic == 1 else BASE_CONFIG)
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            self.cancel()
            self.app.show_error("挑战未开始", error)

    def update(self):
        if self.phase is None:
            return
        app, run = self.app, self.app.run_state
        limit = cornering.OPTIONS.duration if self.topic == 1 else OPTIONS.duration
        self.feedback.setText(f"正在测试{'原装车' if self.phase == 'A' else '改装车'}  ·  {run.elapsed:.1f} / {limit:g} 秒  ·  关闭可停止")
        if not run.done:
            return
        try:
            if run.reason != ("time_limit" if self.topic == 1 else "stopped"):
                raise ValueError("试验没有正常完成，本次不评价")
            if self.phase == "A":
                self.baseline = app.active_record()
                app.baseline = self.baseline
                self.phase = "B"
                self.begin_trial(self.selected_config())
                return
            self.candidate = app.active_record()
            self.result = self.evaluate_records()
        except (OSError, ArithmeticError, ValueError, RuntimeError) as error:
            self.cancel()
            app.show_error("挑战未完成，记录保留", error)
            return
        self.phase = None
        self.set_running(False)
        self.present_result()

    def present_result(self):
        result = self.result
        self.insight_button['state'] = DGG.NORMAL
        if self.topic:
            reasons = result['unmet']
        else:
            reasons = (["预算超出"] if result['cost'] > BUDGET else [])
            reasons += ["停车改善不足10%"] if result['improvement_pct'] < 10. else []
            reasons += ["方向偏转过大"] if result['peak_yaw_radps'] > .05 else []
        outcome = f"通过 · {result['medal']}牌" if result['passed'] else "未达标 · "+" / ".join(reasons)
        self.feedback.setText(f"{outcome}  |  {'偏离' if self.topic else '停车距离'}减少 {result['improvement_pct']:.2f}%")
        self.drive_button['state'] = DGG.NORMAL if result['passed'] else DGG.DISABLED
        self.refresh_diagram()

    def show_insights(self):
        if self.result is None or self.phase is not None:
            return
        try:
            data = describe(self.baseline, self.candidate, self.topic, self.selection())
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error('试验解读未生成，原始记录保留', error)
            return
        self.insights.show(data)

    def prepare_next_trial(self):
        data = self.insights.data
        if data is None or data['next']['selection'] is None or self.result is None:
            return
        selection = data['next']['selection']
        self.share.set(selection[0], fCommand=0)
        self.brakes.set(int(selection[1]), fCommand=0)
        if self.topic == 1:
            self.lower_cg.set(int(selection[2]), fCommand=0)
        self.changed('')
        self.feedback.setText('参数已调整。点击开始试验重新比较。\n原记录和曲线仍保留。')

    def export_interpretation(self):
        if self.result is None or self.phase is not None:
            return
        try:
            data = describe(self.baseline, self.candidate, self.topic, self.selection())
            folder = self.app.output/(datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f')+'-workshop-insights')
            report = export_record(self.candidate, folder, baseline=self.baseline)
            export_insights(data, folder)
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error('解读未导出，原试验与成绩保留', error)
            return
        self.app.last_report = report
        self.insights.basis.setText('已导出完整A/B与insights.json / insights.txt：'+folder.name)
        self.insights.next.setText('已导出。保存位置见“完整数据”。')

    def drive(self):
        if self.result is None or not self.result["passed"]:
            return
        try:
            # 应用完成试验时冻结的配置，不能把后续未运行编辑混入成绩。
            result = self.evaluate_records()
            folder = self.app.output/(datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")+"-workshop")
            report = export_record(self.candidate, folder, baseline=self.baseline)
            export_insights(describe(self.baseline, self.candidate, self.topic, self.selection()), folder)
            (folder/"challenge.json").write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                                           allow_nan=False), encoding="utf-8")
            vehicle = WorkspaceVehicle(OPTIONS.vehicle_id, self.selected_config(),
                                       self.candidate.metadata["parameter_metadata"], str(report), result)
            vehicle.save()
        except (OSError, ValueError, KeyError, TypeError) as error:
            self.app.show_error("挑战车辆未保存，结果保留", error)
            return
        self.app.workspace_vehicle = vehicle
        self.app.next_drive = True
        self.app.back_to_game()

    def capture(self):
        return {"topic": self.topic, "selection": self.selection(), "baseline": self.baseline, "candidate": self.candidate,
                "result": self.result, "text": self.feedback.getText(), 'insight_open': not self.insights.root.isHidden()}

    def restore(self, state):
        self.set_topic(state.get("topic", 0))
        self.share.set(state["selection"][0], fCommand=0)
        self.brakes.set(int(state["selection"][1]), fCommand=0)
        if self.topic == 1:
            self.lower_cg.set(int(state["selection"][2]), fCommand=0)
        self.baseline, self.candidate, self.result = state["baseline"], state["candidate"], state["result"]
        self.refresh_budget()
        self.refresh_diagram()
        self.feedback.setText(state["text"])
        self.drive_button["state"] = DGG.NORMAL if self.result is not None and self.result["passed"] else DGG.DISABLED
        self.insight_button['state'] = DGG.NORMAL if self.result is not None else DGG.DISABLED
        if state.get('insight_open', False):
            self.show_insights()

    def restore_saved(self, vehicle):
        if vehicle.workshop_result is None or self.app.record is None or self.app.baseline is None:
            return
        receipt = vehicle.workshop_result
        topic = int(receipt["challenge_id"] == cornering.CHALLENGE_ID)
        self.set_topic(topic)
        selection = ((receipt["tire_index"], receipt["balanced_bar"], receipt["lower_cg"]) if topic
                     else (receipt["share_index"], receipt["large_brakes"]))
        try:
            result = (cornering.evaluate(self.app.baseline, self.app.record, *selection) if topic
                      else evaluate(self.app.baseline, self.app.record, *selection))
        except (ValueError, KeyError, TypeError) as error:
            self.app.show_error("工坊原始记录与成绩不匹配，请重新运行挑战", error)
            return
        self.restore({"topic": topic, "selection": selection,
                      "baseline": self.app.baseline, "candidate": self.app.record,
                      "result": result, "text": ""})
        self.present_result()
