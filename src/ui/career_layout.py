"""生涯四页的构图，对应garage-v2的05至08设计图。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from career import CHAPTERS, EVENTS, PARTS
from career_garage import GARAGE_CARS, garage_cars
from ui import theme
from ui.garage_layout import GRAY, INK, ORANGE, PART_IMAGES, WHITE
from ui.lab_widgets import rounded_panel

GOLD = (1, .73, .25, 1)
DARK = (.04, .055, .075, .88)
PAPER = (.98, .98, .99, .96)
LINE = (.80, .82, .85, 1)


def canvas(panel, progress, title, *, car=False):
    """四页共用同一画布、字体、栏位；具体页面仍由独立业务函数绘制。"""
    aspect = panel.vehicle_view.base.getAspectRatio()
    panel.layout_aspect, panel.garage_roles, panel.card_edges = aspect, {}, {}
    width, unit = 941*aspect, 2/941
    margin = width*.031

    def point(x, y):
        return (x-width/2)*unit, 1-y*unit

    def box(x, y, w, h):
        a, b = point(x, y+h), point(x+w, y)
        return a[0], b[0], a[1], b[1]

    def fill(x, y, w, h, color=PAPER, radius=4):
        node = rounded_panel(panel.content, 'career-fill', box(x, y, w, h), color, radius*unit)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def label(text, x, y, size=22, color=INK, *, bold=False, right=False, wrap=None):
        item = panel.label(text, *point(x, y), size*unit, color,
                           font=panel.font if bold else panel.garage_font)
        if right:
            item.textNode.setAlign(TextNode.ARight)
        if wrap is not None:
            item.textNode.setWordwrap(wrap/size)
        return item

    def image(name, x, y, w, h, *, tint=WHITE, crop=False):
        if name not in panel.garage_textures:
            panel.garage_textures[name] = panel.loader.loadTexture(theme.asset_filename(name))
        texture = panel.garage_textures[name]
        frame = DirectFrame(parent=panel.content, frameSize=box(x, y, w, h),
            frameTexture=texture, frameColor=tint, state=DGG.DISABLED)
        frame.setTransparency(TransparencyAttrib.MAlpha)
        if crop:
            ratio = (w/h)/(texture.getXSize()/texture.getYSize())
            stage = TextureStage.getDefault()
            if ratio < 1:
                frame.setTexScale(stage, ratio, 1)
                frame.setTexOffset(stage, (1-ratio)/2, 0)
            else:
                frame.setTexScale(stage, 1, 1/ratio)
                frame.setTexOffset(stage, 0, (1-1/ratio)/2)
        panel.frames.append(frame)
        return frame

    def button(text, x, y, w, h, command, value=None, *, role='plain', primary=False, enabled=True):
        if role == 'secondary':
            fill(x-1, y-1, w+2, h+2, (.86, .88, .91, .80))
        px, pz = point(x+w/2, y+h/2)
        item = panel.button(text, px, pz, w*unit, h*unit, command, value,
                            primary=primary, enabled=enabled, radius=4*unit)
        item['text_font'] = panel.font if role == 'primary' else panel.garage_font
        size = 22 if h < 44 else 28 if role == 'primary' else 24 if aspect > 1.5 else 22
        item['text_scale'], item['text_pos'] = size*unit, (0, -8*unit)
        item.setTransparency(TransparencyAttrib.MAlpha)
        panel.garage_roles[len(panel.buttons)-1] = role
        return item

    image('backgrounds/garage-coastal-v2.png', 0, 0, width, 941, crop=True)
    if car:
        wide = min(462., width*.32)
        vehicle = panel.vehicle_view.base.workspace_vehicle
        panel.vehicle_view.show(panel.content, box(margin+wide+18, 205, width-2*margin-wide-18, 541),
                                vehicle, studio=True)
        panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        panel.vehicle_view.highlight(None)
        name = next(item.name for item in garage_cars(vehicle) if item.design_id == vehicle.design_id)
        fill(width-197, 126, 2, 64, WHITE, 0)
        label('当前车辆', width-margin, 149, 19, WHITE, right=True)
        label(name, width-margin, 184, 26, WHITE, bold=True, right=True)
    fill(0, 0, width, 74, (.04, .055, .075, .78), 0)
    fill(0, 860, width, 81, (.04, .055, .075, .86), 0)
    brand = label('COASTAL DRIVE', width*.037, 50, 34 if aspect > 1.5 else 28, WHITE, bold=True)
    brand['font'] = panel.garage_display_font
    # 页名与车库导航占同一中栏；4:3不再把品牌、副标题挤在一行。
    button('赛事', width*.41-60, 12, 120, 50, 'board', role='tab-active' if title == '生涯赛事' else 'tab')
    button('海岸车库' if title == '生涯赛事' else title, width*.55-85, 12, 170, 50,
           'garage' if title == '生涯赛事' else 'board', role='tab' if title == '生涯赛事' else 'tab-active')
    fill(width*(.41 if title == '生涯赛事' else .55)-(60 if title == '生涯赛事' else 85),
         59, 120 if title == '生涯赛事' else 170, 4, ORANGE, 0)
    if aspect > 1.5:
        label(f'★  {progress.stars} / 18 星', width-350, 49, 23, WHITE)
        label(f'{progress.credits} 积分', width-55, 49, 23, WHITE, right=True)
    else:
        label(f'★ {progress.stars} / 18 星', width-35, 30, 18, WHITE, right=True)
        label(f'{progress.credits} 积分', width-35, 58, 18, WHITE, right=True)
    return width, margin, fill, label, image, button


def board(panel, progress):
    width, left, fill, label, image, button = canvas(panel, progress, '生涯赛事')
    span = width-2*left
    fill(left, 122, span, 706)
    label('生涯赛事', left+24, 187, 45, bold=True)
    label('提高星级，解锁下一段海岸旅程。', left+25, 226, 21, GRAY)
    cell = (span-48)/3
    for i, title in enumerate(CHAPTERS):
        x, locked = left+24+i*cell, progress.stars < (0, 5, 9)[i]
        fill(x, 247, 52, 38, (.67, .69, .73, 1) if locked else ORANGE)
        label(f'{i+1:02}', x+10, 275, 24, WHITE, bold=True)
        label(title, x+65, 274, 23, GRAY if locked else INK, bold=True)
        if i:
            label(f'{(0, 5, 9)[i]}星解锁', x+65, 300, 17, GRAY)
    gap, card_w = 18, (span-48-36)/3
    next_event = progress.recommended()
    for index, event in enumerate(EVENTS):
        x, y = left+24+(index % 3)*(card_w+gap), 320+(index//3)*246
        edge = fill(x-3, y-3, card_w+6, 238, (0, 0, 0, 0))
        button('', x, y, card_w, 232, 'brief', event.id, role='event-card')
        panel.card_edges[len(panel.buttons)-1] = edge
        unlocked = progress.available(event)
        image('career/'+event.id+'.png', x, y, card_w, 232, crop=True,
              tint=WHITE if unlocked else (.47, .50, .54, 1))
        fill(x, y+146, card_w, 86, DARK, 0)
        fill(x+12, y+12, min(168, card_w-24), 29, DARK)
        label(f'{event.chapter+1:02}  {CHAPTERS[event.chapter]}', x+22, y+34, 17, WHITE)
        if event.id == next_event.id:
            fill(x+card_w-70, y+12, 58, 29, ORANGE)
            label('推荐', x+card_w-62, y+34, 17, WHITE, bold=True)
        label(event.name, x+17, y+181, 28 if width > 1400 else 25, WHITE, bold=True)
        label(f'{event.distance:g} 米', x+17, y+215, 21, WHITE)
        stars = progress.records.get(event.id, {'stars': 0})['stars']
        label('★'*stars+'☆'*(3-stars) if unlocked else f'还需{event.unlock-progress.stars}星',
              x+card_w-16, y+215, 22, GOLD if unlocked else WHITE, right=True)
    if progress.notice:
        label(progress.notice, left+24, 849, 16, WHITE, wrap=span-48)
    label('Enter  查看赛事    Esc  主菜单', left, 911, 20, WHITE)
    button('车库改装', width-left-440, 877, 180, 52, 'garage', role='secondary')
    button('继续：'+next_event.name, width-left-240, 877, 240, 52, 'brief', next_event.id,
           role='primary', primary=True)
    panel.select(panel.primary)


def brief(panel, progress, event):
    width, left, fill, label, image, button = canvas(panel, progress, '赛前简报')
    span, gap = width-2*left, 22
    right_w = span*.33
    photo_w, right = span-right_w-gap, width-left-right_w
    image('career/'+event.id+'.png', left, 122, photo_w, 550, crop=True)
    fill(left, 528, photo_w, 144, DARK, 0)
    label(f'{event.chapter+1:02}  /  {CHAPTERS[event.chapter]}', left+30, 573, 24, ORANGE, bold=True)
    label(event.name, left+30, 639, 52, WHITE, bold=True)
    fill(left, 672, photo_w, 156)
    label('比赛信息', left+26, 718, 29, bold=True)
    label(f'{event.distance:g}米   /   静止起步   /   {event.limit:g}秒时限', left+26, 754, 23, GRAY)
    label(event.tip, left+26, 795, 21 if width > 1400 else 19, GRAY, wrap=photo_w-52)
    fill(right, 122, right_w, 706)
    label('星级目标', right+30, 187, 40, bold=True)
    for index, target in enumerate(event.targets):
        y = 260+index*111
        label('★', right+26, y+12, 48, GOLD)
        label(str(index+1), right+44, y+2, 19, INK, bold=True)
        label(target, right+95, y, 25 if width > 1400 else 23, wrap=right_w-121)
        fill(right+28, y+57, right_w-56, 1, LINE, 0)
    label('奖励', right+30, 603, 34, bold=True)
    label('每提高1星', right+30, 646, 21, GRAY)
    label(f'+{event.reward} 积分', right+right_w-28, 695, 34, ORANGE, bold=True, right=True)
    fill(right+28, 716, right_w-56, 1, LINE, 0)
    stars = progress.records.get(event.id, {'stars': 0})['stars']
    label('最佳成绩', right+30, 751, 20, GRAY)
    label('★'*stars+'☆'*(3-stars), right+right_w-28, 751, 27, GOLD, right=True)
    label('碰撞、复位或驶离赛道\n会结束本场。', right+30, 793, 18, GRAY, wrap=right_w-60)
    label('Esc  返回赛事', left, 911, 21, WHITE)
    button('车库改装', width-left-440, 877, 200, 52, 'garage', role='secondary')
    available = progress.available(event)
    button('开始比赛' if available else f'需要{event.unlock}星', width-left-220, 877, 220, 52,
           'start', event.id, role='primary', primary=True, enabled=available)
    panel.select(panel.primary if available else len(panel.buttons)-2)


def result(panel, progress, race_result, award):
    width, left, fill, label, image, button = canvas(panel, progress, '赛事结算', car=True)
    event = next(event for event in EVENTS if event.id == race_result.event_id)
    wide = min(462., width*.32)
    inner, x = wide-48, left+24
    fill(left, 122, wide, 706)
    label(f'{event.chapter+1:02} / {event.name}', x, 166, 23, ORANGE, bold=True)
    label('赛事完成' if race_result.succeeded else '再试一次', x, 230, 51, bold=True)
    label('★'*race_result.stars+'☆'*(3-race_result.stars), x, 326, 84, GOLD)
    label('完赛用时' if race_result.succeeded else '本场用时', x, 380, 22, GRAY)
    label(f'{race_result.elapsed:.2f} 秒', x, 440, 54, bold=True)
    fill(x, 465, inner, 1, LINE, 0)
    label('本场奖励' if award['saved'] else '奖励尚未保存', x, 502, 23, GRAY)
    label(f'+{award["credits"]} 积分', x, 564, 48, ORANGE, bold=True)
    label(f'{progress.stars} / 18 星', x, 612, 26, bold=True)
    fill(x, 630, inner, 12, (.82, .83, .85, 1))
    if progress.stars:
        fill(x, 630, inner*progress.stars/18, 12, ORANGE)
    fill(x, 665, inner, 1, LINE, 0)
    # 解锁项全部保留在面板内；车型/零件优先带真实资产缩略图，赛事合并一行。
    cars = [car for car in GARAGE_CARS if car.design_id in award['vehicles']]
    parts = [name for name in award['unlocked'] if name.startswith('零件：')]
    events = [name for name in award['unlocked'] if not name.startswith(('零件：', '新车：'))]
    heading = '保存失败' if not award['saved'] else '新解锁' if award['unlocked'] else '本场记录'
    if award['saved'] and events and (cars or parts):
        heading += ' · '+'、'.join(events)
    label(heading, x, 696, 17 if events and (cars or parts) else 23, bold=True)
    if not award['saved']:
        message = progress.notice[:40]+'…' if len(progress.notice) > 40 else progress.notice
        label(message, x, 732, 18, GRAY, wrap=inner)
        button('重试保存奖励', x, 780, inner, 38, 'save', role='primary', primary=True)
    elif cars or parts or events:
        # 按新车、零件分成相邻两行，多个解锁仍完整显示名称。
        y = 708
        if cars:
            car_height = 64 if len(cars) > 2 else 50
            fill(x, y, inner, car_height, (.91, .92, .94, .85))
            image('garage-v2/car-'+cars[-1].design_id+'.png', x+4, y+2, 85, 46)
            title = label(cars[-1].name+' · 新车', x+103, y+23, 21, bold=True)
            title.setScale(min(21., (inner-113)/title.textNode.getWidth())*2/941)
            if len(cars) > 1:
                label('同时解锁：'+'、'.join(car.name for car in cars[:-1]),
                      x+103, y+44, 16, GRAY, wrap=inner-108)
            y += car_height+7
        if parts:
            fill(x, y, inner, 46, (.91, .92, .94, .85))
            part = next(part for part in PARTS if part.name == parts[0][3:])
            image('garage-v2/'+PART_IMAGES[part.topic]+'.png', x+18, y+4, 38, 38)
            label('、'.join(name[3:] for name in parts), x+103, y+28, 17, wrap=inner-108)
        if events and not (cars or parts):
            label('赛事：'+'、'.join(events), x, 742, 21, GRAY, wrap=inner)
    else:
        detail = race_result.reason or ('星级未提高，本场不重复发放积分。' if award['credits'] == 0 else '完成赛事。')
        detail = detail.rstrip('。')
        if event.kind == 'parking' and race_result.parking_error is not None:
            detail = f'距停车中心 {race_result.parking_error:.1f} 米\n'+detail
        elif event.kind == 'slalom':
            detail = f'通过 {sum(race_result.passed)} / 5 道门\n'+detail
        label(detail, x, 742, 21, GRAY, wrap=inner)
    next_event = progress.recommended()
    strip_w = min(462, width-left-wide-40)
    strip_x = width-left-strip_w
    fill(strip_x, 746, strip_w, 82, DARK)
    image('career/'+next_event.id+'.png', strip_x+12, 756, 96, 62, crop=True)
    label('下一场', strip_x+126, 777, 17, WHITE)
    label(next_event.name, strip_x+126, 811, 26, WHITE, bold=True)
    label('Enter  确认    Esc  返回赛事', left, 911, 20, WHITE)
    primary_w, secondary_w, gap = 240, 190, 18
    start_x = width-left-primary_w-2*secondary_w-2*gap
    # 4:3底栏收短提示，三个操作始终在同一行而不相互覆盖。
    if width < 1400:
        panel.labels[-1].setText('Esc  返回赛事')
        primary_w, secondary_w, gap = 210, 170, 14
        start_x = width-left-primary_w-2*secondary_w-2*gap
    button('重试本场', start_x, 877, secondary_w, 52, 'start', event.id, role='secondary')
    button('查看新车' if award['vehicles'] else '车库改装', start_x+secondary_w+gap, 877,
           secondary_w, 52, 'garage-new' if award['vehicles'] else 'garage',
           award['vehicles'][-1] if award['vehicles'] else None, role='secondary')
    button('继续赛事', width-left-primary_w, 877, primary_w, 52, 'board',
           role='primary' if award['saved'] else 'secondary', primary=award['saved'])
    panel.select(panel.primary)


def pause(panel, progress, event):
    width, left, fill, label, _image, button = canvas(panel, progress, '比赛暂停', car=True)
    wide = min(462., width*.32)
    x, inner = left+24, wide-48
    fill(left, 122, wide, 706)
    label('正在比赛', x, 176, 23, ORANGE, bold=True)
    label(event.name, x, 215, 26, GRAY)
    label('比赛已暂停', x, 290, 49, bold=True)
    label('当前进度已保留', x, 333, 23, GRAY)
    for index, (name, command) in enumerate((('继续驾驶', 'resume'), ('重新开始', 'retry'), ('退出本场', 'board'))):
        fill(x-1, 373+index*92-1, inner+2, 72, LINE)
        button(name, x, 373+index*92, inner, 70, command,
               role='primary' if index == 0 else 'plain', primary=index == 0)
    fill(x, 663, inner, 1, LINE, 0)
    label('重新开始将从起点发车。\n未完成本场不会获得星级或积分。', x, 710, 22, GRAY, wrap=inner)
    strip_w = min(360, width-left-wide-40)
    fill(width-left-strip_w, 744, strip_w, 84, DARK)
    fill(width-left-strip_w, 744, 6, 84, ORANGE, 0)
    label(event.name, width-left-strip_w+24, 782, 25, WHITE, bold=True)
    label(f'{event.distance:g} 米 · {event.limit:g}秒时限', width-left-strip_w+24, 813, 19, WHITE)
    label('Enter  确认    Esc  继续驾驶', left, 911, 21, WHITE)
    panel.select(panel.primary)
