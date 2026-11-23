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
from ui.garage_layout import GRAY, INK, ORANGE, WHITE
from ui.lab_widgets import rounded_panel

GOLD = (1, .73, .25, 1)
DARK = (.04, .055, .075, .88)
PAPER = (.98, .98, .99, .96)
LINE = (.80, .82, .85, 1)
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

    if season:
        fill(0, 0, width, 941, (.966, .961, .949, 1), 0)
        fill(0, 0, width, 68, (.055, .088, .132, 1), 0)
        fill(0, 848, width, 93, (.055, .088, .132, 1), 0)
        brand = label('COASTAL DRIVE', margin, 44, 28, WHITE, bold=True)
        brand['font'] = panel.garage_display_font
        fill(margin+260, 19, 1, 31, WHITE, 0)
        label(title, margin+285, 44, 30, WHITE, bold=True)
        label(f'{progress.stars} / 18 星', width-margin, 44, 26, WHITE, right=True)
        return width, margin, fill, label, image, button

    image('backgrounds/garage-coastal-v2.png', 0, 0, width, 941, crop=True)
    if car:
        vehicle = panel.vehicle_view.base.workspace_vehicle
        panel.vehicle_view.show(panel.content, vehicle_box(aspect),
                                vehicle, studio=True)
        panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        panel.vehicle_view.highlight(None)
        name = next(item.name for item in garage_cars(vehicle) if item.design_id == vehicle.design_id)
        fill(width-197, 126, 2, 64, WHITE, 0)
        label('当前车辆', width-margin, 149, 19, WHITE, right=True)
        label(name, width-margin, 184, 26, WHITE, bold=True, right=True)
    if chrome:
        fill(0, 0, width, 74, (.04, .055, .075, .78), 0)
        fill(0, 860, width, 81, (.04, .055, .075, .86), 0)
    if budget is not None:
        label(title, margin, 50, 32 if aspect > 1.5 else 26, WHITE, bold=True)
        panel.challenge_readouts['budget'] = label('', width-margin, 49 if aspect > 1.5 else 29,
                                                   22 if aspect > 1.5 else 18, WHITE, right=True)
        return width, margin, fill, label, image, button
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
    else:
        label(f'★ {progress.stars} / 18 星', width-35, 30, 18, WHITE, right=True)
    return width, margin, fill, label, image, button


def board(panel, progress, *, chapter=None, event=None):
    from challenge_catalog import ROAD_CHALLENGES

    recommended = progress.recommended()
    if chapter is None:
        chapter = (event or recommended).chapter
    events = tuple(item for item in BOARD_EVENTS.values() if item.chapter == chapter)
    event = event or (recommended if recommended in events else events[0])
    width, left, fill, label, image, button = canvas(panel, progress, '生涯赛季', season=True)
    listing = width*.38
    right, preview_width = left+listing+24, width-2*left-listing-24
    label('海岸生涯', left, 154, 48, bold=True)
    tab_width = listing/len(CHAPTERS)
    for index, title in enumerate(CHAPTERS):
        x = left+index*tab_width
        button(title, x, 198, tab_width, 56, 'board-chapter', index,
               role='setup-active' if index == chapter else 'plain')
        if index == chapter:
            fill(x, 252, tab_width, 5, ORANGE, 0)
    fill(left, 257, listing, 1, LINE, 0)

    rows = {}
    stars = progress.stars
    for index, item in enumerate(events):
        y = 298+index*86
        fill(left, y, listing, 1, LINE, 0)
        background = fill(left, y+1, listing, 85, WHITE, 0)
        edge = fill(left, y+1, 6, 85, ORANGE, 0)
        button('', left, y, listing, 86, 'brief', item.id, role='event-card')
        rows[item.id] = background, edge, len(panel.buttons)-1
        label(item.name, left+20, y+54, 29, bold=True)
        if stars < item.unlock:
            status = f'还需 {item.unlock-stars} 星'
        elif isinstance(item, ClubEvent):
            record = item.best(panel.vehicle_view.base.session)
            status = f'{record["medal"] or "完赛"} · {record["seconds"]:.2f} s' if record else '未完成'
        else:
            status = '未完成'
            record = progress.course_record(item)
            if record is not None:
                medal = ('', '铜', '银', '金')[record['stars']]
                historic = '历史 · ' if item.id not in progress.budget_records else ''
                status = f'{historic}{medal} · {record["seconds"]:.2f} s'
        label(status, left+listing-20, y+54, 23, GRAY, right=True)
    fill(left, 298+len(events)*86, listing, 1, LINE, 0)
    if progress.notice:
        label(progress.notice, left, 795, 18, GRAY, wrap=listing)

    photo_name = event.photo if isinstance(event, ClubEvent) else event.id+'.png'
    photo = image('career/'+photo_name, right, 107, preview_width, 409, crop=True)
    title = label('', right+22, 580, 46, bold=True)
    goal = label('', right+22, 623, 25, wrap=preview_width-44)
    route_root = panel.content.attachNewNode('career-board-route')
    start_label = label('起点', right+58, 724, 21, GRAY)
    end_label = label('', right+preview_width-57, 724, 21, GRAY, right=True)
    fill(right, 749, preview_width, 1, LINE, 0)
    car = label('', right+22, 797, 23, bold=True)
    requirement = label('', width-left-20, 797, 21, GRAY, right=True)
    button('返回', left, 866, 104, 56, 'exit', role='footer')
    button('车库', left+118, 866, 104, 56, 'garage', role='footer')
    button('赛段追时' if stars >= 5 else '追时 · 需 5 星', left+240, 866, 198, 56,
           'chase-menu', role='footer', enabled=stars >= 5)
    button('自选车综合杯' if stars >= 9 else '综合杯 · 需 9 星', left+448, 866, 212, 56,
           'cup-menu', role='footer', enabled=stars >= 9)
    details = button('赛事简报', width-left-250, 864, 250, 60, 'brief', event.id,
                     role='primary', primary=True)

    def preview(item):
        panel.board_event = item
        for event_id, (background, edge, _) in rows.items():
            if event_id == item.id:
                background.setColor(1, .91, .85, 1)
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
            condition = f'{item.distance:g} m  /  预算 {spec.budget}'
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


