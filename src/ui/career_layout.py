"""落日黑曜石与琥珀金风格生涯赛事板、赛前简报、结算与暂停界面。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import LineSegs, TextNode, TextureStage, TransparencyAttrib

from career import CHAPTERS, EVENTS, PARTS
from career_courses import COURSES, CareerCourse
from career_garage import GARAGE_CARS, garage_cars
from highway_curve import HighwayCurve
from ui import atelier, theme
from ui.career_events import BOARD_EVENTS, ClubEvent
from ui.garage_layout import WHITE
from ui.lab_widgets import gradient_panel, rounded_panel
from vehicle_designs import vehicle_design

ORANGE = theme.AMBER
GOLD = theme.AMBER
DARK = theme.CARBON_SOLID
PAPER = theme.CARBON
LINE = theme.CARBON_EDGE
HISTORICAL_PART_IMAGES = {'tires': 'tire', 'brakes': 'brake', 'power': 'power-part', 'suspension': 'suspension-part'}


def vehicle_box(aspect):
    """生涯车辆展示区；加载准备与实际页面使用同一视口。"""
    width, unit = 941*aspect, 2/941
    margin, wide = width*.028, min(462., width*.32)
    return ((margin+wide+18-width/2)*unit, (width-margin-width/2)*unit,
            1-(205+541)*unit, 1-205*unit)


def canvas(panel, progress, title, *, car=False, budget=None, chrome=True, season=False):
    """四页共用同一落日黑曜石细描边母版；具体页面仍由独立业务函数绘制。"""
    aspect = panel.vehicle_view.base.getAspectRatio()
    panel.layout_aspect, panel.garage_roles, panel.card_edges = aspect, {}, {}
    width, unit = 941*aspect, 2/941
    margin = width*.028

    def point(x, y):
        return (x-width/2)*unit, 1-y*unit

    def box(x, y, w, h):
        a, b = point(x, y+h), point(x+w, y)
        return a[0], b[0], a[1], b[1]

    def fill(x, y, w, h, color=PAPER, radius=6):
        node = rounded_panel(panel.content, 'career-fill', box(x, y, w, h), color, radius*unit)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def label(text, x, y, size=22, color=None, *, bold=False, right=False, wrap=None, display=False):
        fg = theme.TEXT_LIGHT if color is None else color
        font = panel.garage_display_font if display else panel.font if bold else panel.garage_font
        item = panel.label(text, *point(x, y), size*unit, fg, font=font)
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
        tex_pair = None
        if role == 'primary':
            tex_pair = ('atelier/btn-primary.png', 'atelier/btn-primary-hover.png')
        elif role in ('secondary', 'footer', 'season-tab', 'setup-tab'):
            tex_pair = ('atelier/btn-ghost.png', 'atelier/btn-ghost-hover.png')
        elif role in ('season-tab-active', 'setup-active', 'category-active'):
            tex_pair = ('atelier/card-active.png', 'atelier/card-active.png')
        px, pz = point(x+w/2, y+h/2)
        item = panel.button(text, px, pz, w*unit, h*unit, command, value,
                            primary=primary, enabled=enabled, radius=6*unit)
        item['text_font'] = panel.font if role in ('primary', 'season-tab-active', 'setup-active') else panel.garage_font
        size = 19 if h < 44 else 23 if role == 'primary' else 20 if aspect > 1.5 else 18
        item['text_scale'], item['text_pos'] = size*unit, (0, -7*unit)
        item.setTransparency(TransparencyAttrib.MAlpha)
        idx = len(panel.buttons)-1
        panel.garage_roles[idx] = role
        if tex_pair is not None:
            item['geom'] = None
            item['frameTexture'] = atelier.tex(panel.loader, tex_pair[0])
            item['frameColor'] = (1, 1, 1, 1)
            panel.atelier_btn_tex[idx] = tex_pair
        return item

    if season:
        # 落日工坊柔暗实景底 + 哑光黑曜石大气暗罩 + 磨砂玻璃顶栏 + 拉丝微颗粒底栏（与主页/车库完全统一）。
        image(atelier.SUNSET_GARAGE_BG, 0, 0, width, 941, tint=(0.24, 0.22, 0.25, 1), crop=True)
        gradient_panel(panel.content, 'season-bg-scrim', box(0, 0, width, 941),
                       (0.045, 0.055, 0.078, 0.90), (0.045, 0.055, 0.078, 0.72))
        gradient_panel(panel.content, 'season-top-scrim', box(0, 0, width, 96),
                       (0.03, 0.04, 0.06, 0.0), (0.03, 0.04, 0.06, 0.88))
        image('atelier/top-nav-glass.png', margin + 206, 0, 320, 74)
        image('atelier/footer-surface.png', 0, 850, width, 91)

        panel.frames.append(atelier.wordmark(panel.content, panel.loader, box(margin, 15, 212, 40)))
        fill(margin+228, 21, 1.5, 28, (0.34, 0.40, 0.50, 0.85), 0)
        label(title, margin+246, 43, 21, WHITE, bold=True)
        fill(margin+246, 68, 84, 3, theme.AMBER, 1.5)

        star_w = 152
        image('atelier/btn-ghost.png', width-margin-star_w, 15, star_w, 42)
        label(f'★  {progress.stars} / 18 星', width-margin-star_w/2, 42, 17, theme.AMBER, bold=True)
        panel.labels[-1].textNode.setAlign(TextNode.ACenter)
        return width, margin, fill, label, image, button

    image(atelier.SUNSET_GARAGE_BG, 0, 0, width, 941, crop=True)
    gradient_panel(panel.content, 'career-car-scrim', box(0, 0, width*0.56, 941),
                   (0.040, 0.050, 0.072, 0.78), (0.040, 0.050, 0.072, 0.0), horizontal=True)
    gradient_panel(panel.content, 'career-top-scrim', box(0, 0, width, 118),
                   (0.03, 0.04, 0.06, 0.0), (0.03, 0.04, 0.06, 0.72))
    gradient_panel(panel.content, 'career-bot-scrim', box(0, 740, width, 201),
                   (0.03, 0.04, 0.06, 0.76), (0.03, 0.04, 0.06, 0.0))
    if car:
        wide_ref = min(462., width*.32)
        stage_x = margin+wide_ref+18
        stage_span = width-margin-stage_x
        image('atelier/floor-warm-bounce.png', stage_x-28, 520, stage_span+56, 260,
              tint=(1, 0.90, 0.74, 0.80))
        vehicle = panel.vehicle_view.base.workspace_vehicle
        panel.vehicle_view.show(panel.content, vehicle_box(aspect), vehicle, studio=True)
        panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
        panel.vehicle_view.highlight(None)
        name = next(item.name for item in garage_cars(vehicle) if item.design_id == vehicle.design_id)
        letter, score, _pi_color, power_kw, _ = theme.vehicle_pi(vehicle.config)
        badge_w = 344
        bx = width-margin-badge_w
        image('atelier/card-idle.png', bx-8, 88, badge_w+16, 102)
        fill(bx+8, 115, 3.5, 48, theme.AMBER, 2)
        fill(bx+22, 125, 84, 28, theme.STEEL_BG, 5)
        lbl_pi = label(f'{letter} {score}', bx+64, 145, 16, theme.STEEL_TEXT, bold=True, display=True)
        lbl_pi.textNode.setAlign(TextNode.ACenter)
        label(name, width-margin-18, 135, 22, WHITE, bold=True, right=True)
        label(f'{power_kw:.0f} kW  |  {vehicle.config.mass:.0f} kg', width-margin-18, 165, 15, theme.DARK_SUB, right=True)
    if chrome:
        image('atelier/bar-top.png', 0, 0, width, 72)
        image('atelier/footer-surface.png', 0, 856, width, 85)
    if budget is not None:
        label(title, margin, 46, 28 if aspect > 1.5 else 24, WHITE, bold=True)
        panel.challenge_readouts['budget'] = label('', width-margin, 46 if aspect > 1.5 else 28,
                                                   20 if aspect > 1.5 else 17, WHITE, right=True)
        return width, margin, fill, label, image, button
    panel.frames.append(atelier.wordmark(panel.content, panel.loader, box(margin, 15, 212 if aspect > 1.5 else 182, 40 if aspect > 1.5 else 34)))
    button('赛事', width*.42-60, 14, 120, 44, 'board', role='tab-active' if title == '生涯赛事' else 'tab')
    button('海岸车库' if title == '生涯赛事' else title, width*.56-85, 14, 170, 44,
           'garage' if title == '生涯赛事' else 'board', role='tab' if title == '生涯赛事' else 'tab-active')
    fill(width*(.42 if title == '生涯赛事' else .56)-(60 if title == '生涯赛事' else 85)+20,
         66, (120 if title == '生涯赛事' else 170)-40, 3, theme.AMBER, 1.5)
    star_w = 152
    image('atelier/btn-ghost.png', width-margin-star_w, 15, star_w, 42)
    label(f'★  {progress.stars} / 18 星', width-margin-star_w/2, 42, 17, theme.AMBER, bold=True)
    panel.labels[-1].textNode.setAlign(TextNode.ACenter)
    return width, margin, fill, label, image, button


def board(panel, progress, *, chapter=None, event=None):
    from challenge_catalog import ROAD_CHALLENGES

    recommended = progress.recommended()
    if chapter is None:
        chapter = (event or recommended).chapter
    events = tuple(item for item in BOARD_EVENTS.values() if item.chapter == chapter)
    event = event or (recommended if recommended in events else events[0])
    width, left, fill, label, image, button = canvas(panel, progress, '生涯赛季', season=True)
    unit = 2/941
    listing = width*.405
    right, preview_width = left+listing+26, width-2*left-listing-26

    # 左侧拉丝黑曜石赛事列表区（保留严格纵向排列，确保上下方向键精准移动）。
    label('生涯赛季  /  章节选择', left, 102, 14, theme.DARK_SUB)
    label('第一季 · 海岸生涯', left, 138, 30, WHITE, bold=True)

    # 章节细描边标签栏（选中暖琥珀金微光卡，未选中拉丝暗钢）。
    tab_gap = 10
    tab_width = (listing-tab_gap*(len(CHAPTERS)-1))/len(CHAPTERS)
    for index, title in enumerate(CHAPTERS):
        x = left+index*(tab_width+tab_gap)
        button(title, x, 162, tab_width, 46, 'board-chapter', index,
               role='season-tab-active' if index == chapter else 'season-tab')

    rows = {}
    stars = progress.stars
    for index, item in enumerate(events):
        y = 228+index*96
        locked = stars < item.unlock
        image('atelier/card-idle.png', left-4, y-4, listing+8, 84+8)
        # 选中时亮起高分柔光琥珀金微光卡框。
        edge = image('atelier/card-active.png', left-4, y-4, listing+8, 84+8)
        background = fill(left, y, listing, 84, (0, 0, 0, 0), 7)
        button('', left, y, listing, 84, 'brief', item.id, role='event-card')
        radio_node = image('atelier/radio-idle.png', left+listing-36, y+30, 23, 23)
        rows[item.id] = background, edge, len(panel.buttons)-1, radio_node

        thumb_name = item.photo if isinstance(item, ClubEvent) else item.id+'.png'
        fill(left+11, y+9, 106, 66, (0.04, 0.05, 0.07, 0.9), 4)
        image('career/'+thumb_name, left+12, y+10, 104, 64,
              tint=(0.45, 0.48, 0.55, 1) if locked else WHITE, crop=True)

        tx = left+130
        label(item.name, tx, y+38, 21 if width > 1400 else 19,
              theme.DARK_LOCKED if locked else WHITE, bold=True)
        sub_text = f'{item.distance:g} m' if getattr(item, 'distance', None) else item.goal
        label(sub_text, tx, y+65, 14.5, theme.DARK_LOCKED if locked else theme.DARK_SUB)

        status_color = theme.DARK_SUB
        if locked:
            status = f'需 {item.unlock} 星'
            status_color = theme.DARK_LOCKED
        elif isinstance(item, ClubEvent):
            record = item.best(panel.vehicle_view.base.session)
            if record:
                medal = record['medal'] or '完赛'
                status = f'{medal} · {record["seconds"]:.2f} s'
                status_color = {'金': theme.AMBER, '银': theme.SILVER, '铜': theme.BRONZE}.get(medal, theme.STEEL_TEXT)
            else:
                status = '待挑战'
                status_color = theme.STEEL_TEXT
        else:
            status = '待挑战'
            status_color = theme.STEEL_TEXT
            record = progress.course_record(item)
            if record is not None:
                medal = ('', '铜', '银', '金')[record['stars']]
                historic = '历史 · ' if item.id not in progress.budget_records else ''
                status = f'{historic}{medal} · {record["seconds"]:.2f} s'
                status_color = (theme.DARK_SUB, theme.BRONZE, theme.SILVER, theme.AMBER)[record['stars']]
        label(status, left+listing-50, y+48, 17 if width > 1400 else 15.5, status_color, bold=not locked, right=True)

    if progress.notice:
        label(progress.notice, left, 816, 16, theme.AMBER, wrap=listing)

    # 右侧电影感赛道预览舞台（深黑曜石拉丝框 + 实景赛道图 + 遥测路线 + Cycles 微缩指定车辆）。
    fill(right-1, 89, preview_width+2, 740, (0.28, 0.34, 0.44, 0.85), 9)
    fill(right, 90, preview_width, 738, (0.068, 0.082, 0.112, 0.96), 8)
    photo_name = event.photo if isinstance(event, ClubEvent) else event.id+'.png'
    photo = image('career/'+photo_name, right, 90, preview_width, 446, crop=True)
    gradient_panel(panel.content, 'board-hero-scrim',
                   ((right-width/2)*unit, (right+preview_width-width/2)*unit, 1-536*unit, 1-275*unit),
                   (0.068, 0.082, 0.112, 0.99), (0.068, 0.082, 0.112, 0.0))
    fill(right+24, 404, 96, 25, theme.STEEL_BG, 5)
    label('赛事预览', right+72, 422, 13, theme.STEEL_TEXT, bold=True)
    panel.labels[-1].textNode.setAlign(TextNode.ACenter)

    title = label('', right+24, 482, 36, WHITE, bold=True)
    goal = label('', right+24, 520, 17.5, theme.DARK_SUB, wrap=preview_width-48)

    fill(right+19, 559, preview_width-38, 152, (0.24, 0.29, 0.38, 0.78), 8)
    fill(right+20, 560, preview_width-40, 150, (0.088, 0.106, 0.144, 0.95), 7)
    route_root = panel.content.attachNewNode('career-board-route')
    start_label = label('起点', right+54, 694, 15.5, theme.DARK_SUB)
    end_label = label('', right+preview_width-54, 694, 15.5, theme.DARK_SUB, right=True)

    fill(right+20, 728, preview_width-40, 1.2, (0.22, 0.27, 0.35, 0.85), 0)
    car_thumb = image('garage-v2/car-game-tuned.png', right+20, 742, 120, 68, tint=(0.95, 0.92, 0.86, 0.96))
    label('指定车辆', right+152, 764, 13.5, theme.DARK_SUB)
    car = label('', right+152, 796, 20 if width > 1400 else 18, WHITE, bold=True)
    label('参赛条件', right+preview_width-24, 764, 13.5, theme.DARK_SUB, right=True)
    requirement = label('', right+preview_width-24, 796, 19 if width > 1400 else 17, theme.AMBER, bold=True, right=True)

    # 底部拉丝通栏行动按钮（适配 16:9 与 4:3 无挤压）。
    narrow = width < 1400
    b_back_w, b_gar_w = (96, 96) if narrow else (108, 108)
    b_chase_w = 172 if narrow else 196
    b_cup_w = 190 if narrow else 212
    b_gap = 10 if narrow else 12
    bx = left
    button('返回', bx, 868, b_back_w, 54, 'exit', role='footer')
    bx += b_back_w + b_gap
    button('车库', bx, 868, b_gar_w, 54, 'garage', role='footer')
    bx += b_gar_w + b_gap
    button('赛段追时' if stars >= 5 else '追时 · 需 5 星', bx, 868, b_chase_w, 54,
           'chase-menu', role='footer', enabled=stars >= 5)
    bx += b_chase_w + b_gap
    button('自选车综合杯' if stars >= 9 else '综合杯 · 需 9 星', bx, 868, b_cup_w, 54,
           'cup-menu', role='footer', enabled=stars >= 9)
    cta_w = 228 if narrow else 248
    details = button('进入简报', width-left-cta_w, 865, cta_w, 58, 'brief', event.id,
                     role='primary', primary=True)
    details['text_pos'] = (16*unit, -7*unit)
    d_ic = atelier.picture(details, panel.loader, 'atelier/icon-steering.png',
                           (-72*unit, -44*unit, -14*unit, 14*unit), color=theme.INK)
    panel.frames.append(d_ic)

    def preview(item):
        panel.board_event = item
        for event_id, (background, edge, _, radio_node) in rows.items():
            if event_id == item.id:
                background.hide()
                edge.show()
                radio_node['frameTexture'] = atelier.tex(panel.loader, 'atelier/radio-active.png')
            else:
                background.hide()
                edge.hide()
                radio_node['frameTexture'] = atelier.tex(panel.loader, 'atelier/radio-idle.png')
        photo['frameTexture'] = panel.photos[item.id]
        title.setText(item.name)
        goal.setText(item.goal)
        spec = ROAD_CHALLENGES[item.id]
        car_name = next(car.name for car in GARAGE_CARS if car.design_id == spec.design_id)
        car.setText(car_name)
        thumb_id = spec.design_id if spec.design_id in (
            'game-tuned', 'coastal-hatch', 'coastal-roadster', 'gr86-2022-premium-6mt',
            'coastal-gt', 'club-coupe', 'subaru-wrx-sti', 'porsche-930') else 'game-tuned'
        car_thumb['frameTexture'] = atelier.tex(panel.loader, f'garage-v2/car-{thumb_id}.png')
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
        board_route(route_root, item, width, right, preview_width, center=636)

    panel.board_preview = preview
    preview(event)
    panel.select(rows[event.id][2])


def board_route(root, event, width, left, span, *, center=676):
    """用关卡几何绘制冷静钢蓝预览路径与琥珀金起终点。"""
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
    line.setThickness(3.8)
    line.setColor(*theme.STEEL_TEXT)
    for index, (x, y) in enumerate(positions):
        point = ((x-width/2)*unit, 0, 1-y*unit)
        line.moveTo(*point) if index == 0 else line.drawTo(*point)
    root.attachNewNode(line.create())
    markers = LineSegs('career-board-endpoints')
    markers.setColor(*theme.AMBER)
    markers.setThickness(8.5)
    for x, y in (positions[0], positions[-1]):
        markers.moveTo((x-width/2-4)*unit, 0, 1-y*unit)
        markers.drawTo((x-width/2+4)*unit, 0, 1-y*unit)
    root.attachNewNode(markers.create())


def brief(panel, progress, event):
    from challenge_catalog import ROAD_CHALLENGES

    spec = ROAD_CHALLENGES[event.id]
    club = isinstance(event, ClubEvent)
    width, left, fill, label, image, button = canvas(panel, progress, '赛前简报', season=True)
    unit = 2/941
    span = width-2*left
    photo_width = span*.585
    right = left+photo_width+26
    columns = width-left-right

    # 左侧大幅赛道电影卡 + 遥测路线与驾驶提示。
    fill(left-1, 89, photo_width+2, 740, (0.28, 0.34, 0.44, 0.85), 9)
    fill(left, 90, photo_width, 738, (0.068, 0.082, 0.112, 0.96), 8)
    image('career/'+(event.photo if club else event.id+'.png'), left, 90, photo_width, 510, crop=True)
    gradient_panel(panel.content, 'brief-scrim',
                   ((left-width/2)*unit, (left+photo_width-width/2)*unit, 1-600*unit, 1-410*unit),
                   (0.068, 0.082, 0.112, 0.99), (0.068, 0.082, 0.112, 0.0))
    fill(left+19, 615, photo_width-38, 120, (0.24, 0.29, 0.38, 0.78), 8)
    fill(left+20, 616, photo_width-40, 118, (0.088, 0.106, 0.144, 0.95), 7)
    route = panel.content.attachNewNode('career-brief-route')
    board_route(route, event, width, left, photo_width, center=676)
    if event.shape not in COURSES and not club:
        label('起点', left+54, 722, 16, theme.DARK_SUB)
    end = '停车区' if not club and event.kind == 'parking' else '终点'
    label(f'{end}  {event.distance:g} m', left+photo_width-34, 722, 16.5, theme.STEEL_TEXT, bold=True, right=True)
    label(event.tip, left+26, 782, 17.5, WHITE, wrap=photo_width-52)

    # 右侧拉丝黑曜石精密简报操作台（复刻主页与车库右侧拉丝面板实体质感）。
    fill(right-1, 89, columns+2, 740, (0.28, 0.34, 0.44, 0.85), 9)
    fill(right, 90, columns, 738, (0.068, 0.082, 0.112, 0.96), 8)
    pad = 28
    rx, rw = right+pad, columns-2*pad

    label('生涯赛季  /  赛前简报', rx, 130, 13.5, theme.DARK_SUB)
    label(event.name, rx, 176, 34 if width > 1400 else 30, WHITE, bold=True)
    label(event.goal, rx, 214, 17, theme.DARK_SUB, wrap=rw)

    # 指定车辆实景缩略卡（嵌入真实 Cycles 车模小图 + 钢蓝 PI 徽章）。
    car = next(car for car in GARAGE_CARS if car.design_id == spec.design_id)
    c_let, c_scr, _, _, _ = theme.vehicle_pi(vehicle_design(car.design_id).config)
    image('atelier/card-idle.png', rx-4, 244, rw+8, 76)
    thumb_id = car.design_id if car.design_id in (
        'game-tuned', 'coastal-hatch', 'coastal-roadster', 'gr86-2022-premium-6mt',
        'coastal-gt', 'club-coupe', 'subaru-wrx-sti', 'porsche-930') else 'game-tuned'
    image(f'garage-v2/car-{thumb_id}.png', rx+10, 252, 102, 58, tint=(0.96, 0.93, 0.88, 0.98))
    label('指定车辆', rx+122, 272, 13, theme.DARK_SUB)
    label(car.name, rx+122, 300, 19 if width > 1400 else 17, WHITE, bold=True)
    fill(rx+rw-84, 268, 70, 26, theme.STEEL_BG, 5)
    lbl_pi = label(f'{c_let} {c_scr}', rx+rw-49, 287, 14.5, theme.STEEL_TEXT, bold=True, display=True)
    lbl_pi.textNode.setAlign(TextNode.ACenter)

    if spec.assessment == 'road':
        targets = [f'≤ {target.seconds:g} s   ·   ≤ {target.consumption:g} L/100km' for target in spec.targets]
    elif spec.assessment == 'lower':
        targets = [f'≤ {limit:g} m' for limit in spec.metric_limits]
    else:
        targets = event.targets
    medal_colors = (theme.BRONZE, theme.SILVER, theme.AMBER)
    for index, (medal, target) in enumerate(zip(('铜牌', '银牌', '金牌'), targets, strict=True)):
        y = 336+index*74
        is_gold = index == 2
        image('atelier/card-active.png' if is_gold else 'atelier/card-idle.png', rx-4, y-4, rw+8, 64+8)
        fill(rx+2, y+13, 4, 38, medal_colors[index], 2)
        label(medal, rx+20, y+40, 19.5, medal_colors[index], bold=True)
        label(target, rx+rw-16, y+40, 18.5 if width > 1400 else 16.5, WHITE, right=True)

    label(event.rules if club else '碰撞、复位或驶离赛道会结束本场。', rx, 594, 16.5, theme.DARK_SUB, wrap=rw)
    fill(rx, 640, rw, 1.2, (0.22, 0.27, 0.35, 0.85), 0)
    label('本场改装预算', rx, 676, 14, theme.DARK_SUB)
    label(f'{spec.budget}', rx, 718, 30, theme.AMBER, bold=True, display=True)
    if club:
        record = event.best(panel.vehicle_view.base.session) if progress.available(event) else None
    else:
        record = progress.course_record(event)
    if record is not None:
        medal = (record['medal'] or '完赛') if club else ('', '铜', '银', '金')[record['stars']]
        rec_title = '历史成绩' if not club and event.id not in progress.budget_records else '个人最佳'
        label(rec_title, rx+rw, 676, 14, theme.DARK_SUB, right=True)
        label(f'{medal} · {record["seconds"]:.2f} s', rx+rw, 714, 21, theme.STEEL_TEXT, bold=True, right=True)

    available = progress.available(event)
    button('返回赛事', left, 868, 156, 54, 'board', role='footer')
    tune_btn = button('调整方案', width-left-460, 865, 202, 58, 'start', event.id,
                      role='secondary', enabled=available)
    tune_btn['text_pos'] = (14*unit, -7*unit)
    t_ic = atelier.picture(tune_btn, panel.loader, 'atelier/icon-sliders.png',
                           (-66*unit, -42*unit, -12*unit, 12*unit),
                           color=WHITE if available else theme.DARK_LOCKED)
    panel.frames.append(t_ic)
    go_btn = button('原车发车' if available else f'需要 {event.unlock} 星', width-left-244, 865, 244, 58,
                    'start-stock', event.id, role='primary', primary=True, enabled=available)
    if available:
        go_btn['text_pos'] = (16*unit, -7*unit)
        g_ic = atelier.picture(go_btn, panel.loader, 'atelier/icon-steering.png',
                               (-72*unit, -44*unit, -14*unit, 14*unit), color=theme.INK)
        panel.frames.append(g_ic)
    panel.select(panel.primary if available else 0)


def result(panel, progress, race_result, award):
    width, left, fill, label, image, button = canvas(panel, progress, '赛事结算', car=True)
    unit = 2/941
    event = next(event for event in EVENTS if event.id == race_result.event_id)
    wide = min(462., width*.32)
    inner, x = wide-48, left+24
    image('atelier/panel-obsidian.png', left-10, 86, wide+20, 756)
    fill(left+10, 114, 4, 42, theme.AMBER, 2)

    label(f'{event.chapter+1:02} / {event.name}', x, 146, 16, theme.DARK_SUB)
    label('赛事完成' if race_result.succeeded else '再试一次', x, 202, 42, WHITE, bold=True)
    label('★'*race_result.stars+'☆'*(3-race_result.stars), x, 294, 70, theme.AMBER)
    label('完赛用时' if race_result.succeeded else '本场用时', x, 352, 17, theme.DARK_SUB)
    label(f'{race_result.elapsed:.2f} s', x, 418, 50, WHITE, bold=True, display=True)
    fill(x, 446, inner, 1.2, (0.24, 0.29, 0.38, 0.85), 0)
    label('本场奖励' if award['saved'] else '奖励尚未保存', x, 486, 17, theme.DARK_SUB)
    label(f'+{award["credits"]} 积分', x, 540, 38, theme.AMBER, bold=True)
    label(f'{progress.stars} / 18 星', x, 590, 21, WHITE, bold=True)
    fill(x, 610, inner, 8, (0.14, 0.17, 0.23, 0.95), 4)
    if progress.stars:
        fill(x, 610, inner*progress.stars/18, 8, theme.AMBER, 4)
    fill(x, 644, inner, 1.2, (0.24, 0.29, 0.38, 0.85), 0)
    cars = [car for car in GARAGE_CARS if car.design_id in award['vehicles']]
    parts = [name for name in award['unlocked'] if name.startswith('零件：')]
    events = [name for name in award['unlocked'] if not name.startswith(('零件：', '新车：'))]
    heading = '保存失败' if not award['saved'] else '新解锁' if award['unlocked'] else '本场记录'
    if award['saved'] and events and (cars or parts):
        heading += ' · '+'、'.join(events)
    label(heading, x, 680, 17 if events and (cars or parts) else 20, WHITE, bold=True)
    if not award['saved']:
        message = progress.notice[:40]+'…' if len(progress.notice) > 40 else progress.notice
        label(message, x, 718, 17, theme.AMBER, wrap=inner)
        button('重试保存奖励', x, 772, inner, 42, 'save', role='primary', primary=True)
    elif cars or parts or events:
        y = 696
        if cars:
            car_height = 64 if len(cars) > 2 else 50
            image('atelier/card-active.png', x-6, y-5, inner+12, car_height+10)
            image('garage-v2/car-'+cars[-1].design_id+'.png', x+6, y+2, 85, 46)
            title = label(cars[-1].name+' · 新车', x+103, y+23, 20, WHITE, bold=True)
            title.setScale(min(20., (inner-113)/title.textNode.getWidth())*2/941)
            if len(cars) > 1:
                label('同时解锁：'+'、'.join(car.name for car in cars[:-1]),
                      x+103, y+44, 15, theme.DARK_SUB, wrap=inner-108)
            y += car_height+7
        if parts:
            image('atelier/card-idle.png', x-6, y-5, inner+12, 56)
            part = next(part for part in PARTS if part.name == parts[0][3:])
            image('garage-v2/'+HISTORICAL_PART_IMAGES[part.topic]+'.png', x+18, y+4, 38, 38)
            label('、'.join(name[3:] for name in parts), x+103, y+28, 17, WHITE, wrap=inner-108)
        if events and not (cars or parts):
            label('赛事：'+'、'.join(events), x, 728, 19, theme.DARK_SUB, wrap=inner)
    else:
        detail = race_result.reason or ('星级未提高，本场不重复发放积分。' if award['credits'] == 0 else '完成赛事。')
        detail = detail.rstrip('。')
        if event.kind == 'parking' and race_result.parking_error is not None:
            detail = f'距停车中心 {race_result.parking_error:.1f} 米\n'+detail
        elif event.kind == 'slalom':
            detail = f'通过 {sum(race_result.passed)} / 5 道门\n'+detail
        label(detail, x, 728, 18, theme.DARK_SUB, wrap=inner)
    next_event = progress.recommended()
    strip_w = min(462, width-left-wide-40)
    strip_x = width-left-strip_w
    image('atelier/panel-obsidian.png', strip_x-9, 738, strip_w+18, 100)
    fill(strip_x+10, 760, 4, 56, theme.AMBER, 2)
    fill(strip_x+20, 755, 102, 66, (0.04, 0.05, 0.08, 0.92), 5)
    image('career/'+next_event.id+'.png', strip_x+22, 757, 98, 62, crop=True)
    label('下一场推荐', strip_x+134, 777, 13, theme.AMBER, bold=True)
    label(next_event.name, strip_x+134, 811, 23, WHITE, bold=True)
    label('Enter  确认    Esc  返回赛事', left, 908, 17, theme.DARK_SUB)
    primary_w, secondary_w, gap = 240, 190, 18
    start_x = width-left-primary_w-2*secondary_w-2*gap
    if width < 1400:
        panel.labels[-1].setText('Esc  返回赛事')
        primary_w, secondary_w, gap = 210, 170, 14
        start_x = width-left-primary_w-2*secondary_w-2*gap
    button('重试本场', start_x, 874, secondary_w, 52, 'start', event.id, role='secondary')
    button('查看新车' if award['vehicles'] else '车库改装', start_x+secondary_w+gap, 874,
           secondary_w, 52, 'garage-new' if award['vehicles'] else 'garage',
           award['vehicles'][-1] if award['vehicles'] else None, role='secondary')
    cont_btn = button('继续赛事', width-left-primary_w, 874, primary_w, 52, 'board',
                      role='primary' if award['saved'] else 'secondary', primary=award['saved'])
    if award['saved']:
        cont_btn['text_pos'] = (16*unit, -7*unit)
        c_ic = atelier.picture(cont_btn, panel.loader, 'atelier/icon-steering.png',
                               (-72*unit, -46*unit, -13*unit, 13*unit), color=theme.INK)
        panel.frames.append(c_ic)
    panel.select(panel.primary)


def pause(panel, progress, event):
    width, left, fill, label, image, button = canvas(panel, progress, '比赛暂停', car=True)
    unit = 2/941
    wide = min(462., width*.32)
    x, inner = left+28, wide-56
    image('atelier/panel-obsidian.png', left-10, 86, wide+20, 756)
    fill(left+10, 114, 4, 42, theme.AMBER, 2)
    label(f'正在比赛  /  {event.name}', x, 146, 15, theme.DARK_SUB)
    label('比赛已暂停', x, 206, 42, WHITE, bold=True)
    for index, (name, command) in enumerate((('继续驾驶', 'resume'), ('重新开始', 'retry'), ('退出本场', 'board'))):
        item = button(name, x, 286+index*96, inner, 68, command,
                      role='primary' if index == 0 else 'secondary', primary=index == 0)
        if index == 0:
            item['text_pos'] = (16*unit, -7*unit)
            ic = atelier.picture(item, panel.loader, 'atelier/icon-steering.png',
                                 (-74*unit, -46*unit, -14*unit, 14*unit), color=theme.INK)
            panel.frames.append(ic)
    strip_w = min(360, width-left-wide-40)
    image('atelier/panel-obsidian.png', width-left-strip_w-9, 736, strip_w+18, 100)
    fill(width-left-strip_w+10, 758, 4, 56, theme.AMBER, 2)
    label(event.name, width-left-strip_w+26, 782, 22, WHITE, bold=True)
    label(f'{event.distance:g} 米  |  {event.limit:g} 秒时限', width-left-strip_w+26, 813, 16, theme.DARK_SUB)
    label('Enter  确认    Esc  继续驾驶', left, 908, 17, theme.DARK_SUB)
    panel.select(panel.primary)
