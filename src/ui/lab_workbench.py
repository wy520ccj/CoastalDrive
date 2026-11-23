"""现代汽车工程试验台：深海顶栏、冷瓷精密卡片、直达控制策略与互斥零遮挡弹窗。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectEntry, DirectFrame, DirectSlider
from panda3d.core import TextNode, TransparencyAttrib

from lab_experiment import MANEUVERS
from ui import theme
from ui.lab_feedback import LabFeedback
from ui.lab_plot import LabPlot
from ui.lab_widgets import BORDER, MUTED, rounded_panel
from vehicle_designs import DESIGN_VEHICLES

VIEWPORT = (-.90, .90, .06, .66)
_VEHICLE_LABELS = {
    "game-tuned": "游戏调校",
    "reference-rwd": "参考后驱 RWD",
    "reference-fwd": "参考前驱 FWD",
    "reference-awd": "参考四驱 AWD",
    "gr86-2022-premium-6mt": "GR86 Premium 6MT",
}


def _card(parent, name, box, radius=.022, fill=theme.PAPER_LIGHT):
    left, right, bottom, top = box
    rounded_panel(parent, name+"-edge", (left-.004, right+.004, bottom-.004, top+.004), BORDER, radius+.002)
    return rounded_panel(parent, name, box, fill, radius)


def _modal_backdrop(parent, sort_order):
    frame = DirectFrame(parent=parent, frameColor=(.04, .06, .09, .58),
                        frameSize=(-1.78, 1.78, -1.0, 1.0), sortOrder=sort_order, state=DGG.NORMAL)
    frame.setTransparency(TransparencyAttrib.MAlpha)
    return frame


def build_workbench(app):
    root = app.root
    display_font = theme.load_font(theme.DISPLAY_FONT_FILE)

    # 精密冷瓷灰背景，围绕真实 3D 视窗镂空，绝不遮盖车辆渲染区。
    for box in ((-1.78, 1.78, .66, 1.5), (-1.78, 1.78, -1.5, .06),
                (-1.78, -.90, .06, .66), (.90, 1.78, .06, .66)):
        DirectFrame(parent=root, frameColor=theme.PAPER, frameSize=box, sortOrder=-100)

    # 顶栏深海一体通栏（与游戏主界面统一品牌语言）。
    DirectFrame(parent=root, frameColor=theme.SLATE_BAR, frameSize=(-1.78, 1.78, .82, 1.02), sortOrder=-50)
    DirectFrame(parent=root, frameColor=theme.SLATE_BORDER, frameSize=(-1.78, 1.78, .816, .82), sortOrder=-49)
    app.text("COASTAL DRIVE", -1.70, .892, .052, theme.TEXT_LIGHT, font=display_font)
    DirectFrame(parent=root, frameColor=theme.ORANGE, frameSize=(-1.125, -1.117, .868, .952))
    app.text("专家试验台", -1.08, .894, .050, theme.TEXT_LIGHT, font=app.heading_font)
    app.text("配置 · 回看 · 对比", -.66, .898, .031, theme.TEXT_SUB)

    app.button("保存与试驾", .18, .910, .38, lambda: app.design_loop.show(), dark=True)
    app.button("参数说明 F1", .62, .910, .39, app.show_parameter_help, dark=True)
    app.button("记录 ▼", 1.04, .910, .34, app.toggle_record_menu, dark=True)
    app.button("返回驾驶", 1.48, .910, .42, app.back_to_game, dark=True)

    # 三大主卡片区：左通高配置卡、中视窗播放卡、右结果对比卡。
    _card(root, "trial-card", (-1.72, -.98, -.95, .78))
    _card(root, "result-card", (.98, 1.72, -.18, .78))
    _card(root, "viewport-top", (-.94, .94, .66, .78))
    _card(root, "viewport-bottom", (-.94, .94, -.18, .06))
    DirectFrame(parent=root, frameColor=theme.PAPER_LIGHT, frameSize=(-.94, -.90, .05, .67))
    DirectFrame(parent=root, frameColor=theme.PAPER_LIGHT, frameSize=(.90, .94, .05, .67))
    DirectFrame(parent=root, frameColor=BORDER, frameSize=(-.944, -.94, .05, .67))
    DirectFrame(parent=root, frameColor=BORDER, frameSize=(.94, .944, .05, .67))

    for x, label in ((-1.62, "试验配置"), (-.84, "车辆视窗"), (1.08, "试验结果")):
        DirectFrame(parent=root, frameColor=theme.ORANGE, frameSize=(x-.042, x-.032, .692, .744))
        app.text(label, x, .702, .042, font=app.heading_font)

    # ── 左栏上段：车辆、工况、初速/附着、直达电子控制 ──
    app.text("车辆模型", -1.64, .625, .030, MUTED)
    vehicle_items = [_VEHICLE_LABELS.get(design.id, design.name.split(" · ")[0])
                     for design in DESIGN_VEHICLES]
    app.vehicle_menu = app.option(vehicle_items, -1.64, .565, .60,
                                  command=app.choose_vehicle, parameter="vehicle")
    app.vehicle_menu.set(1, fCommand=0)
    app.configuration_note = app.text("车型默认 · 无独立轮心", -1.64, .492, .029, MUTED)

    app.text("试验工况", -1.64, .432, .030, MUTED)
    app.maneuver_menu = app.option(list(MANEUVERS.values()), -1.64, .372, .60,
                                   app.apply_preset, parameter="maneuver")
    app.field("speed", "初速 km/h", 100, .276, x=-1.64, width=.24)
    app.field("mu", "路面附着 μ", 1.1, .196, x=-1.64, width=.24)

    # 将 ABS 与 ESC/ABS-DYC 控制策略并列直达主面板，无需再钻二级弹窗寻找。
    app.abs_menu = app.option(["ABS 开启", "ABS 关闭"], -1.64, .105, .60, parameter="abs")
    app.esc_menu = app.option(["ESC 关闭", "ESC 开启", "协调控制（ABS–DYC）"], -1.64, .015, .60,
                              command=app.select_stability_control, parameter="esc")

    app.advanced_button = app.button("高级参数 ›", -1.50, -.088, .28, app.toggle_advanced)
    app.reset_button = app.button("重置参数", -1.18, -.088, .28, app.reset_parameters)
    app.start_button = app.button("开始试验", -1.34, -.196, .60, app.start_experiment, accent=True)
    app.button("设为对照 A", -1.34, -.296, .60, app.pin_baseline)

    # ── 左栏下段：曲线切换与工坊入口（规整收纳，彻底清空底部拥挤区）──
    DirectFrame(parent=root, frameColor=BORDER, frameSize=(-1.64, -1.04, -.376, -.372))
    app.text("曲线组", -1.64, -.434, .030, MUTED)
    app.plot_menu = app.option(["制动响应", "转向响应", "四轮法向载荷", "四轮滑移率", "轮胎力 / 轮速", "路径跟踪", "执行器响应",
                               "轮胎侧偏角", "附着利用率", "车身侧偏 / 侧倾", "左右载荷转移", "轮胎回正力矩",
                               "质心运动", "车身 / 轮心振动", "悬架行程 / 速度", "轮胎径向压缩"],
                              -1.64, -.500, .60, app.set_plot_group, parameter="plot")
    app.button("新手工坊", -1.34, -.632, .60, lambda: app.workshop.show())
    app.button("方案库", -1.34, -.734, .60, lambda: app.schemes.show())
    app.text("F1 参数说明 · Space 暂停/继续", -1.64, -.858, .028, MUTED)

    # ── 中栏：3D 视窗工具与播放控制条 ──
    app.button("切换视角", .74, .718, .28, app.cycle_camera)
    app.manual_button = app.button("执行器输入", .38, .718, .32, app.show_manual)
    app.manual_button.hide()

    app.model_note = app.text("设计参考车 RWD", -.88, .012, .031, MUTED)
    app.model_note.textNode.setWordwrap(38)
    app.cursor_label = app.text("t = 0.000 s", .88, .012, .033, theme.INK, align=TextNode.ARight)

    app.button("暂停", -.75, -.074, .26, app.toggle_pause)
    app.button("单步", -.46, -.074, .26, app.single_step)
    app.button("回放", -.17, -.074, .26, app.toggle_playback)
    app.timeline = DirectSlider(parent=root, range=(0, 1), value=0, pageSize=1, scrollSize=0,
        frameSize=(-.38, .38, -.032, .032), frameVisibleScale=(1, .14), frameColor=(.82, .86, .90, 1),
        thumb_frameColor=theme.ORANGE, thumb_frameSize=(-.014, .014, -.024, .024),
        thumb_relief=DGG.FLAT, borderWidth=(0, 0), relief=DGG.FLAT,
        pos=(.47, 0, -.074), command=app.seek)
    for control in (app.timeline, app.timeline.thumb):
        control.bind(DGG.B1PRESS, app.set_pointer, [True])
        control.bind(DGG.B1RELEASE, app.set_pointer, [False])
    app.text("时间轴 · 点击或拖动分析任意时刻", -.88, -.150, .028, MUTED)
    app.text("A 海湾青   ·   B 赛道橙", .88, -.150, .028, MUTED, align=TextNode.ARight)

    # ── 右栏：核心指标 + 双色 A/B 对比卡 + 规整分析操作 ──
    app.status = app.text("等待试验", 1.66, .706, .031, theme.SEA, align=TextNode.ARight)
    app.metric_label = app.text("停车距离", 1.05, .612, .031, MUTED)
    app.metric = app.text("—", 1.05, .498, .100, theme.ORANGE, font=app.heading_font)

    # 双色 A/B 对比胶囊子卡，一眼分清 A 基线与 B 当前。
    rounded_panel(root, "slot-a", (1.04, 1.34, .275, .445), (.925, .968, .982, 1), .016)
    rounded_panel(root, "slot-b", (1.36, 1.66, .275, .445), (.995, .945, .922, 1), .016)
    app.baseline_label = app.text("对照 A", 1.06, .392, .028, theme.SEA)
    app.candidate_label = app.text("本次 B", 1.38, .392, .028, theme.ORANGE)
    app.baseline_value = app.text("—", 1.06, .314, .044, theme.SEA, font=app.heading_font)
    app.candidate_value = app.text("—", 1.38, .314, .044, theme.ORANGE, font=app.heading_font)

    app.result = app.text("设为对照 A 后显示差值", 1.05, .206, .031, MUTED)
    app.timing = app.text("仿真 — · 计算 —", 1.05, .136, .028, MUTED)

    app.button("详细信号", 1.19, .026, .29, app.toggle_details)
    app.button("工程指标", 1.51, .026, .29, app.show_engineering)
    app.button("清除 A", 1.19, -.084, .29, app.clear_baseline)
    app.button("导出报告", 1.51, -.084, .29, app.export)

    # ── 底部全宽双曲线分析卡 ──
    app.plots = [LabPlot(root, app.font, (-.94, .36, -.88, -.22), "speed"),
                 LabPlot(root, app.font, (.40, 1.72, -.88, -.22), "ax")]
    for plot in app.plots:
        plot.update(())

    # 底部通栏状态条（绝不再和按钮打架）。
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

    # ── 互斥浮层弹窗：均带独立遮罩或清晰高层次边框，彻底消除互相遮挡 ──
    app.record_menu = DirectFrame(parent=root, frameColor=(.04, .06, .09, .34),
                                  frameSize=(-1.78, 1.78, -1.0, 1.0), sortOrder=95, state=DGG.NORMAL)
    app.record_menu.setTransparency(TransparencyAttrib.MAlpha)
    app.record_menu.bind(DGG.B1PRESS, lambda _event: app.record_menu.hide())
    DirectFrame(parent=app.record_menu, frameColor=(0, 0, 0, 0),
                frameSize=(.90, 1.68, .06, .82), state=DGG.NORMAL)
    _card(app.record_menu, "record-card", (.92, 1.66, .08, .80), .022)
    DirectFrame(parent=app.record_menu, frameColor=theme.ORANGE, frameSize=(.97, .98, .726, .768))
    app.text("记录与工程文件", 1.00, .734, .034, theme.INK, parent=app.record_menu, font=app.heading_font)
    app.button("收起", 1.53, .744, .17, app.record_menu.hide, parent=app.record_menu)
    for z, label, action in ((.645, "载入实验记录", app.open_record),
                             (.543, "复算当前记录", app.recalculate_record),
                             (.441, "打开导出报告", app.open_report),
                             (.339, "导入工程模型", app.open_engineering)):
        app.button(label, 1.29, z, .60, action, parent=app.record_menu)
    app.driving_car_button = app.button("载入驾驶车硬件", 1.29, .237, .60,
                                        app.stage_driving_vehicle, parent=app.record_menu)
    app.driving_car_button["state"] = DGG.NORMAL if app.workspace_vehicle is not None else DGG.DISABLED
    app.road_retest_button = app.button("道路 A/B 复测", 1.29, .135, .60,
                                        app.road_retest.show, parent=app.record_menu)
    app.road_retest_button["state"] = DGG.DISABLED
    app.record_menu.hide()

    app.advanced_panel = _modal_backdrop(root, 90)
    _card(app.advanced_panel, "advanced-card", (-1.16, 1.22, -.52, .68), .026)
    DirectFrame(parent=app.advanced_panel, frameColor=theme.ORANGE, frameSize=(-1.09, -1.08, .55, .605))
    app.text("高级试验参数", -1.05, .562, .045, parent=app.advanced_panel, font=app.heading_font)
    app.advanced_reset_button = app.button("重置当前工况", .62, .576, .38, app.reset_parameters,
                                           parent=app.advanced_panel)
    app.button("关闭 · Esc", 1.02, .576, .30, app.toggle_advanced, parent=app.advanced_panel)
    app.field("duration", "时长 s", 12, .41, x=-1.04, width=.28, parent=app.advanced_panel)
    app.field("steer", "目标转角 °", 3, .29, x=-1.04, width=.28, parent=app.advanced_panel)
    app.field("cg", "质心高度 m", "", .17, x=-1.04, width=.28, parent=app.advanced_panel)
    app.field("radius", "定圆半径 m", 60, .41, x=.14, width=.28, parent=app.advanced_panel)
    app.field("right_mu", "右侧附着 μ", .3, .29, x=.14, width=.28, parent=app.advanced_panel)
    app.field("onset", "输入起始 s", .5, .17, x=.14, width=.28, parent=app.advanced_panel)
    app.field("tire_load", "轮胎基准 N", "", .05, x=-1.04, width=.28, parent=app.advanced_panel)
    app.field("bump_height", "凸起高度 m", .01, .05, x=.14, width=.28, parent=app.advanced_panel)
    app.field("bump_length", "凸起长度 m", .9, -.07, x=-1.04, width=.28, parent=app.advanced_panel)
    app.field("bump_distance", "凸起距离 m", 6, -.07, x=.14, width=.28, parent=app.advanced_panel)
    app.button("导入悬架台架数据", .58, -.21, .60, app.open_suspension_bench, parent=app.advanced_panel)
    app.parameter_hint = app.text("", -1.04, -.36, .029, MUTED, parent=app.advanced_panel)
    app.parameter_hint.textNode.setWordwrap(68)
    app.advanced_panel.hide()

    app.details_panel = _modal_backdrop(root, 95)
    _card(app.details_panel, "details-card", (-1.16, 1.22, -.42, .68), .026)
    DirectFrame(parent=app.details_panel, frameColor=theme.SEA, frameSize=(-1.09, -1.08, .55, .605))
    app.text("真实信号 · 当前时间游标", -1.05, .562, .044, parent=app.details_panel, font=app.heading_font)
    app.button("关闭 · Esc", 1.02, .576, .30, app.toggle_details, parent=app.details_panel)
    app.telemetry = app.text("等待真实实验信号", -1.04, .44, .033, parent=app.details_panel)
    app.wheel_telemetry = app.text("", .12, .44, .033, parent=app.details_panel)
    app.details_panel.hide()

    app.manual_panel = _modal_backdrop(root, 95)
    _card(app.manual_panel, "manual-card", (-.88, .92, -.12, .54), .026)
    DirectFrame(parent=app.manual_panel, frameColor=theme.ORANGE, frameSize=(-.81, -.80, .41, .465))
    app.text("执行器输入", -.77, .422, .044, parent=app.manual_panel, font=app.heading_font)
    app.button("关闭 · Esc", .72, .436, .30, app.manual_panel.hide, parent=app.manual_panel)
    app.manual_entries = {}
    for i, (key, label, value) in enumerate((("throttle", "油门 %", 0), ("brake", "制动 %", 0),
                                             ("gear", "挡位", 1), ("clutch", "离合 %", 100))):
        x = -.76+i*.40
        app.field_labels["manual."+key] = app.text(label, x, .295, .030, MUTED, parent=app.manual_panel)
        target = DirectFrame(parent=app.manual_panel, relief=None, state=DGG.NORMAL,
                             frameColor=(0, 0, 0, 0),
                             frameSize=(0, .32, -.015, .045), pos=(x, 0, .295))
        app.bind_parameter(target, f"manual.{key}")
        app.manual_entries[key] = DirectEntry(parent=app.manual_panel, initialText=str(value),
            text_font=app.font, text_fg=theme.INK, scale=.036, width=7,
            frameColor=(.935, .950, .965, 1), pos=(x, 0, .205), relief=DGG.FLAT)
        app.bind_parameter(app.manual_entries[key], f"manual.{key}", focus=True)
    app.text("目标转角在高级参数中设置 · R=-1 / N=0 / D=1…", -.76, .095,
             .029, MUTED, parent=app.manual_panel)
    app.button("确认输入", .58, -.025, .48, app.apply_manual, parent=app.manual_panel, accent=True)
    app.manual_panel.hide()

    app.parameter_help = ParameterHelp(app)
    app.engineering_panel = EngineeringPanel(app)
