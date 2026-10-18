"""有限预算改装、固定条件A/B与道路试驾的单个教学内容。"""

import json
from datetime import UTC, datetime

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame

import workshop_cornering as cornering
from lab_records import export_record
from ui import theme
from vehicle_workspace import WorkspaceVehicle
from workshop import BASE_CONFIG, BUDGET, OPTIONS, build_config, cost, evaluate


class WorkshopPanel:
    def __init__(self, app):
        self.app = app
        self.phase = None
        self.topic = 0
        self.baseline = self.candidate = self.result = None
        self.root = DirectFrame(parent=app.root, frameColor=(.04, .10, .14, .70),
                                frameSize=(-1.78, 1.78, -1, 1), sortOrder=95, state=DGG.NORMAL)
        DirectFrame(parent=self.root, frameColor=theme.PAPER_LIGHT,
                    frameSize=(-1.70, 1.70, -.86, .79))
        app.text("海岸工坊", -1.52, .63, .062, parent=self.root, font=app.heading_font)
        self.topic_menu = app.option(["01 制动配方", "02 弯道循迹"], -.75, .64, 1.44,
                                     self.choose_topic, parent=self.root)
        app.button("关闭", 1.42, .66, .28, self.hide, parent=self.root)
        self.description = app.text("把车停得更短，也把预算用得更聪明。", -1.52, .51, .043, theme.SEA, parent=self.root)
        self.rules = app.text("任务  80–0 停车距离缩短 ≥10% · 峰值横摆 ≤0.05 rad/s · 预算3点\n"
                 "虚构教学车：参考后驱 / 初始前制动45% / ABS开 / ESC关 / 平路 μ=1.1\n"
                 "同条件真实计算 A 与 B；只能改变下方两项，原车与专家实验仍可自由使用。",
                 -1.52, .39, .037, parent=self.root)
        self.first_label = app.text("前制动份额 / 调整消耗1点", -1.52, .10, .038, parent=self.root)
        self.share = app.option(["45% 原配", "60%", "70%", "80%"], -1.52, .01, .60,
                                self.changed, parent=self.root)
        self.second_label = app.text("制动器 / 加大消耗3点", -.62, .10, .038, parent=self.root)
        self.brakes = app.option(["原配", "加大扭矩 +40%"], -.62, .01, .66, self.changed, parent=self.root)
        self.third_label = app.text("重心 / 降低消耗3点", .61, .10, .038, parent=self.root)
        self.lower_cg = app.option(["原配0.42m", "降低至0.32m"], .61, .01, .90, self.changed, parent=self.root)
        self.third_label.hide()
        self.lower_cg.hide()
        self.budget = app.text("预算 0 / 3", .39, .00, .044, theme.SEA, parent=self.root)
        self.feedback = app.text("先保留原方案试一次，再选择改装。\n金：改善≥12%且只用1点；银：改善≥12%；铜：达到任务目标。",
                                 -1.52, -.17, .038, parent=self.root)
        self.feedback.textNode.setWordwrap(77)
        self.hint = app.text("提示：制动时前后轮荷不同，分配不合适可能让某一轴先用满附着。\n"
                 "查看四轮滑移与ABS介入，比较不同方案的轮胎利用情况。",
                 -1.52, -.49, .035, theme.SEA, parent=self.root)
        self.run_button = app.button("运行 A/B", -1.12, -.71, .70, self.start, parent=self.root, accent=True)
        self.analyze_button = app.button("查看曲线", -.22, -.71, .65, self.hide, parent=self.root)
        self.drive_button = app.button("保存并道路验证", .86, -.71, 1.00, self.drive, parent=self.root)
        self.drive_button["state"] = DGG.DISABLED
        self.root.hide()

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
            self.description.setText("让教学车少向弯外推，也留意侧偏和改装代价。")
            self.rules.setText("任务  末2秒平均循迹误差≤1.6m且减少≥50% · 预算3点\n"
                "虚构教学RWD · 目标60km/h / 半径40m / 10秒 / μ=1.1 / ESC关\n"
                "末窗车速60±1.2km/h · 全程峰值侧偏≤4° / 侧倾≤3°")
            self.first_label.setText("前胎侧偏配方 / N/rad")
            self.second_label.setText("前/后防倾分配 / 1点")
            first_items = ["35k 原配 / 0点", "45k / 1点", "50k / 2点", "70k / 2点"]
            second_items = ["28/2 kN/m 原配", "8/22 kN/m"]
            self.second_label.setX(-.45)
            self.third_label.show()
            self.lower_cg.show()
            self.budget.setPos(1.03, .49)
            self.hint.setText("轮胎选项只调前轴侧偏刚度；路面μ与峰值参数保持，防倾总刚度保持。\n"
                              "观察循迹、实际转角与侧偏；侧倾更小也要看是否解决本题问题。")
        else:
            self.description.setText("把车停得更短，也把预算用得更聪明。")
            self.rules.setText("任务  80–0 停车距离缩短 ≥10% · 峰值横摆 ≤0.05 rad/s · 预算3点\n"
                "虚构教学车：参考后驱 / 初始前制动45% / ABS开 / ESC关 / 平路 μ=1.1\n"
                "同条件真实计算 A 与 B；只能改变下方两项，原车与专家实验仍可自由使用。")
            self.first_label.setText("前制动份额 / 调整消耗1点")
            self.second_label.setText("制动器 / 加大消耗3点")
            first_items = ["45% 原配", "60%", "70%", "80%"]
            second_items = ["原配", "加大扭矩 +40%"]
            self.second_label.setX(-.62)
            self.third_label.hide()
            self.lower_cg.hide()
            self.budget.setPos(.39, .00)
            self.hint.setText("提示：制动时前后轮荷不同，分配不合适可能让某一轴先用满附着。\n"
                              "查看四轮滑移与ABS介入，比较不同方案的轮胎利用情况。")
        # DirectOptionMenu重设items会丢失已消费的item字体/尺寸选项；选题时重建这两个控件。
        for menu in (self.share, self.brakes):
            menu.hidePopupMenu()
            menu.destroy()
        self.share = self.app.option(first_items, -1.52, .01, .90 if topic else .60,
                                     self.changed, parent=self.root)
        self.brakes = self.app.option(second_items, -.45 if topic else -.62, .01, .90 if topic else .66,
                                      self.changed, parent=self.root)
        self.lower_cg.set(0, fCommand=0)
        self.changed("")
        self.feedback.setText("先试原方案，再选择改装。金：改善≥65%且≤2点；银：改善≥55%；铜：达到目标。"
                              if topic == 1 else "先保留原方案试一次，再选择改装。\n金：改善≥12%且只用1点；银：改善≥12%；铜：达到任务目标。")

    def changed(self, label):
        self.result = None
        self.drive_button["state"] = DGG.DISABLED
        points = self.selected_cost()
        self.budget.setText(f"预算 {points} / {BUDGET}" + (" · 超出预算" if points > BUDGET else ""))
        self.feedback.setText("选项已改变，重新运行 A/B 后评价；旧曲线仍可查看。")

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
        if self.phase is not None:
            self.cancel()
        self.share.hidePopupMenu()
        self.brakes.hidePopupMenu()
        self.lower_cg.hidePopupMenu()
        self.topic_menu.hidePopupMenu()
        self.root.hide()

    def cancel(self):
        if self.app.run_state is not None:
            self.app.run_state.paused = True
        self.phase = None
        self.result = None
        self.set_running(False)
        self.feedback.setText("挑战已停止；已有曲线保留，重新运行 A/B 才能获奖。")

    def set_running(self, running):
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
        self.feedback.setText(f"正在计算 {self.phase} · 仿真 {run.elapsed:.2f} s / 最长{limit:g} s\n"
                              "离线逐拍推进；计算时间与仿真时间分别显示。关闭可停止。")
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
        if self.topic == 1:
            measured = result["candidate_metrics"]
            outcome = f"通过 · {result['medal']}牌" if result["passed"] else "未达标 · "+" / ".join(result["unmet"])
            self.feedback.setText(f"{outcome}\n"
                f"末窗误差 A {result['baseline_metrics']['mean_error_m']:.3f} → B {measured['mean_error_m']:.3f} m"
                f" · 减少{result['improvement_pct']:.2f}% · 预算{result['cost']}/3\n"
                f"速度偏差{measured['max_speed_error_kph']:.2f}km/h · 峰值侧偏{measured['peak_beta_deg']:.2f}°"
                f" · 侧倾{measured['peak_roll_deg']:.2f}°\n"
                "查看路径跟踪与转向响应，比较误差减少和侧偏代价。")
            self.drive_button["state"] = DGG.NORMAL if result["passed"] else DGG.DISABLED
            return
        unmet = []
        if result["cost"] > BUDGET:
            unmet.append("预算超出")
        if result["improvement_pct"] < 10.:
            unmet.append("距离改善不足")
        if result["peak_yaw_radps"] > .05:
            unmet.append("横摆超限")
        outcome = f"通过 · {result['medal']}牌" if result["passed"] else "未达标 · "+" / ".join(unmet)
        self.feedback.setText(f"{outcome}    A {result['baseline_m']:.2f} m → B {result['candidate_m']:.2f} m\n"
                              f"停车改善 {result['improvement_pct']:+.2f}% / 目标≥10% · 预算 {result['cost']}/3\n"
                              f"峰值横摆 {result['peak_yaw_radps']:.4f} rad/s / 上限0.05\n"
                              "查看曲线比较速度、减速度和四轮滑移；改变选项可以再试。")
        self.drive_button["state"] = DGG.NORMAL if result["passed"] else DGG.DISABLED

    def drive(self):
        if self.result is None or not self.result["passed"]:
            return
        try:
            # 应用完成试验时冻结的配置，不能把后续未运行编辑混入成绩。
            result = self.evaluate_records()
            folder = self.app.output/(datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")+"-workshop")
            report = export_record(self.candidate, folder, baseline=self.baseline)
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
                "result": self.result, "text": self.feedback.getText()}

    def restore(self, state):
        self.set_topic(state.get("topic", 0))
        self.share.set(state["selection"][0], fCommand=0)
        self.brakes.set(int(state["selection"][1]), fCommand=0)
        if self.topic == 1:
            self.lower_cg.set(int(state["selection"][2]), fCommand=0)
        self.baseline, self.candidate, self.result = state["baseline"], state["candidate"], state["result"]
        self.budget.setText(f"预算 {self.selected_cost()} / 3")
        self.feedback.setText(state["text"])
        self.drive_button["state"] = DGG.NORMAL if self.result is not None and self.result["passed"] else DGG.DISABLED

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
