"""按已认可设计图排版：配置、车辆、核心结果及两张主要曲线。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectEntry, DirectFrame, DirectSlider
from panda3d.core import CardMaker, Point2

from lab_experiment import MANEUVERS
from ui import theme
from ui.lab_plot import LabPlot
from ui.lab_widgets import rounded_panel

VIEWPORT = (-.88, .90, -.02, .62)


def build_workbench(app):
    root = app.root
    # 背景围绕真正的3D视窗绘制，不用静态设计图覆盖车辆。
    for box in ((-1.78, 1.78, .62, 1), (-1.78, 1.78, -1, -.02),
                (-1.78, -.88, -.02, .62), (.90, 1.78, -.02, .62)):
        DirectFrame(parent=root, frameColor=theme.PAPER, frameSize=box, sortOrder=-100)
    header = CardMaker("lab-coastal-header")
    header.setFrame(-1.78, 1.78, .80, 1)
    header.setUvRange(Point2(0, .70), Point2(1, .83))
    art = root.attachNewNode(header.generate())
    art.setTexture(app.loader.loadTexture(theme.asset_filename("backgrounds/coastal-menu.png")))
    DirectFrame(parent=root, frameColor=theme.PAPER_LIGHT, frameSize=(-1.78, -.23, .80, 1))
    app.text("COASTAL DRIVE", -1.65, .868, .092, font=app.display_font)
    app.text("车辆实验室", -.66, .894, .047, font=app.heading_font)
    app.text("VEHICLE DYNAMICS LAB", -.66, .837, .035, theme.MUTED)
    DirectFrame(parent=root, frameColor=theme.ORANGE, frameSize=(-1.78, 1.78, .793, .798))
    app.button("‹  返回驾驶", 1.15, .90, .36, app.back_to_game)
    app.button("记录", 1.57, .90, .28, app.toggle_record_menu)

    rounded_panel(root, "trial-card", (-1.72, -.98, -.47, .75), theme.PAPER_LIGHT)
    rounded_panel(root, "result-card", (.98, 1.72, -.19, .75), theme.PAPER_LIGHT)
    rounded_panel(root, "viewport-header", (-.94, .94, .62, .75), theme.PAPER_LIGHT)
    rounded_panel(root, "viewport-controls", (-.94, .94, -.19, -.02), theme.PAPER_LIGHT)
    DirectFrame(parent=root, frameColor=theme.PAPER_LIGHT, frameSize=(-.94, -.88, -.02, .63))
    DirectFrame(parent=root, frameColor=theme.PAPER_LIGHT, frameSize=(.90, .94, -.02, .63))
    for x, label in ((-1.63, "试验配置"), (-.84, "车辆视窗"), (1.07, "试验结果")):
        DirectFrame(parent=root, frameColor=theme.ORANGE, frameSize=(x-.045, x-.035, .638, .695))
        app.text(label, x, .646, .047, font=app.heading_font)

    app.text("车辆模型", -1.62, .542, .032, theme.MUTED)
    app.vehicle_menu = app.option(["游戏调校", "参考后驱 RWD", "参考前驱 FWD", "参考四驱 AWD", "GR86 Premium 6MT"],
                                 -1.63, .463, .60)
    app.vehicle_menu.set(1)
    app.text("试验工况", -1.62, .360, .032, theme.MUTED)
    app.maneuver_menu = app.option(list(MANEUVERS.values()), -1.63, .282, .60, app.apply_preset)
    app.field("speed", "初速 km/h", 100, .168, width=.23)
    app.field("mu", "路面附着 μ", 1.1, .074, width=.23)
    app.abs_menu = app.option(["ABS 开启", "ABS 关闭"], -1.63, -.031, .60)
    app.button("高级参数  ›", -1.33, -.143, .60, app.toggle_advanced)
    app.button("开始试验", -1.33, -.292, .60, app.start_experiment, accent=True)
    app.button("固定当前为 A", -1.33, -.395, .60, app.pin_baseline)
    app.text("离线实验 / 固定120 Hz\n零交通 / 平整试验场", -1.62, -.57, .035, theme.MUTED)

    app.model_note = app.text("设计参考车 RWD", -.84, -.053, .035, theme.MUTED)
    app.button("切换视角", .73, .674, .29, app.cycle_camera)
    app.status = app.text("等待试验", 1.07, .552, .033, theme.SEA)
    app.metric_label = app.text("停车距离", 1.07, .456, .035, theme.MUTED)
    app.metric = app.text("—", 1.07, .328, .110, theme.ORANGE, font=app.heading_font)
    app.text("方案 A", 1.07, .235, .031, theme.SEA)
    app.text("方案 B", 1.43, .235, .031, theme.ORANGE)
    app.baseline_value = app.text("—", 1.07, .158, .052, theme.SEA, font=app.heading_font)
    app.candidate_value = app.text("—", 1.43, .158, .052, theme.ORANGE, font=app.heading_font)
    app.result = app.text("固定 A 后比较", 1.07, .077, .029, theme.MUTED)
    app.timing = app.text("仿真  —\n计算  —", 1.07, -.008, .030, theme.MUTED)
    app.button("查看详细信号  ›", 1.35, -.135, .56, app.toggle_details)

    app.button("暂停", -.70, -.100, .30, app.toggle_pause)
    app.button("单步", -.34, -.100, .30, app.single_step)
    app.button("回放", .02, -.100, .30, app.toggle_playback)
    app.timeline = DirectSlider(parent=root, range=(0, 1), value=0, pageSize=.001,
        frameSize=(-.28, .28, -.009, .009), frameColor=(.77, .82, .80, 1),
        thumb_frameColor=theme.ORANGE, thumb_frameSize=(-.014, .014, -.025, .025),
        thumb_relief=DGG.FLAT, borderWidth=(0, 0), relief=DGG.FLAT,
        pos=(.55, 0, -.104), command=app.seek)
    app.cursor_label = app.text("0.000 s", .30, -.051, .025, theme.MUTED)
    app.timeline.bind(DGG.ENTER, app.set_timeline_hover, [True])
    app.timeline.bind(DGG.EXIT, app.set_timeline_hover, [False])
    app.timeline.thumb.bind(DGG.ENTER, app.set_timeline_hover, [True])
    app.timeline.thumb.bind(DGG.EXIT, app.set_timeline_hover, [False])

    app.plots = [LabPlot(root, app.font, (-.94, .36, -.86, -.27), "speed"),
                 LabPlot(root, app.font, (.40, 1.72, -.86, -.27), "ax")]
    for plot in app.plots:
        plot.update(())
    app.plot_menu = app.option(["制动响应", "转向响应", "四轮法向载荷", "四轮滑移率", "轮胎力 / 轮速", "路径跟踪", "执行器响应"],
                              -1.63, -.785, .60, app.set_plot_group)
    app.text("曲线组", -1.62, -.700, .030, theme.MUTED)
    app.text("A 海蓝   B 橙色", .60, -.238, .026, theme.MUTED)
    app.button("清除 A", 1.50, -.228, .26, app.clear_baseline)
    app.notice = app.text("选择工况，开始第一次试验", -.88, -.955, .027, theme.MUTED)
    app.button("导出 CSV / 报告", 1.36, -.935, .62, app.export)

    app.record_menu = DirectFrame(parent=root, frameColor=theme.PAPER_LIGHT,
                                 frameSize=(1.05, 1.71, .47, .83), sortOrder=60)
    for z, label, action in ((.76, "载入记录", app.open_record), (.65, "复算当前记录", app.recalculate_record),
                             (.54, "打开报告", app.open_report)):
        app.button(label, 1.38, z, .56, action, parent=app.record_menu)
    app.record_menu.hide()

    app.advanced_panel = DirectFrame(parent=root, frameColor=theme.PAPER_LIGHT,
                                    frameSize=(-.94, 1.72, -.18, .69), sortOrder=70)
    app.text("高级参数", -.82, .578, .047, parent=app.advanced_panel, font=app.heading_font)
    app.button("关闭", 1.52, .592, .26, app.toggle_advanced, parent=app.advanced_panel)
    app.field("duration", "时长 s", 12, .44, x=-.82, parent=app.advanced_panel)
    app.field("steer", "目标转角 °", 3, .32, x=-.82, parent=app.advanced_panel)
    app.field("cg", "质心高度 m", "", .20, x=-.82, parent=app.advanced_panel)
    app.field("radius", "定圆半径 m", 60, .44, x=.44, parent=app.advanced_panel)
    app.field("right_mu", "右侧附着 μ", .3, .32, x=.44, parent=app.advanced_panel)
    app.field("onset", "转向起始 s", .5, .20, x=.44, parent=app.advanced_panel)
    app.esc_menu = app.option(["ESC 关闭", "ESC 开启"], -.82, .071, .62, parent=app.advanced_panel)
    app.text("质心留空采用车型配置；右侧附着仅用于对开制动。\n改动用于下一次试验，当前结果仍对应原配置。", -.82, -.06,
             .030, theme.MUTED, parent=app.advanced_panel)
    app.advanced_panel.hide()

    app.details_panel = DirectFrame(parent=root, frameColor=theme.PAPER_LIGHT,
                                   frameSize=(-.84, 1.70, -.16, .70), sortOrder=80)
    app.text("真实信号 / 当前时间游标", -.74, .602, .045,
             parent=app.details_panel, font=app.heading_font)
    app.button("关闭", 1.50, .622, .26, app.toggle_details, parent=app.details_panel)
    app.telemetry = app.text("等待真实实验信号", -.74, .506, .034, parent=app.details_panel)
    app.wheel_telemetry = app.text("", .55, .506, .034, parent=app.details_panel)
    app.details_panel.hide()

    app.manual_panel = DirectFrame(parent=root, frameColor=theme.PAPER_LIGHT,
                                  frameSize=(-.75, .94, -.02, .55), sortOrder=80)
    app.text("执行器输入", -.65, .441, .045, parent=app.manual_panel, font=app.heading_font)
    app.manual_entries = {}
    for i, (key, label, value) in enumerate((("throttle", "油门 %", 0), ("brake", "制动 %", 0),
                                           ("gear", "挡位", 1), ("clutch", "离合 %", 100))):
        x = -.65+i*.38
        app.text(label, x, .312, .030, theme.MUTED, parent=app.manual_panel)
        app.manual_entries[key] = DirectEntry(parent=app.manual_panel, initialText=str(value),
            text_font=app.font, text_fg=theme.INK, scale=.038, width=7,
            frameColor=theme.PAPER, pos=(x, 0, .22), relief=DGG.FLAT)
    app.text("目标转角在高级参数中设置。R=-1 / N=0 / D=1…", -.65, .112,
             .028, theme.MUTED, parent=app.manual_panel)
    app.button("应用输入", .56, .052, .55, app.apply_manual, parent=app.manual_panel, accent=True)
    app.manual_panel.hide()
    app.manual_button = app.button("执行器", .00, .674, .30, app.show_manual)
    app.manual_button.hide()
