"""落日黑曜石与琥珀金风格自选车综合杯与第一季总览结算。"""

from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import TextNode, TransparencyAttrib

from career import EVENT_BY_ID
from career_garage import CAR_BY_DESIGN, GARAGE_CARS
from driving_tour import POINTS
from season_cup import CUP_LEGS, cup_specs
from tour_budget import tour_medal, tour_points
from ui import atelier, theme
from ui.career_layout import WHITE, canvas
from ui.lab_widgets import gradient_panel
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle

STAGE_NAMES = ('滨海计时', '山脊冲刺', '弯坡车流')


def draw(panel, progress, store, *, picking, recap, preview):
    app = panel.vehicle_view.base
    title = '选择参赛车辆' if picking else '第一季结算' if recap else '自选车综合杯'
    width, left, fill, label, image, button = canvas(panel, progress, title, season=True)
    unit = 2/941
    right = width*.56
    span = right-left-28
    design_id = store.specs[CUP_LEGS[0]].design_id if store is not None else app.workspace_vehicle.design_id
    car = CAR_BY_DESIGN.get(preview or design_id, GARAGE_CARS[0])
    compatible = app._cup_available()
    show_car(panel, car, width, right, fill, label, image)
    notice = app.cup_notice or (store.notice if store is not None else '')
    if not compatible:
        notice = '发车前请使用游戏驾驶和默认 ABS / TCS / ESC。'

    if picking:
        rows = tuple(item for item in GARAGE_CARS if progress.stars >= item.unlock)
        ready = set()
        for item in rows:
            try:
                cup_specs(item.design_id)
            except (OSError, ValueError, KeyError, TypeError):
                continue
            ready.add(item.design_id)
        label('第一季  /  自选车综合杯', left, 102, 14, theme.DARK_SUB)
        label('选择参赛车辆', left, 136, 30, WHITE, bold=True)
        for index, item in enumerate(rows):
            y = 158+index*74
            selected_row = item == car
            image('atelier/card-active.png' if selected_row else 'atelier/card-idle.png', left-4, y-4, span+8, 64+8)
            button('', left, y, span, 64, 'cup-preview', item.design_id, role='event-card')
            panel.card_edges[len(panel.buttons)-1] = fill(left, y, 4, 64, (0, 0, 0, 0), 2)
            c_let, c_scr, _, _, _ = theme.vehicle_pi(vehicle_design(item.design_id).config)
            fill(left+14, y+18, 72, 28, theme.STEEL_BG, 5)
            lbl_pi = label(f'{c_let} {c_scr}', left+50, y+38, 15, theme.STEEL_TEXT, bold=True, display=True)
            lbl_pi.textNode.setAlign(TextNode.ACenter)
            label(item.name, left+102, y+40, 21, theme.AMBER if selected_row else WHITE, bold=True)
            image('atelier/radio-active.png' if selected_row else 'atelier/radio-idle.png', left+span-38, y+20, 24, 24)
            if item.design_id not in ready:
                label('标定中', left+span-54, y+40, 16, theme.DARK_SUB, right=True)
        available = compatible and car.design_id in ready
        sel_btn = button('使用这辆车', width-left-238, 866, 238, 56, 'cup-select', car.design_id,
                         role='primary', primary=True, enabled=available)
        sel_btn['text_pos'] = (16*unit, -7*unit)
        s_ic = atelier.picture(sel_btn, panel.loader, 'atelier/icon-steering.png',
                               (-78*unit, -52*unit, -13*unit, 13*unit),
                               color=theme.INK if available else theme.DARK_LOCKED)
        panel.frames.append(s_ic)
    else:
        series_rows(panel, progress, store, car, recap, width, left, span, fill, label, image, button, compatible)
    if notice:
        label(notice, left, 822, 16, theme.AMBER, wrap=span)
    button('返回综合杯' if picking and store is not None else '返回赛事', left, 866, 172, 56, panel.back,
           role='footer')
    primary = panel.buttons[panel.primary]
    panel.select(panel.primary if primary['state'] == DGG.NORMAL else len(panel.buttons)-1)


def show_car(panel, car, width, right, fill, label, image):
    unit = 2/941
    stage_w = width-right
    image(atelier.SUNSET_GARAGE_BG, right, 70, stage_w, 779, crop=True)
    gradient_panel(panel.content, 'cup-stage-left',
                   ((right-width/2)*unit, (right+80-width/2)*unit, 1-849*unit, 1-70*unit),
                   (0.045, 0.055, 0.078, 0.85), (0.045, 0.055, 0.078, 0.0), horizontal=True)
    gradient_panel(panel.content, 'cup-stage-bot',
                   ((right-width/2)*unit, (width/2)*unit, 1-849*unit, 1-680*unit),
                   (0.040, 0.050, 0.072, 0.88), (0.040, 0.050, 0.072, 0.0))
    image('atelier/floor-warm-bounce.png', right-12, 515, stage_w+24, 240, tint=(1, 0.90, 0.74, 0.80))
    box = ((right+12-width/2)*unit, (width/2-18)*unit, 1-740*unit, 1-180*unit)
    vehicle = WorkspaceVehicle(car.design_id, vehicle_design(car.design_id).config)
    panel.vehicle_view.show(panel.content, box, vehicle, studio=True)
    panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
    panel.vehicle_view.highlight(None)
    letter, score, _, power_kw, _ = theme.vehicle_pi(vehicle.config)
    plate_w = min(392., stage_w-44)
    px = (width+right-plate_w)/2
    image('atelier/card-idle.png', px-8, 720, plate_w+16, 100)
    fill(px+8, 748, 3.5, 46, theme.AMBER, 2)
    fill(px+22, 756, 78, 28, theme.STEEL_BG, 5)
    lbl_pi = label(f'{letter} {score}', px+61, 776, 16, theme.STEEL_TEXT, bold=True, display=True)
    lbl_pi.textNode.setAlign(TextNode.ACenter)
    label(car.name, px+plate_w-18, 766, 21, WHITE, bold=True, right=True)
    label(f'{car.category}  |  {power_kw:.0f} kW', px+plate_w-18, 796, 15, theme.DARK_SUB, right=True)


