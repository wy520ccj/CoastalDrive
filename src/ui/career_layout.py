"""生涯赛事板、简报和结算的构图。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import LineSegs, TextNode, TextureStage, TransparencyAttrib

from career import CHAPTERS, EVENTS, PARTS
from career_courses import COURSES, CareerCourse
from career_garage import GARAGE_CARS, garage_cars
from highway_curve import HighwayCurve
from ui import theme
from ui.career_events import BOARD_EVENTS, ClubEvent
from ui.garage_layout import INK, ORANGE, WHITE
from ui.lab_widgets import rounded_panel

GOLD = theme.GOLD
DARK = theme.CHARCOAL
PAPER = theme.GLASS_LIGHT
LINE = theme.HAIRLINE
HISTORICAL_PART_IMAGES = {'tires': 'tire', 'brakes': 'brake', 'power': 'power-part', 'suspension': 'suspension-part'}


def vehicle_box(aspect):
    """生涯车辆展示区；加载准备与实际页面使用同一视口。"""
    width, unit = 941*aspect, 2/941
    margin, wide = width*.031, min(462., width*.32)
    return ((margin+wide+18-width/2)*unit, (width-margin-width/2)*unit,
            1-(205+541)*unit, 1-205*unit)


def canvas(panel, progress, title, *, car=False, budget=None, chrome=True, season=False):
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

    def label(text, x, y, size=22, color=None, *, bold=False, right=False, wrap=None):
        fg = (theme.TEXT_LIGHT if season else INK) if color is None else color
        item = panel.label(text, *point(x, y), size*unit, fg,
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
            fill(x-1, y-1, w+2, h+2, theme.SLATE_BORDER, 7)
        px, pz = point(x+w/2, y+h/2)
        item = panel.button(text, px, pz, w*unit, h*unit, command, value,
                            primary=primary, enabled=enabled, radius=6*unit)
        item['text_font'] = panel.font if role == 'primary' else panel.garage_font
        size = 21 if h < 44 else 26 if role == 'primary' else 22 if aspect > 1.5 else 20
        item['text_scale'], item['text_pos'] = size*unit, (0, -7*unit)
        item.setTransparency(TransparencyAttrib.MAlpha)
        panel.garage_roles[len(panel.buttons)-1] = role
        return item

    if season:
        fill(0, 0, width, 941, theme.SLATE_BG, 0)
        fill(0, 0, width, 68, theme.SLATE_BAR, 0)
        fill(0, 68, width, 1.5, theme.SLATE_BORDER, 0)
        fill(0, 848, width, 93, theme.SLATE_BAR, 0)
        fill(0, 847, width, 1.5, theme.SLATE_BORDER, 0)
        brand = label('COASTAL DRIVE', margin, 44, 26, theme.TEXT_LIGHT, bold=True)
        brand['font'] = panel.garage_display_font
        fill(margin+252, 20, 2, 28, ORANGE, 1)
        label(title, margin+272, 43, 26, theme.TEXT_LIGHT, bold=True)
        label(f'★  {progress.stars} / 18 星', width-margin, 43, 24, theme.GOLD, bold=True, right=True)
        return width, margin, fill, label, image, button

    image('backgrounds/garage-coastal-v2.png', 0, 0, width, 941, crop=True)
    if car:
        vehicle = panel.vehicle_view.base.workspace_vehicle
        panel.vehicle_view.show(panel.content, vehicle_box(aspect),
                                vehicle, studio=True)
        panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        panel.vehicle_view.highlight(None)
        name = next(item.name for item in garage_cars(vehicle) if item.design_id == vehicle.design_id)
        badge_w = 300
        bx = width-margin-badge_w
        fill(bx-1, 113, badge_w+2, 82, theme.SLATE_BORDER, 11)
        fill(bx, 114, badge_w, 80, theme.SLATE_GLASS, 10)
        fill(bx+badge_w-4, 126, 4, 56, ORANGE, 2)
        label('当前车辆', width-margin-18, 144, 16, theme.TEXT_SUB, right=True)
        label(name, width-margin-18, 180, 25, theme.TEXT_LIGHT, bold=True, right=True)
    if chrome:
        fill(0, 0, width, 74, theme.SLATE_BAR, 0)
        fill(0, 74, width, 1.5, theme.SLATE_BORDER, 0)
        fill(0, 860, width, 81, theme.SLATE_BAR, 0)
        fill(0, 859, width, 1.5, theme.SLATE_BORDER, 0)
    if budget is not None:
        label(title, margin, 50, 32 if aspect > 1.5 else 26, theme.TEXT_LIGHT, bold=True)
        panel.challenge_readouts['budget'] = label('', width-margin, 49 if aspect > 1.5 else 29,
                                                   22 if aspect > 1.5 else 18, theme.TEXT_LIGHT, right=True)
        return width, margin, fill, label, image, button
    brand = label('COASTAL DRIVE', width*.031, 49, 32 if aspect > 1.5 else 26, theme.TEXT_LIGHT, bold=True)
    brand['font'] = panel.garage_display_font
    button('赛事', width*.41-60, 12, 120, 50, 'board', role='tab-active' if title == '生涯赛事' else 'tab')
    button('海岸车库' if title == '生涯赛事' else title, width*.55-85, 12, 170, 50,
           'garage' if title == '生涯赛事' else 'board', role='tab' if title == '生涯赛事' else 'tab-active')
    fill(width*(.41 if title == '生涯赛事' else .55)-(60 if title == '生涯赛事' else 85)+14,
         62, (120 if title == '生涯赛事' else 170)-28, 3, ORANGE, 1.5)
    label(f'★  {progress.stars} / 18 星', width-margin, 48, 22 if aspect > 1.5 else 18, theme.GOLD, bold=True, right=True)
    return width, margin, fill, label, image, button


def board(panel, progress, *, chapter=None, event=None):
    from challenge_catalog import ROAD_CHALLENGES

    recommended = progress.recommended()
    if chapter is None:
        chapter = (event or recommended).chapter
    events = tuple(item for item in BOARD_EVENTS.values() if item.chapter == chapter)
    event = event or (recommended if recommended in events else events[0])
    width, left, fill, label, image, button = canvas(panel, progress, '生涯赛季', season=True)
    listing = width*.385
    right, preview_width = left+listing+28, width-2*left-listing-28

    label('第一季 · 海岸生涯', left, 132, 38, theme.TEXT_LIGHT, bold=True)
    label('按章节推进赛事，赢取星级解锁俱乐部与综合杯', left, 166, 17, theme.TEXT_SUB)

    # 章节胶囊切换栏（清晰高亮无压边）。
    tab_gap = 8
    tab_width = (listing-tab_gap*(len(CHAPTERS)-1))/len(CHAPTERS)
    for index, title in enumerate(CHAPTERS):
        x = left+index*(tab_width+tab_gap)
        button(title, x, 192, tab_width, 52, 'board-chapter', index,
               role='season-tab-active' if index == chapter else 'season-tab')
        if index == chapter:
            fill(x+14, 240, tab_width-28, 3.5, ORANGE, 2)

    rows = {}
    stars = progress.stars
    for index, item in enumerate(events):
        y = 266+index*94
        fill(left-1, y-1, listing+2, 82+2, theme.SLATE_BORDER, 9)
        fill(left, y, listing, 82, theme.SLATE_CARD, 8)
        background = fill(left, y, listing, 82, theme.SLATE_CARD_HI, 8)
        edge = fill(left, y+12, 4.5, 58, ORANGE, 2)
        button('', left, y, listing, 82, 'brief', item.id, role='event-card')
        rows[item.id] = background, edge, len(panel.buttons)-1
        locked = stars < item.unlock
        label(item.name, left+22, y+38, 26, theme.TEXT_LOCKED if locked else theme.TEXT_LIGHT, bold=True)
        sub_text = f'{item.distance:g} m' if getattr(item, 'distance', None) else item.goal
        label(sub_text, left+22, y+65, 16, theme.TEXT_LOCKED if locked else theme.TEXT_SUB)
        status_color = theme.TEXT_SUB
        if locked:
            status = f'需 {item.unlock} 星'
            status_color = theme.TEXT_LOCKED
        elif isinstance(item, ClubEvent):
            record = item.best(panel.vehicle_view.base.session)
            if record:
                medal = record['medal'] or '完赛'
                status = f'{medal} · {record["seconds"]:.2f} s'
                status_color = {'金': theme.GOLD, '银': theme.SILVER, '铜': theme.BRONZE}.get(medal, theme.SEA)
            else:
                status = '待挑战'
        else:
            status = '待挑战'
            record = progress.course_record(item)
            if record is not None:
                medal = ('', '铜', '银', '金')[record['stars']]
                historic = '历史 · ' if item.id not in progress.budget_records else ''
                status = f'{historic}{medal} · {record["seconds"]:.2f} s'
                status_color = (theme.TEXT_SUB, theme.BRONZE, theme.SILVER, theme.GOLD)[record['stars']]
        label(status, left+listing-22, y+48, 21, status_color, bold=not locked, right=True)

    if progress.notice:
        label(progress.notice, left, 804, 17, (1, .84, .64, 1), wrap=listing)

    # 右侧统一深海展示卡片：高清赛道图 + 悬浮信息区 + 路线轨迹。
    fill(right-1.5, 96-1.5, preview_width+3, 728+3, theme.SLATE_BORDER, 13)
    fill(right, 96, preview_width, 728, theme.SLATE_CARD, 12)
    photo_name = event.photo if isinstance(event, ClubEvent) else event.id+'.png'
    photo = image('career/'+photo_name, right, 96, preview_width, 412, crop=True)
    fill(right, 507, preview_width, 2, theme.SLATE_BORDER, 0)

    title = label('', right+28, 566, 38, theme.TEXT_LIGHT, bold=True)
    goal = label('', right+28, 606, 21, theme.TEXT_SUB, wrap=preview_width-56)
    route_root = panel.content.attachNewNode('career-board-route')
    start_label = label('起点', right+64, 718, 18, theme.TEXT_SUB)
    end_label = label('', right+preview_width-64, 718, 18, theme.TEXT_SUB, right=True)
    fill(right+28, 742, preview_width-56, 1.5, theme.SLATE_BORDER, 0)
    car = label('', right+28, 788, 21, theme.TEXT_LIGHT, bold=True)
    requirement = label('', right+preview_width-28, 788, 20, theme.GOLD, bold=True, right=True)

    button('返回', left, 868, 108, 54, 'exit', role='footer')
    button('车库', left+122, 868, 108, 54, 'garage', role='footer')
    button('赛段追时' if stars >= 5 else '追时 · 需 5 星', left+246, 868, 198, 54,
           'chase-menu', role='footer', enabled=stars >= 5)
    button('自选车综合杯' if stars >= 9 else '综合杯 · 需 9 星', left+456, 868, 214, 54,
           'cup-menu', role='footer', enabled=stars >= 9)
    details = button('进入简报', width-left-240, 865, 240, 58, 'brief', event.id,
                     role='primary', primary=True)

    def preview(item):
        panel.board_event = item
        for event_id, (background, edge, _) in rows.items():
            if event_id == item.id:
                background.setColor(*theme.ORANGE_TINT)
                background.show()
                edge.show()
            else:
                background.hide()
                edge.hide()
        photo['frameTexture'] = panel.photos[item.id]
        title.setText(item.name)
        goal.setText(item.goal)
        spec = ROAD_CHALLENGES[item.id]
        car.setText('指定车辆 · '+next(car.name for car in GARAGE_CARS if car.design_id == spec.design_id))
        if stars < item.unlock:
            condition = f'{item.unlock} 星解锁'
        elif spec.assessment == 'lower':
            condition = '  /  '.join(f'{medal} {value:g} m' for medal, value in
                                      zip(('铜', '银', '金'), spec.metric_limits, strict=True))
        elif spec.assessment == 'career-slalom':
            condition = f'{len(item.gates)} 道门'
        else:
            condition = f'{item.distance:g} m  ·  预算 {spec.budget}'
        requirement.setText(condition)
        details['extraArgs'] = ['brief', item.id]
        if item.shape in COURSES or isinstance(item, ClubEvent):
            start_label.hide()
            end_label.hide()
        else:
            start_label.show()
            end_label.show()
            end_label.setText('停车区' if item.kind == 'parking' else '终点')
        board_route(route_root, item, width, right, preview_width)

    panel.board_preview = preview
    preview(event)
    panel.select(rows[event.id][2])


def board_route(root, event, width, left, span, *, center=676):
    """用关卡几何绘制预览路径。"""
    root.getChildren().detach()
    points = ()
    if event.shape in COURSES:
        points = CareerCourse(event.shape, event.seed).points[::3]
    elif isinstance(event, ClubEvent):
        curve = HighwayCurve(event.seed, hills=True)
        points = tuple(curve.sample(8+distance) for distance in range(0, int(event.distance)+1, 12))
    if points:
        min_x, max_x = min(point.y for point in points), max(point.y for point in points)
        min_y, max_y = min(point.x for point in points), max(point.x for point in points)
        scale = min((span-120)/max(1, max_x-min_x), 66/max(1, max_y-min_y))
        positions = [(left+span/2+(point.y-(min_x+max_x)/2)*scale,
                      center+(point.x-(min_y+max_y)/2)*scale) for point in points]
    else:
        positions = [(left+84, center), (left+span-84, center)]
    unit = 2/941
    line = LineSegs('career-board-outline')
    line.setThickness(3.5)
    line.setColor(*theme.SEA)
    for index, (x, y) in enumerate(positions):
        point = ((x-width/2)*unit, 0, 1-y*unit)
        line.moveTo(*point) if index == 0 else line.drawTo(*point)
    root.attachNewNode(line.create())
    markers = LineSegs('career-board-endpoints')
    markers.setColor(*ORANGE)
    markers.setThickness(8)
    for x, y in (positions[0], positions[-1]):
        markers.moveTo((x-width/2-3.5)*unit, 0, 1-y*unit)
        markers.drawTo((x-width/2+3.5)*unit, 0, 1-y*unit)
    root.attachNewNode(markers.create())


def brief(panel, progress, event):
    from challenge_catalog import ROAD_CHALLENGES

    spec = ROAD_CHALLENGES[event.id]
    club = isinstance(event, ClubEvent)
    width, left, fill, label, image, button = canvas(panel, progress, '赛前简报', season=True)
    span = width-2*left
    photo_width = span*.59
    right = left+photo_width+28
    columns = width-left-right

    # 左侧大幅赛道卡 + 路线与提示条。
    fill(left-1.5, 96-1.5, photo_width+3, 726+3, theme.SLATE_BORDER, 13)
    fill(left, 96, photo_width, 726, theme.SLATE_CARD, 12)
    image('career/'+(event.photo if club else event.id+'.png'), left, 96, photo_width, 520, crop=True)
    fill(left, 616, photo_width, 2, theme.SLATE_BORDER, 0)
    route = panel.content.attachNewNode('career-brief-route')
    board_route(route, event, width, left, photo_width, center=686)
    if event.shape not in COURSES and not club:
        label('起点', left+64, 736, 19, theme.TEXT_SUB)
    end = '停车区' if not club and event.kind == 'parking' else '终点'
    label(f'{end}  {event.distance:g} m', left+photo_width-28, 736, 19, theme.TEXT_SUB, right=True)
    label(event.tip, left+28, 788, 19, theme.TEXT_LIGHT, wrap=photo_width-56)

    # 右侧统一深海简报信息卡。
    fill(right-1.5, 96-1.5, columns+3, 726+3, theme.SLATE_BORDER, 13)
    fill(right, 96, columns, 726, theme.SLATE_CARD, 12)
    pad = 28
    rx, rw = right+pad, columns-2*pad
    label(event.name, rx, 158, 42, theme.TEXT_LIGHT, bold=True)
    label(event.goal, rx, 204, 21, theme.TEXT_SUB, wrap=rw)
    car = next(car for car in GARAGE_CARS if car.design_id == spec.design_id)
    fill(rx, 246, rw, 54, theme.SLATE_BG, 8)
    label('指定车辆', rx+16, 281, 18, theme.TEXT_SUB)
    label(car.name, rx+rw-16, 281, 21, theme.TEXT_LIGHT, bold=True, right=True)

    if spec.assessment == 'road':
        targets = [f'≤ {target.seconds:g} s   ·   ≤ {target.consumption:g} L/100km' for target in spec.targets]
    elif spec.assessment == 'lower':
        targets = [f'≤ {limit:g} m' for limit in spec.metric_limits]
    else:
        targets = event.targets
    medal_colors = (theme.BRONZE, theme.SILVER, theme.GOLD)
    for index, (medal, target) in enumerate(zip(('铜牌', '银牌', '金牌'), targets, strict=True)):
        y = 326+index*74
        fill(rx, y, rw, 60, theme.MIST, 8)
        fill(rx, y+12, 4, 36, medal_colors[index], 2)
        label(medal, rx+18, y+38, 22, medal_colors[index], bold=True)
        label(target, rx+rw-16, y+38, 21 if width > 1400 else 19, theme.INK, right=True)

    label(event.rules if club else '碰撞、复位或驶离赛道会结束本场。', rx, 594, 19, theme.TEXT_SUB, wrap=rw)
    fill(rx, 646, rw, 1.5, theme.SLATE_BORDER, 0)
    label('本场改装预算', rx, 704, 19, theme.TEXT_SUB)
    label(f'{spec.budget}', rx+rw, 706, 30, theme.GOLD, bold=True, right=True)
    if club:
        record = event.best(panel.vehicle_view.base.session) if progress.available(event) else None
    else:
        record = progress.course_record(event)
    if record is not None:
        medal = (record['medal'] or '完赛') if club else ('', '铜', '银', '金')[record['stars']]
        title = '历史成绩' if not club and event.id not in progress.budget_records else '个人最佳'
        label(f'{title} · {medal} / {record["seconds"]:.2f} s', rx, 764, 19, theme.SEA, bold=True)

    available = progress.available(event)
    button('返回赛事', left, 868, 156, 54, 'board', role='footer')
    button('调整方案', width-left-456, 866, 200, 56, 'start', event.id,
           role='secondary', enabled=available)
    button('原车发车' if available else f'需要 {event.unlock} 星', width-left-240, 866, 240, 56,
           'start-stock', event.id, role='primary', primary=True, enabled=available)
    panel.select(panel.primary if available else 0)


def result(panel, progress, race_result, award):
    width, left, fill, label, image, button = canvas(panel, progress, '赛事结算', car=True)
    event = next(event for event in EVENTS if event.id == race_result.event_id)
    wide = min(462., width*.32)
    inner, x = wide-48, left+24
    fill(left-1, 113, wide+2, 718, theme.SLATE_BORDER, 13)
    fill(left, 114, wide, 716, theme.SLATE_GLASS, 12)
    label(f'{event.chapter+1:02} / {event.name}', x, 160, 21, ORANGE, bold=True)
    label('赛事完成' if race_result.succeeded else '再试一次', x, 222, 46, theme.TEXT_LIGHT, bold=True)
    label('★'*race_result.stars+'☆'*(3-race_result.stars), x, 316, 78, GOLD)
    label('完赛用时' if race_result.succeeded else '本场用时', x, 372, 20, theme.TEXT_SUB)
    label(f'{race_result.elapsed:.2f} 秒', x, 432, 50, theme.TEXT_LIGHT, bold=True)
    fill(x, 458, inner, 1, theme.SLATE_BORDER, 0)
    label('本场奖励' if award['saved'] else '奖励尚未保存', x, 496, 20, theme.TEXT_SUB)
    label(f'+{award["credits"]} 积分', x, 554, 44, ORANGE, bold=True)
    label(f'{progress.stars} / 18 星', x, 602, 24, theme.GOLD, bold=True)
    fill(x, 620, inner, 10, theme.MIST, 5)
    if progress.stars:
        fill(x, 620, inner*progress.stars/18, 10, ORANGE, 5)
    fill(x, 654, inner, 1, theme.SLATE_BORDER, 0)
    cars = [car for car in GARAGE_CARS if car.design_id in award['vehicles']]
    parts = [name for name in award['unlocked'] if name.startswith('零件：')]
    events = [name for name in award['unlocked'] if not name.startswith(('零件：', '新车：'))]
    heading = '保存失败' if not award['saved'] else '新解锁' if award['unlocked'] else '本场记录'
    if award['saved'] and events and (cars or parts):
        heading += ' · '+'、'.join(events)
    label(heading, x, 688, 17 if events and (cars or parts) else 22, theme.TEXT_LIGHT, bold=True)
    if not award['saved']:
        message = progress.notice[:40]+'…' if len(progress.notice) > 40 else progress.notice
        label(message, x, 724, 17, theme.TEXT_SUB, wrap=inner)
        button('重试保存奖励', x, 774, inner, 40, 'save', role='primary', primary=True)
    elif cars or parts or events:
        y = 702
        if cars:
            car_height = 64 if len(cars) > 2 else 50
            fill(x, y, inner, car_height, theme.SLATE_CARD, 8)
            image('garage-v2/car-'+cars[-1].design_id+'.png', x+6, y+2, 85, 46)
            title = label(cars[-1].name+' · 新车', x+103, y+23, 20, theme.TEXT_LIGHT, bold=True)
            title.setScale(min(20., (inner-113)/title.textNode.getWidth())*2/941)
            if len(cars) > 1:
                label('同时解锁：'+'、'.join(car.name for car in cars[:-1]),
                      x+103, y+44, 15, theme.TEXT_SUB, wrap=inner-108)
            y += car_height+7
        if parts:
            fill(x, y, inner, 46, theme.SLATE_CARD, 8)
            part = next(part for part in PARTS if part.name == parts[0][3:])
            image('garage-v2/'+HISTORICAL_PART_IMAGES[part.topic]+'.png', x+18, y+4, 38, 38)
            label('、'.join(name[3:] for name in parts), x+103, y+28, 17, theme.TEXT_LIGHT, wrap=inner-108)
        if events and not (cars or parts):
            label('赛事：'+'、'.join(events), x, 734, 20, theme.TEXT_SUB, wrap=inner)
    else:
        detail = race_result.reason or ('星级未提高，本场不重复发放积分。' if award['credits'] == 0 else '完成赛事。')
        detail = detail.rstrip('。')
        if event.kind == 'parking' and race_result.parking_error is not None:
            detail = f'距停车中心 {race_result.parking_error:.1f} 米\n'+detail
        elif event.kind == 'slalom':
            detail = f'通过 {sum(race_result.passed)} / 5 道门\n'+detail
        label(detail, x, 734, 20, theme.TEXT_SUB, wrap=inner)
    next_event = progress.recommended()
    strip_w = min(462, width-left-wide-40)
    strip_x = width-left-strip_w
    fill(strip_x-1, 745, strip_w+2, 84, theme.SLATE_BORDER, 11)
    fill(strip_x, 746, strip_w, 82, theme.SLATE_GLASS, 10)
    image('career/'+next_event.id+'.png', strip_x+12, 756, 96, 62, crop=True)
    label('下一场', strip_x+126, 777, 16, theme.TEXT_SUB)
    label(next_event.name, strip_x+126, 811, 25, theme.TEXT_LIGHT, bold=True)
    label('Enter  确认    Esc  返回赛事', left, 910, 19, theme.TEXT_SUB)
    primary_w, secondary_w, gap = 240, 190, 18
    start_x = width-left-primary_w-2*secondary_w-2*gap
    if width < 1400:
        panel.labels[-1].setText('Esc  返回赛事')
        primary_w, secondary_w, gap = 210, 170, 14
        start_x = width-left-primary_w-2*secondary_w-2*gap
    button('重试本场', start_x, 876, secondary_w, 52, 'start', event.id, role='secondary')
    button('查看新车' if award['vehicles'] else '车库改装', start_x+secondary_w+gap, 876,
           secondary_w, 52, 'garage-new' if award['vehicles'] else 'garage',
           award['vehicles'][-1] if award['vehicles'] else None, role='secondary')
    button('继续赛事', width-left-primary_w, 876, primary_w, 52, 'board',
           role='primary' if award['saved'] else 'secondary', primary=award['saved'])
    panel.select(panel.primary)


def pause(panel, progress, event):
    width, left, fill, label, _image, button = canvas(panel, progress, '比赛暂停', car=True)
    wide = min(462., width*.32)
    x, inner = left+28, wide-56
    fill(left-1, 113, wide+2, 718, theme.SLATE_BORDER, 13)
    fill(left, 114, wide, 716, theme.SLATE_GLASS, 12)
    fill(x, 146, 4, 32, ORANGE, 2)
    label('正在比赛', x+16, 172, 22, ORANGE, bold=True)
    label(event.name, x, 212, 25, theme.TEXT_SUB)
    label('比赛已暂停', x, 286, 44, theme.TEXT_LIGHT, bold=True)
    label('当前进度已保留', x, 326, 20, theme.TEXT_SUB)
    for index, (name, command) in enumerate((('继续驾驶', 'resume'), ('重新开始', 'retry'), ('退出本场', 'board'))):
        if index > 0:
            fill(x-1, 368+index*90-1, inner+2, 72, theme.SLATE_BORDER, 7)
        button(name, x, 368+index*90, inner, 70, command,
               role='primary' if index == 0 else 'secondary', primary=index == 0)
    fill(x, 654, inner, 1, theme.SLATE_BORDER, 0)
    label('重新开始将从起点发车。\n未完成本场不会获得星级或积分。', x, 702, 20, theme.TEXT_SUB, wrap=inner)
    strip_w = min(360, width-left-wide-40)
    fill(width-left-strip_w-1, 743, strip_w+2, 86, theme.SLATE_BORDER, 11)
    fill(width-left-strip_w, 744, strip_w, 84, theme.SLATE_GLASS, 10)
    fill(width-left-strip_w, 744, 5, 84, ORANGE, 2)
    label(event.name, width-left-strip_w+24, 782, 24, theme.TEXT_LIGHT, bold=True)
    label(f'{event.distance:g} 米 · {event.limit:g} 秒时限', width-left-strip_w+24, 813, 18, theme.TEXT_SUB)
    label('Enter  确认    Esc  继续驾驶', left, 910, 19, theme.TEXT_SUB)
    panel.select(panel.primary)
