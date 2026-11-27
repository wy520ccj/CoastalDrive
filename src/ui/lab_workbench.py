"""明净浅瓷汽车工程试验台：通透顶栏、纯白精密卡片、高对比钢蓝/暖橙 A/B 对照与互斥弹窗。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectEntry, DirectFrame, DirectSlider
from panda3d.core import TextNode, TransparencyAttrib

from lab_experiment import MANEUVERS
from ui import theme
from ui.lab_feedback import LabFeedback
from ui.lab_plot import LabPlot
from ui.lab_widgets import (
    BORDER,
    LAB_ACCENT_A,
    LAB_ACCENT_B,
    LAB_BG,
    LAB_CARD,
    LAB_FIELD,
    LAB_HEADER,
    LAB_LINE_A,
    LAB_LINE_B,
    LAB_TEXT,
    LAB_TINT_A,
    LAB_TINT_B,
    LAB_TRACK,
    MUTED,
    rounded_panel,
)
from vehicle_designs import DESIGN_VEHICLES

VIEWPORT = (-.90, .90, .06, .66)
_VEHICLE_LABELS = {
    "game-tuned": "游戏调校",
    "reference-rwd": "参考后驱 RWD",
    "reference-fwd": "参考前驱 FWD",
    "reference-awd": "参考四驱 AWD",
    "gr86-2022-premium-6mt": "GR86 Premium 6MT",
}


def _card(parent, name, box, radius=.022, fill=LAB_CARD):
    left, right, bottom, top = box
    rounded_panel(parent, name+"-edge", (left-.004, right+.004, bottom-.004, top+.004), BORDER, radius+.002)
    return rounded_panel(parent, name, box, fill, radius)


def _modal_backdrop(parent, sort_order):
    frame = DirectFrame(parent=parent, frameColor=(.06, .08, .11, .42),
                        frameSize=(-1.78, 1.78, -1.0, 1.0), sortOrder=sort_order, state=DGG.NORMAL)
    frame.setTransparency(TransparencyAttrib.MAlpha)
    return frame


def build_workbench(app):
    root = app.root

    # 明净浅瓷灰背景，围绕真实 3D 车辆视窗镂空，绝不遮盖渲染区。
    for box in ((-1.78, 1.78, .66, 1.5), (-1.78, 1.78, -1.5, .06),
                (-1.78, -.90, .06, .66), (.90, 1.78, .06, .66)):
        DirectFrame(parent=root, frameColor=LAB_BG, frameSize=box, sortOrder=-100)

    # 浅瓷通栏顶栏 + 海岸三色精密细线（上下视觉一体，告别黑顶白身割裂）。
    DirectFrame(parent=root, frameColor=LAB_HEADER, frameSize=(-1.78, 1.78, .828, 1.02), sortOrder=-50)
    DirectFrame(parent=root, frameColor=LAB_ACCENT_B, frameSize=(-1.78, -.58, .824, .831), sortOrder=-48)
    DirectFrame(parent=root, frameColor=theme.AMBER, frameSize=(-.58, .60, .824, .831), sortOrder=-48)
    DirectFrame(parent=root, frameColor=LAB_ACCENT_A, frameSize=(.60, 1.78, .824, .831), sortOrder=-48)
    app.text("COASTAL DRIVE", -1.70, .900, .052, LAB_TEXT, font=app.display_font)
    DirectFrame(parent=root, frameColor=LAB_ACCENT_B, frameSize=(-1.125, -1.116, .880, .948))
    app.text("专家试验台", -1.08, .900, .048, LAB_TEXT, font=app.heading_font)
    app.text("配置 · 回看 · A/B 遥测", -.68, .905, .030, MUTED)

    for text, x, w, action in (
            ("保存与试驾", .18, .38, lambda: app.design_loop.show()),
            ("参数说明 F1", .62, .39, app.show_parameter_help),
            ("记录 ▼", 1.04, .34, app.toggle_record_menu),
            ("返回驾驶", 1.48, .42, app.back_to_game)):
        app.button(text, x, .914, w, action)

    # 三大主卡片区：左通高配置卡、中视窗播放卡、右结果对比卡。
    _card(root, "trial-card", (-1.72, -.98, -.95, .79))
    _card(root, "result-card", (.98, 1.72, -.18, .79))
    _card(root, "viewport-top", (-.94, .94, .66, .79))
    _card(root, "viewport-bottom", (-.94, .94, -.18, .06))
    DirectFrame(parent=root, frameColor=LAB_CARD, frameSize=(-.94, -.90, .05, .67))
    DirectFrame(parent=root, frameColor=LAB_CARD, frameSize=(.90, .94, .05, .67))
    DirectFrame(parent=root, frameColor=BORDER, frameSize=(-.944, -.94, .05, .67))
    DirectFrame(parent=root, frameColor=BORDER, frameSize=(.94, .944, .05, .67))

    for x, label in ((-1.62, "试验配置"), (-.84, "车辆视窗"), (1.08, "试验结果")):
        DirectFrame(parent=root, frameColor=LAB_ACCENT_B, frameSize=(x-.042, x-.032, .698, .754))
        app.text(label, x, .713, .042, LAB_TEXT, font=app.heading_font)

    # ── 左栏上段：车辆、工况、初速/附着、直达电子控制（全列左右严格对齐 [-1.64, -1.04]）──
    app.text("车辆模型", -1.64, .646, .029, MUTED)
    vehicle_items = [_VEHICLE_LABELS.get(design.id, design.name.split(" · ")[0])
                     for design in DESIGN_VEHICLES]
    app.vehicle_menu = app.option(vehicle_items, -1.64, .588, .60,
                                  command=app.choose_vehicle, parameter="vehicle")
    app.vehicle_menu.set(1, fCommand=0)
    app.configuration_note = app.text("车型默认 · 无独立轮心", -1.64, .518, .028, MUTED)

    app.text("试验工况", -1.64, .460, .029, MUTED)
    app.maneuver_menu = app.option(list(MANEUVERS.values()), -1.64, .402, .60,
                                   app.apply_preset, parameter="maneuver")
    app.field("speed", "初速 km/h", 100, .306, x=-1.64, width=.26)
    app.field("mu", "路面附着 μ", 1.1, .218, x=-1.64, width=.26)

    # 将 ABS 与 ESC/ABS-DYC 控制策略并列直达主面板，无需再钻二级弹窗寻找。
    app.abs_menu = app.option(["ABS 开启", "ABS 关闭"], -1.64, .122, .60, parameter="abs")
    app.esc_menu = app.option(["ESC 关闭", "ESC 开启", "协调控制（ABS–DYC）"], -1.64, .034, .60,
                              command=app.select_stability_control, parameter="esc")

    app.advanced_button = app.button("高级参数 ›", -1.50, -.066, .28, app.toggle_advanced)
    app.reset_button = app.button("重置参数", -1.18, -.066, .28, app.reset_parameters)
    app.start_button = app.button("开始试验", -1.34, -.170, .60, app.start_experiment, accent=True)
    app.button("设为对照 A", -1.34, -.270, .60, app.pin_baseline)

    # ── 左栏下段：曲线切换与工坊入口 ──
    DirectFrame(parent=root, frameColor=BORDER, frameSize=(-1.64, -1.04, -.348, -.344))
    app.text("曲线组", -1.64, -.402, .029, MUTED)
    app.plot_menu = app.option(["制动响应", "转向响应", "四轮法向载荷", "四轮滑移率", "轮胎力 / 轮速", "路径跟踪", "执行器响应",
                               "轮胎侧偏角", "附着利用率", "车身侧偏 / 侧倾", "左右载荷转移", "轮胎回正力矩",
                               "质心运动", "车身 / 轮心振动", "悬架行程 / 速度", "轮胎径向压缩",
                               "K&C 外倾 / 转角", "状态估计对比"],
                              -1.64, -.466, .60, app.set_plot_group, parameter="plot")
    app.button("新手工坊", -1.34, -.596, .60, lambda: app.workshop.show())
    app.button("方案库", -1.34, -.696, .60, lambda: app.schemes.show())
    app.text("F1 参数说明 · Space 暂停/继续", -1.64, -.852, .028, MUTED)

    # ── 中栏：3D 视窗工具与播放控制条 ──
    app.button("切换视角", .74, .726, .28, app.cycle_camera)
    app.manual_button = app.button("执行器输入", .38, .726, .32, app.show_manual)
    app.manual_button.hide()

    app.model_note = app.text("设计参考车 RWD", -.88, .012, .031, MUTED)
    app.model_note.textNode.setWordwrap(38)
    app.cursor_label = app.text("t = 0.000 s", .88, .012, .033, LAB_TEXT, align=TextNode.ARight)

    app.button("暂停", -.75, -.066, .26, app.toggle_pause)
    app.button("单步", -.46, -.066, .26, app.single_step)
    app.button("回放", -.17, -.066, .26, app.toggle_playback)
    app.timeline = DirectSlider(parent=root, range=(0, 1), value=0, pageSize=1, scrollSize=0,
        frameSize=(-.38, .38, -.032, .032), frameVisibleScale=(1, .14), frameColor=LAB_TRACK,
        thumb_frameColor=LAB_ACCENT_B, thumb_frameSize=(-.014, .014, -.024, .024),
        thumb_relief=DGG.FLAT, borderWidth=(0, 0), relief=DGG.FLAT,
        pos=(.47, 0, -.066), command=app.seek)
    for control in (app.timeline, app.timeline.thumb):
        control.bind(DGG.B1PRESS, app.set_pointer, [True])
        control.bind(DGG.B1RELEASE, app.set_pointer, [False])
    app.text("时间轴 · 点击或拖动分析任意时刻", -.88, -.144, .028, MUTED)
    app.text("A 海岸蓝   ·   B 赛道橙", .88, -.144, .028, MUTED, align=TextNode.ARight)

    # ── 右栏：核心指标 + 高对比浅底双色 A/B 对比卡 + 分析操作 ──
    app.status = app.text("等待试验", 1.66, .717, .030, LAB_ACCENT_A, align=TextNode.ARight)
    app.metric_label = app.text("停车距离", 1.04, .634, .030, MUTED)
    app.metric = app.text("—", 1.04, .514, .094, LAB_ACCENT_B, font=app.heading_font)

    # 高对比浅底双色 A/B 对比胶囊子卡（深海蓝 A / 暖赛道橙 B，浅底清晰锐利）。
    rounded_panel(root, "slot-a-edge", (1.036, 1.344, .286, .466), LAB_LINE_A, .018)
    rounded_panel(root, "slot-a", (1.04, 1.34, .290, .462), LAB_TINT_A, .016)
    rounded_panel(root, "slot-b-edge", (1.356, 1.664, .286, .466), LAB_LINE_B, .018)
    rounded_panel(root, "slot-b", (1.36, 1.66, .290, .462), LAB_TINT_B, .016)
    app.baseline_label = app.text("对照 A", 1.056, .412, .027, LAB_ACCENT_A)
    app.candidate_label = app.text("本次 B", 1.376, .412, .027, LAB_ACCENT_B)
    app.baseline_value = app.text("—", 1.056, .326, .040, LAB_ACCENT_A, font=app.heading_font)
    app.candidate_value = app.text("—", 1.376, .326, .040, LAB_ACCENT_B, font=app.heading_font)

    app.result = app.text("设为对照 A 后显示差值", 1.04, .226, .030, MUTED)
    app.timing = app.text("仿真 — · 计算 —", 1.04, .156, .028, MUTED)

    app.button("详细信号", 1.19, .044, .29, app.toggle_details)
    app.button("工程指标", 1.51, .044, .29, app.show_engineering)
    app.button("清除 A", 1.19, -.066, .29, app.clear_baseline)
    app.button("导出报告", 1.51, -.066, .29, app.export)

    # ── 底部全宽双曲线分析卡 ──
    app.plots = [LabPlot(root, app.font, (-.94, .36, -.88, -.22), "speed"),
                 LabPlot(root, app.font, (.40, 1.72, -.88, -.22), "ax")]
    for plot in app.plots:
        plot.update(())

    # 底部通栏状态条。
    app.notice = LabFeedback(app)
    app.notice.footer.setPos(-.94, -.948)
    app.notice.footer.setScale(.029)
    app.notice.footer.textNode.setWordwrap(82)

    from ui.lab_design_loop import DesignLoopPanel
    from ui.lab_engineering import EngineeringPanel
    from ui.lab_road_retest import RoadRetestPanel
    from ui.lab_schemes import SchemesPanel
    from ui.lab_workshop import WorkshopPanel
    from ui.parameter_help import ParameterHelp

    app.design_loop = DesignLoopPanel(app)
    app.workshop = WorkshopPanel(app)
    app.schemes = SchemesPanel(app)
    app.road_retest = RoadRetestPanel(app)

    # ── 互斥浅瓷浮层弹窗 ──
    app.record_menu = DirectFrame(parent=root, frameColor=(.06, .08, .11, .28),
                                  frameSize=(-1.78, 1.78, -1.0, 1.0), sortOrder=95, state=DGG.NORMAL)
    app.record_menu.setTransparency(TransparencyAttrib.MAlpha)
    app.record_menu.bind(DGG.B1PRESS, lambda _event: app.record_menu.hide())
    DirectFrame(parent=app.record_menu, frameColor=(0, 0, 0, 0),
                frameSize=(.90, 1.68, .06, .82), state=DGG.NORMAL)
    _card(app.record_menu, "record-card", (.92, 1.66, .08, .80), .022)
    DirectFrame(parent=app.record_menu, frameColor=LAB_ACCENT_B, frameSize=(.97, .98, .718, .764))
    app.text("记录与工程文件", 1.00, .730, .034, LAB_TEXT, parent=app.record_menu, font=app.heading_font)
    app.button("收起", 1.51, .741, .18, app.record_menu.hide, parent=app.record_menu)
    for z, label, action in ((.642, "载入实验记录", app.open_record),
                             (.540, "复算当前记录", app.recalculate_record),
                             (.438, "打开导出报告", app.open_report),
                             (.336, "导入工程模型", app.open_engineering)):
        app.button(label, 1.29, z, .60, action, parent=app.record_menu)
    app.driving_car_button = app.button("载入驾驶车硬件", 1.29, .234, .60,
                                        app.stage_driving_vehicle, parent=app.record_menu)
    app.driving_car_button["state"] = DGG.NORMAL if app.workspace_vehicle is not None else DGG.DISABLED
    app.road_retest_button = app.button("道路 A/B 复测", 1.29, .132, .60,
                                        app.road_retest.show, parent=app.record_menu)
    app.road_retest_button["state"] = DGG.DISABLED
    app.record_menu.hide()

    app.advanced_panel = _modal_backdrop(root, 90)
    _card(app.advanced_panel, "advanced-card", (-1.12, 1.12, -.64, .68), .026)
    DirectFrame(parent=app.advanced_panel, frameColor=LAB_ACCENT_B, frameSize=(-1.03, -1.02, .548, .604))
    app.text("高级试验参数", -.99, .562, .045, LAB_TEXT, parent=app.advanced_panel, font=app.heading_font)
    app.advanced_reset_button = app.button("重置当前工况", .45, .576, .38, app.reset_parameters,
                                           parent=app.advanced_panel)
    app.button("关闭 · Esc", .83, .576, .30, app.toggle_advanced, parent=app.advanced_panel)
    # 左右两列严格对称：左列 [-0.98, -0.30]（宽 0.68），右列 [0.30, 0.98]（宽 0.68）。
    app.field("duration", "时长 s", 12, .42, x=-.98, width=.34, parent=app.advanced_panel)
    app.field("steer", "目标转角 °", 3, .30, x=-.98, width=.34, parent=app.advanced_panel)
    app.field("cg", "质心高度 m", "", .18, x=-.98, width=.34, parent=app.advanced_panel)
    app.field("radius", "定圆半径 m", 60, .42, x=.30, width=.34, parent=app.advanced_panel)
    app.field("right_mu", "右侧附着 μ", .3, .30, x=.30, width=.34, parent=app.advanced_panel)
    app.field("onset", "输入起始 s", .5, .18, x=.30, width=.34, parent=app.advanced_panel)
    app.field("tire_load", "轮胎基准 N", "", .06, x=-.98, width=.34, parent=app.advanced_panel)
    app.field("bump_height", "凸起高度 m", .01, .06, x=.30, width=.34, parent=app.advanced_panel)
    app.field("bump_length", "凸起长度 m", .9, -.06, x=-.98, width=.34, parent=app.advanced_panel)
    app.field("bump_distance", "凸起距离 m", 6, -.06, x=.30, width=.34, parent=app.advanced_panel)
    app.field("sweep_end", "扫点末速 km/h", 90, -.18, x=-.98, width=.34, parent=app.advanced_panel)
    app.button("导入悬架台架数据", .64, -.18, .68, app.open_suspension_bench, parent=app.advanced_panel)
    app.road_class_menu = app.option(["路谱 ISO-A 级", "路谱 ISO-B 级", "路谱 ISO-C 级", "路谱 ISO-D 级"],
                                     -.98, -.31, .68, parent=app.advanced_panel, parameter="road_class")
    app.road_class_menu.set(2, fCommand=0)
    app.feedback_menu = app.option(["反馈：仿真真值", "反馈：传感器 EKF"],
                                   .30, -.31, .68, parent=app.advanced_panel, parameter="feedback_source")
    app.feedback_menu.set(0, fCommand=0)
    app.parameter_hint = app.text("", -.98, -.46, .029, MUTED, parent=app.advanced_panel)
    app.parameter_hint.textNode.setWordwrap(66)
    app.advanced_panel.hide()

    app.details_panel = _modal_backdrop(root, 95)
    _card(app.details_panel, "details-card", (-1.08, 1.08, -.46, .66), .026)
    DirectFrame(parent=app.details_panel, frameColor=LAB_ACCENT_A, frameSize=(-.99, -.98, .528, .584))
    app.text("当前时刻遥测信号", -.95, .542, .044, LAB_TEXT, parent=app.details_panel, font=app.heading_font)
    app.button("关闭 · Esc", .81, .556, .30, app.toggle_details, parent=app.details_panel)
    app.telemetry = app.text("等待试验数据", -.95, .42, .033, LAB_TEXT, parent=app.details_panel)
    app.wheel_telemetry = app.text("", .10, .42, .033, LAB_TEXT, parent=app.details_panel)
    app.details_panel.hide()

    app.manual_panel = _modal_backdrop(root, 95)
    _card(app.manual_panel, "manual-card", (-.88, .88, -.16, .54), .026)
    DirectFrame(parent=app.manual_panel, frameColor=LAB_ACCENT_B, frameSize=(-.79, -.78, .408, .464))
    app.text("执行器输入", -.75, .422, .044, LAB_TEXT, parent=app.manual_panel, font=app.heading_font)
    app.button("关闭 · Esc", .61, .436, .30, app.manual_panel.hide, parent=app.manual_panel)
    app.manual_entries = {}
    for i, (key, label, value) in enumerate((("throttle", "油门 %", 0), ("brake", "制动 %", 0),
                                             ("gear", "挡位", 1), ("clutch", "离合 %", 100))):
        x = -.75 + i * .39
        app.field_labels["manual."+key] = app.text(label, x, .300, .030, MUTED, parent=app.manual_panel)
        target = DirectFrame(parent=app.manual_panel, relief=None, state=DGG.NORMAL,
                             frameColor=(0, 0, 0, 0),
                             frameSize=(0, .33, -.018, .042), pos=(x, 0, .300))
        app.bind_parameter(target, f"manual.{key}")
        entry_scale = .036
        pad_x = .26
        span = .33 / entry_scale
        app.manual_entries[key] = DirectEntry(parent=app.manual_panel, initialText=str(value),
            text_font=app.font, text_fg=LAB_TEXT, scale=entry_scale,
            width=max(2.0, span - 2 * pad_x), numLines=1, focus=0,
            frameSize=(-pad_x, span - pad_x, -.52, 1.12),
            frameColor=LAB_FIELD, pos=(x + pad_x * entry_scale, 0, .205), relief=DGG.FLAT)
        app.bind_parameter(app.manual_entries[key], f"manual.{key}", focus=True)
    app.text("目标转角在高级参数中设置 · R=-1 / N=0 / D=1…", -.75, .072,
             .029, MUTED, parent=app.manual_panel)
    app.button("确认输入", .52, -.048, .48, app.apply_manual, parent=app.manual_panel, accent=True)
    app.manual_panel.hide()

    app.parameter_help = ParameterHelp(app)
    app.engineering_panel = EngineeringPanel(app)
