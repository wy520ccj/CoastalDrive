"""海岸车库（Porsche Configurator / GT7 展厅风格）：顶部悬浮分栏胶囊 + 中央全幅展车 + 底部横向选车/色漆画廊。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from skins import SKINS
from ui import theme
from ui.lab_widgets import rounded_panel

INK = theme.INK
GRAY = theme.MUTED
WHITE = (1, 1, 1, 1)
ORANGE = theme.ORANGE
LINE = theme.HAIRLINE


def show(panel, progress, vehicle, notice, tab, preview, skin_index, cars):
    aspect = panel.vehicle_view.base.getAspectRatio()
    panel.garage_aspect = aspect
    panel.garage_roles = {}
    panel.garage_values = {}
    height, width = 941., 941.*aspect
    unit = 2/height
    margin = width*.032
    usable = width-2*margin

    def point(x, y):
        return (x-width/2)*unit, 1-y*unit

    def box(x, y, w, h):
        a, b = point(x, y+h), point(x+w, y)
        return a[0], b[0], a[1], b[1]

    def fill(x, y, w, h, color, radius=8):
        node = rounded_panel(panel.content, 'garage-fill', box(x, y, w, h), color, radius*unit)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def label(text, x, y, size=18, color=INK, bold=False, right=False, center=False, wrap=None):
        p = point(x, y)
        item = panel.label(text, *p, size*unit, color, font=panel.font if bold else panel.garage_font)
        if right:
            item.textNode.setAlign(TextNode.ARight)
        elif center:
            item.textNode.setAlign(TextNode.ACenter)
        if wrap is not None:
            item.textNode.setWordwrap(wrap/size)
        return item

    def image(name, x, y, w, h, color=WHITE):
        if name not in panel.garage_textures:
            panel.garage_textures[name] = panel.loader.loadTexture(theme.asset_filename(name))
        frame = DirectFrame(parent=panel.content, frameSize=box(x, y, w, h),
            frameTexture=panel.garage_textures[name], frameColor=color, state=DGG.DISABLED)
        frame.setTransparency(TransparencyAttrib.MAlpha)
        panel.frames.append(frame)
        return frame

    def button(text, x, y, w, h, command, value=None, *, role='plain', enabled=True, primary=False, radius=10):
        px, pz = point(x+w/2, y+h/2)
        item = panel.button(text, px, pz, w*unit, h*unit, command, value,
                            enabled=enabled, primary=primary, radius=radius*unit)
        item['text_font'] = panel.font if role in ('primary', 'tab-active') else panel.garage_font
        item['text_scale'] = (21 if role == 'primary' else 18)*unit
        item['text_pos'] = (0, -6*unit)
        item.setTransparency(TransparencyAttrib.MAlpha)
        panel.garage_roles[len(panel.buttons)-1] = role
        return item

    # 全屏日光海岸车库背景。
    image('backgrounds/garage-coastal-v2.png', 0, 0, width, height)
    background = panel.frames[-1]
    texture = panel.garage_textures['backgrounds/garage-coastal-v2.png']
    ratio = aspect/(texture.getXSize()/texture.getYSize())
    background.setTexScale(TextureStage.getDefault(), ratio, 1)
    background.setTexOffset(TextureStage.getDefault(), (1-ratio)/2, 0)

    # 3D 展车居中通透呈现，上方避开导航胶囊，下方避开横向选车坞（绝对零重叠）。
    preview = vehicle if preview is None or tab != 'cars' else preview
    view_top, view_bottom = 98., 632.
    panel.vehicle_view.show(panel.content, box(width*.12, view_top, width*.76, view_bottom-view_top),
                            preview, studio=True, skin_index=skin_index)
    panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
    panel.vehicle_view.highlight(None)

    # ── 顶部悬浮暖阳导航栏（复古三色标 + 分段胶囊 + 暖金星标）──
    brand_w = 278 if aspect > 1.5 else 214
    fill(margin+1, 25, brand_w, 50, theme.SHADOW, 14)
    fill(margin-1, 21, brand_w+2, 52, LINE, 15)
    fill(margin, 22, brand_w, 50, theme.GLASS_LIGHT, 14)
    fill(margin+12, 32, 4, 10, ORANGE, 2)
    fill(margin+12, 44, 4, 9, theme.AMBER, 2)
    fill(margin+12, 55, 4, 7, theme.SEA, 2)
    brand = label('COASTAL DRIVE', margin+26, 55, 22 if aspect > 1.5 else 19, INK, True)
    brand['font'] = panel.garage_display_font

    # 中央悬浮分段胶囊导航：我的车辆 / 挑战改装 / 车身颜色 / 专家参数。
    tabs = (('cars', '我的车辆'), ('upgrade', '挑战改装'), ('paint', '车身颜色'), ('setup', '专家参数'))
    nav_w = 122 if aspect > 1.5 else 96
    nav_gap = 6
    total_nav = len(tabs)*nav_w+(len(tabs)-1)*nav_gap+12
    nav_x = (width-total_nav)/2
    fill(nav_x+1, 25, total_nav, 50, theme.SHADOW, 25)
    fill(nav_x-1, 21, total_nav+2, 52, LINE, 26)
    fill(nav_x, 22, total_nav, 50, theme.GLASS_LIGHT, 25)
    for i, (key, title) in enumerate(tabs):
        tx = nav_x+6+i*(nav_w+nav_gap)
        button(title, tx, 27, nav_w, 40, 'garage-tab', key,
               role='tab-active' if key == tab else 'tab', radius=20)

    # 右上角暖金星级 + 车型参数奶油浮卡。
    car = next(item for item in cars if item.design_id == preview.design_id)
    config = preview.config
    power = max(rpm*torque/9549.3 for rpm, torque in config.torque_curve)
    star_w = 126
    sx = width-margin-star_w
    fill(sx+1, 25, star_w, 50, theme.SHADOW, 25)
    fill(sx-1, 21, star_w+2, 52, (0.87, 0.72, 0.45, .9), 26)
    fill(sx, 22, star_w, 50, theme.AMBER_TINT, 25)
    label(f'★ {progress.stars}/18', sx+star_w/2, 54, 18, theme.GOLD, True, center=True)

    if tab in ('cars', 'paint'):
        spec_w = 290
        spec_x = width-margin-spec_w
        fill(spec_x+1, 95, spec_w, 72, theme.SHADOW, 12)
        fill(spec_x-1, 91, spec_w+2, 74, LINE, 13)
        fill(spec_x, 92, spec_w, 72, theme.GLASS_LIGHT, 12)
        fill(spec_x+spec_w-5, 106, 5, 44, ORANGE, 2.5)
        label(car.name, width-margin-20, 124, 22, INK, True, right=True)
        tuning = '项目调校 · ' if preview.design_id in ('game-tuned', 'coastal-hatch', 'coastal-roadster', 'club-coupe', 'subaru-wrx-sti', 'porsche-930') else ''
        label(f'{tuning}{power:.0f} kW  /  {config.mass:.0f} kg', width-margin-20, 151, 15, GRAY, right=True)

    # ── 底部横向展厅画廊坞（完全替代旧左侧白板墙）──
    dock_y, dock_h = 650., 262.
    fill(margin+2, dock_y+4, usable, dock_h, theme.SHADOW, 18)
    fill(margin-1, dock_y-1, usable+2, dock_h+2, LINE, 19)
    fill(margin, dock_y, usable, dock_h, theme.GLASS_LIGHT, 18)

    pad = 22.
    action_w = min(252., usable*.19)
    action_x = margin+usable-pad-action_w
    gallery_x = margin+pad
    gallery_w = action_x-gallery_x-22

    if tab == 'cars':
        count = sum(progress.stars >= item.unlock or item.design_id == vehicle.design_id for item in cars)
        fill(gallery_x, dock_y+20, 4, 22, ORANGE, 2)
        label('我的车辆', gallery_x+14, dock_y+39, 22, INK, bold=True)
        label(f'已解锁 {count} / {len(cars)} 辆', gallery_x+124, dock_y+38, 16, GRAY)
        selected = next(i for i, item in enumerate(cars) if item.design_id == preview.design_id)
        first = min(max(0, selected-1), max(0, len(cars)-4))
        arrow_w = 38.
        cards_x = gallery_x+arrow_w+12
        cards_w = gallery_w-2*(arrow_w+12)
        card_gap = 14.
        card_w = (cards_w-3*card_gap)/4
        card_y, card_h = dock_y+56, 158.
        if len(cars) > 4:
            button('‹', gallery_x, card_y+46, arrow_w, 66, 'garage-car',
                   cars[(selected-1) % len(cars)].design_id, role='secondary', radius=10)
            button('›', cards_x+cards_w+12, card_y+46, arrow_w, 66, 'garage-car',
                   cars[(selected+1) % len(cars)].design_id, role='secondary', radius=10)
        for index, item in enumerate(cars[first:first+4]):
            cx = cards_x+index*(card_w+card_gap)
            active = item.design_id == preview.design_id
            fill(cx-1.5, card_y-1.5, card_w+3, card_h+3, ORANGE if active else LINE, 13)
            button('', cx, card_y, card_w, card_h, 'garage-car', item.design_id,
                   role='category-active' if active else 'category', radius=12)
            if active:
                fill(cx+18, card_y, card_w-36, 4, ORANGE, 2)
            thumbnail = item.design_id if item.design_id in ('game-tuned', 'coastal-hatch', 'coastal-roadster',
                'gr86-2022-premium-6mt', 'coastal-gt', 'club-coupe', 'subaru-wrx-sti', 'porsche-930') else 'game-tuned'
            tw = min(card_w-24, 152.)
            th = tw*9/16
            image('garage-v2/car-'+thumbnail+'.png', cx+(card_w-tw)/2, card_y+12, tw, th)
            label(item.name, cx+card_w/2, card_y+th+34, 18 if card_w >= 180 else 16, INK, bold=True, center=True)
            is_cur = item.design_id == vehicle.design_id
            is_open = progress.stars >= item.unlock
            tag = '当前驾驶' if is_cur else '已解锁' if is_open else f'需 {item.unlock} 星'
            tag_color = ORANGE if is_cur else theme.SEA if is_open else theme.LOCKED
            label(tag, cx+card_w/2, card_y+th+56, 14, tag_color, bold=is_cur, center=True)

        current = preview.design_id == vehicle.design_id
        unlocked = current or progress.stars >= car.unlock
        button('当前驾驶' if current else '选择驾驶' if unlocked else f'需 {car.unlock} 星解锁',
               action_x, dock_y+56, action_w, 60, 'garage-select',
               role='primary', primary=True, enabled=unlocked and not current, radius=12)
        label(f'第 {selected+1} / {len(cars)} 辆 · 预览不切换', action_x+action_w/2, dock_y+142, 14, GRAY, center=True)
    else:
        fill(gallery_x, dock_y+20, 4, 22, ORANGE, 2)
        label('车身涂装', gallery_x+14, dock_y+39, 22, INK, bold=True)
        label(f'{car.name}  ·  当前预览：{SKINS[skin_index].name}', gallery_x+124, dock_y+38, 16, GRAY)
        cell_gap = 14.
        cell_w = (gallery_w-(len(SKINS)-1)*cell_gap)/len(SKINS)
        cell_y, cell_h = dock_y+56, 158.
        for index, skin in enumerate(SKINS):
            cx = gallery_x+index*(cell_w+cell_gap)
            active = index == skin_index
            fill(cx-1.5, cell_y-1.5, cell_w+3, cell_h+3, ORANGE if active else LINE, 13)
            button('', cx, cell_y, cell_w, cell_h, 'garage-paint', index,
                   role='category-active' if active else 'category', radius=12)
            if active:
                fill(cx+18, cell_y, cell_w-36, 4, ORANGE, 2)
            image('garage-v2/paint-'+str(index)+'.png', cx+(cell_w-84)/2, cell_y+18, 84, 84)
            label(skin.name, cx+cell_w/2, cell_y+134, 17, ORANGE if active else INK, bold=active, center=True)
        button('应用车身颜色', action_x, dock_y+56, action_w, 58, 'garage-paint-save',
               role='primary', primary=True, radius=12)
        button('恢复原车漆', action_x, dock_y+128, action_w, 42, 'garage-tab', 'paint',
               role='secondary', radius=10)

    # 底部操作条整合在坞内最下沿，干净零遮挡。
    footer_y = dock_y+dock_h-44
    fill(gallery_x, footer_y-8, usable-2*pad, 1, LINE, 0)
    button('←', gallery_x, footer_y, 44, 34, 'garage-orbit', -25, role='secondary', radius=8)
    button('→', gallery_x+52, footer_y, 44, 34, 'garage-orbit', 25, role='secondary', radius=8)
    label('旋转展车视角', gallery_x+108, footer_y+24, 15, GRAY)
    message = notice or progress.notice
    if message:
        line = panel.vehicle_view.base.fit_lines(message, (gallery_w-260)*unit, 15*unit, max_lines=1)
        label(line+('…' if line != message else ''), gallery_x+230, footer_y+24, 15, ORANGE, bold=True)
    back_title = '‹  返回首页' if panel.vehicle_view.base.career_garage_return == 'home' else '‹  返回赛事'
    button(back_title, action_x, footer_y, action_w, 34, 'garage-back', role='footer', radius=8)
    panel.select(panel.primary)


def style(panel):
    for index, button in enumerate(panel.buttons):
        role = panel.garage_roles[index]
        disabled, focused = button['state'] == DGG.DISABLED, index == panel.selected
        transparent = role in ('event-card', 'quiet')
        if role == 'primary':
            color = (.84, .80, .74, 1) if disabled else (theme.ORANGE_BRIGHT if focused else ORANGE)
        elif role == 'tab-active':
            color = theme.CHARCOAL_SOFT if focused else theme.CHARCOAL
        elif role == 'tab':
            color = theme.MIST if focused else (0, 0, 0, 0)
        elif role == 'category-active':
            color = theme.ORANGE_TINT if focused else (.99, .935, .895, 1)
        elif role == 'category':
            color = theme.AMBER_TINT if focused else theme.PAPER_LIGHT
        elif role in ('season-tab-active', 'setup-active'):
            color = theme.CHARCOAL_SOFT if focused else theme.CHARCOAL
        elif role in ('season-tab', 'setup-tab'):
            color = theme.MIST if focused else theme.PAPER_LIGHT
        elif role in ('setup-preset', 'setup-step', 'footer'):
            color = theme.CHARCOAL if focused else theme.MIST
        elif role == 'secondary':
            color = theme.CHARCOAL if focused else theme.PAPER_LIGHT
        elif transparent:
            color = (.88, .33, .16, .10) if focused else (0, 0, 0, 0)
        else:
            color = theme.MIST if focused else theme.PAPER_LIGHT
        button['geom_color'] = color
        if disabled:
            button['text_fg'] = theme.LOCKED
        elif role in ('primary', 'tab-active', 'season-tab-active', 'setup-active') or (
                focused and role in ('secondary', 'footer', 'setup-preset', 'setup-step')):
            button['text_fg'] = WHITE
        elif role in ('tab', 'season-tab', 'setup-tab') and not focused:
            button['text_fg'] = GRAY
        else:
            button['text_fg'] = INK
