"""选车、综合杯总览与第一季结算。"""

from direct.gui import DirectGuiGlobals as DGG
from panda3d.core import TransparencyAttrib

from career import EVENT_BY_ID
from career_garage import CAR_BY_DESIGN, GARAGE_CARS
from driving_tour import POINTS
from season_cup import CUP_LEGS, cup_specs
from tour_budget import tour_medal, tour_points
from ui.career_layout import DARK, GRAY, LINE, ORANGE, WHITE, canvas
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle

STAGE_NAMES = ('滨海计时', '山脊冲刺', '弯坡车流')


def draw(panel, progress, store, *, picking, recap, preview):
    app = panel.vehicle_view.base
    title = '选择参赛车辆' if picking else '第一季结算' if recap else '自选车综合杯'
    width, left, fill, label, image, button = canvas(panel, progress, title, season=True)
    right = width*.58
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
        label('自选车综合杯', left, 152, 44, bold=True)
        for index, item in enumerate(rows):
            y = 191+index*67
            fill(left, y, span, 1, LINE, 0)
            if item == car:
                fill(left, y+1, span, 66, (1, .91, .85, 1), 0)
                fill(left, y+1, 6, 66, ORANGE, 0)
            button('', left, y+1, span, 66, 'cup-preview', item.design_id, role='event-card')
            panel.card_edges[len(panel.buttons)-1] = fill(left, y+1, 6, 66, (0, 0, 0, 0), 0)
            label(item.name, left+18, y+45, 27, bold=True)
            if item.design_id not in ready:
                label('标定中', right-42, y+45, 19, GRAY, right=True)
        available = compatible and car.design_id in ready
        button('使用这辆车', width-left-238, 864, 238, 61, 'cup-select', car.design_id,
               role='primary', primary=True, enabled=available)
    else:
        series_rows(panel, progress, store, car, recap, width, left, span, fill, label, button, compatible)
    if notice:
        label(notice, left, 824, 18, ORANGE, wrap=span)
    button('返回综合杯' if picking and store is not None else '返回赛事', left, 864, 172, 61, panel.back,
           role='footer')
    primary = panel.buttons[panel.primary]
    panel.select(panel.primary if primary['state'] == DGG.NORMAL else len(panel.buttons)-1)


def show_car(panel, car, width, right, fill, label, image):
    image('backgrounds/garage-coastal-v2.png', right, 68, width-right, 780, crop=True)
    unit = 2/941
    box = ((right+12-width/2)*unit, (width/2-18)*unit, 1-749*unit, 1-195*unit)
    vehicle = WorkspaceVehicle(car.design_id, vehicle_design(car.design_id).config)
    panel.vehicle_view.show(panel.content, box, vehicle, studio=True)
    panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
    panel.vehicle_view.highlight(None)
    x = (width+right)/2
    fill(x-159, 739, 318, 48, DARK, 0)
    label(car.category, x-137, 771, 20, WHITE)


def series_rows(panel, progress, store, car, recap, width, left, span, fill, label, button, compatible):
    rows = store.best if recap else store.current
    count = len(rows)
    label('第一季完成' if recap else car.name, left, 158, 48, bold=True)
    label('综合杯 · '+car.name if recap else f'已完成 {count} / 3 站', left, 218, 27, GRAY)
    label('站点', left+16, 301, 22, GRAY)
    label('用时', left+span*.66, 301, 22, GRAY, right=True)
    label('评价', left+span-16, 301, 22, GRAY, right=True)
    for index, name in enumerate(STAGE_NAMES):
        y = 325+index*110
        fill(left, y, span, 1, LINE, 0)
        if index == count:
            fill(left, y+1, span, 109, (1, .91, .85, 1), 0)
            fill(left, y+1, 7, 109, ORANGE, 0)
        label(f'{index+1:02d}   {name}', left+16, y+65, 30, bold=True)
        row = rows[index] if index < count else None
        label('—' if row is None else f'{row.seconds:.3f} s', left+span*.66, y+65, 26, right=True)
        status = row.medal+'牌' if row is not None else '待发车' if index == count else '等待上一站'
        label(status, left+span-16, y+65, 22, ORANGE if index == count else GRAY, right=True)
    fill(left, 655, span, 1, LINE, 0)
    points = tour_points(rows, ranked=store.ranked)
    medal = tour_medal(rows, ranked=store.ranked)
    label(f'{medal+"牌 · " if medal else ""}{points} / 9 分', left+16, 713, 30, ORANGE, bold=True)
    label('海岸杯决赛 · 已完成' if recap else '每站预算 5000', left+span-16, 713, 22, GRAY, right=True)
    if recap:
        index = min(range(count), key=lambda i: (POINTS[rows[i].medal], -rows[i].seconds/store.specs[
            store.legs[i]].targets[-1].seconds))
        tip = f'可提升赛段 · {STAGE_NAMES[index]}' if points < 9 else '三站金牌 · 可继续刷新总用时'
        fill(left, 739, span, 57, (1, .91, .85, 1), 0)
        label(tip, left+16, 776, 23, bold=True)

    button('更换车型', width-left-436, 864, 174, 61, 'cup-pick', role='secondary')
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
    button(text, width-left-238, 864, 238, 61, action, value, role='primary', primary=True,
           enabled=compatible or action in ('cup-season-result', 'cup-save', 'brief'))