def board_route(root, event, width, left, span, *, center=681):
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
        scale = min((span-100)/max(1, max_x-min_x), 70/max(1, max_y-min_y))
        positions = [(left+span/2+(point.y-(min_x+max_x)/2)*scale,
                      center+(point.x-(min_y+max_y)/2)*scale) for point in points]
    else:
        positions = [(left+80, center), (left+span-80, center)]
    unit = 2/941
    line = LineSegs('career-board-outline')
    line.setThickness(3)
    line.setColor(.38, .41, .45, 1)
    for index, (x, y) in enumerate(positions):
        point = ((x-width/2)*unit, 0, 1-y*unit)
        line.moveTo(*point) if index == 0 else line.drawTo(*point)
    root.attachNewNode(line.create())
    markers = LineSegs('career-board-endpoints')
    markers.setColor(*ORANGE)
    markers.setThickness(7)
    for x, y in (positions[0], positions[-1]):
        markers.moveTo((x-width/2-3)*unit, 0, 1-y*unit)
        markers.drawTo((x-width/2+3)*unit, 0, 1-y*unit)
    root.attachNewNode(markers.create())


def brief(panel, progress, event):
    from challenge_catalog import ROAD_CHALLENGES

    spec = ROAD_CHALLENGES[event.id]
    club = isinstance(event, ClubEvent)
    width, left, fill, label, image, button = canvas(panel, progress, '赛前简报', season=True)
    span = width-2*left
    photo_width = span*.62
    right = left+photo_width+38
    columns = width-left-right
    image('career/'+(event.photo if club else event.id+'.png'), left, 115, photo_width, 546, crop=True)
    route = panel.content.attachNewNode('career-brief-route')
    board_route(route, event, width, left, photo_width, center=726)
    if event.shape not in COURSES and not club:
        label('起点', left+58, 770, 22, GRAY)
    end = '停车区' if not club and event.kind == 'parking' else '终点'
    label(f'{end} {event.distance:g} m', left+photo_width-20, 770, 22, GRAY, right=True)
    label(event.tip, left, 821, 21, GRAY, wrap=photo_width)

    label(event.name, right, 172, 48, bold=True)
    label(event.goal, right, 234, 25, wrap=columns)
    car = next(car for car in GARAGE_CARS if car.design_id == spec.design_id)
    label('指定车辆 · '+car.name, right, 318, 26, bold=True)
    if spec.assessment == 'road':
        targets = [f'≤ {target.seconds:g} s  /  ≤ {target.consumption:g} L/100km' for target in spec.targets]
    elif spec.assessment == 'lower':
        targets = [f'≤ {limit:g} m' for limit in spec.metric_limits]
    else:
        targets = event.targets
    for index, (medal, target) in enumerate(zip(('铜', '银', '金'), targets, strict=True)):
        y = 358+index*74
        fill(right, y, columns, 1, LINE, 0)
        label(medal, right+12, y+51, 28, ((.53, .32, .15, 1), GRAY, (.62, .39, .08, 1))[index], bold=True)
        label(target, right+70, y+51, 25 if width > 1400 else 22, wrap=columns-70)
    fill(right, 580, columns, 1, LINE, 0)
    label(event.rules if club else '碰撞、复位或驶离赛道会结束本场。', right, 643, 23, GRAY, wrap=columns)
    label(f'预算 {spec.budget}', right, 746, 29, bold=True)
    if club:
        record = event.best(panel.vehicle_view.base.session) if progress.available(event) else None
    else:
        record = progress.course_record(event)
    if record is not None:
        medal = (record['medal'] or '完赛') if club else ('', '铜', '银', '金')[record['stars']]
        title = '历史成绩' if not club and event.id not in progress.budget_records else '最佳成绩'
        label(f'{title} · {medal} / {record["seconds"]:.2f} s', right, 793, 21, GRAY)

    available = progress.available(event)
    button('返回赛事', left, 865, 166, 59, 'board', role='footer')
    button('调整方案', width-left-460, 865, 200, 59, 'start', event.id,
           role='secondary', enabled=available)
    button('原车发车' if available else f'需要 {event.unlock} 星', width-left-240, 865, 240, 59,
           'start-stock', event.id, role='primary', primary=True, enabled=available)
    panel.select(panel.primary if available else 0)


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
            image('garage-v2/'+HISTORICAL_PART_IMAGES[part.topic]+'.png', x+18, y+4, 38, 38)
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