def series_rows(panel, progress, store, car, recap, width, left, span, fill, label, image, button, compatible):
    unit = 2/941
    rows = store.best if recap else store.current
    count = len(rows)
    label('第一季  /  赛季总结' if recap else '第一季  /  自选车综合杯', left, 106, 14, theme.DARK_SUB)
    fill(left, 124, 4, 34, theme.AMBER, 2)
    label('第一季完成' if recap else car.name, left+16, 154, 38, WHITE, bold=True)
    label('综合杯 · '+car.name if recap else f'已完成 {count} / 3 站', left+16, 198, 20, theme.DARK_SUB)
    fill(left, 254, span, 36, (0.055, 0.070, 0.098, 0.85), 6)
    label('站点', left+18, 279, 16, theme.DARK_SUB)
    label('用时', left+span*.66, 279, 16, theme.DARK_SUB, right=True)
    label('评价', left+span-18, 279, 16, theme.DARK_SUB, right=True)
    for index, name in enumerate(STAGE_NAMES):
        y = 304+index*110
        current = index == count
        image('atelier/card-active.png' if current else 'atelier/card-idle.png', left-6, y-6, span+12, 108)
        if current:
            fill(left+8, y+18, 4, 60, theme.AMBER, 2)
        label(f'{index+1:02d}', left+24, y+58, 26, theme.AMBER if current else theme.DARK_SUB,
              bold=True, display=True)
        label(name, left+78, y+58, 25, WHITE, bold=True)
        row = rows[index] if index < count else None
        label('—' if row is None else f'{row.seconds:.3f} s', left+span*.66, y+58, 23,
              WHITE if row is not None else theme.DARK_SUB, right=True, display=row is not None)
        status = row.medal+'牌' if row is not None else '待发车' if current else '等待上一站'
        status_color = theme.AMBER if (current or (row is not None and row.medal == '金')) else (
            theme.STEEL_TEXT if row is not None else theme.DARK_SUB)
        label(status, left+span-20, y+58, 19, status_color, bold=row is not None or current, right=True)
    fill(left, 648, span, 1.2, (0.24, 0.29, 0.38, 0.85), 0)
    points = tour_points(rows, ranked=store.ranked)
    medal = tour_medal(rows, ranked=store.ranked)
    label(f'{medal+"牌 · " if medal else ""}{points} / 9 分', left+12, 704, 27, theme.AMBER, bold=True)
    label('海岸杯决赛 · 已完成' if recap else '每站预算 5000', left+span-12, 704, 18, theme.DARK_SUB, right=True)
    if recap:
        index = min(range(count), key=lambda i: (POINTS[rows[i].medal], -rows[i].seconds/store.specs[
            store.legs[i]].targets[-1].seconds))
        tip = f'可提升赛段 · {STAGE_NAMES[index]}' if points < 9 else '三站金牌 · 可继续刷新总用时'
        image('atelier/card-idle.png', left-6, 728, span+12, 68)
        fill(left+8, 746, 4, 32, theme.AMBER, 2)
        label(tip, left+24, 770, 20, WHITE, bold=True)

    button('更换车型', width-left-436, 866, 174, 56, 'cup-pick', role='secondary')
    if store.unsaved:
        text, action, value = '重试保存进度', 'cup-save', None
    elif recap:
        text, action, value = '同车再赛', 'cup-rerun', car.design_id
    elif count < 3:
        text, action, value = f'配置第 {count+1} 站', 'cup-stage', False
    elif progress.course_record(EVENT_BY_ID['coastal-cup']):
        text, action, value = '第一季结算', 'cup-season-result', None
    else:
        text, action, value = '前往海岸杯决赛', 'brief', 'coastal-cup'
    go_enabled = compatible or action in ('cup-season-result', 'cup-save', 'brief')
    go_btn = button(text, width-left-238, 866, 238, 56, action, value, role='primary', primary=True,
                    enabled=go_enabled)
    go_btn['text_pos'] = (14*unit, -7*unit)
    g_ic = atelier.picture(go_btn, panel.loader, 'atelier/icon-steering.png',
                           (-86*unit, -62*unit, -12*unit, 12*unit),
                           color=theme.INK if go_enabled else theme.DARK_LOCKED)
    panel.frames.append(g_ic)
