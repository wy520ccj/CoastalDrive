"""车库三页与共享按钮样式；Dark Atelier 深海玻璃母版，车辆展台通透居中。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from skins import SKINS
from ui import theme
from ui.lab_widgets import rounded_panel

INK = (.055, .075, .13, 1)
GRAY = (.36, .39, .45, 1)
WHITE = (1, 1, 1, 1)
ORANGE = theme.ORANGE
LINE = (.79, .81, .84, 1)


def show(panel, progress, vehicle, notice, tab, preview, skin_index, cars):
    aspect = panel.vehicle_view.base.getAspectRatio()
    panel.garage_aspect = aspect
    panel.garage_roles = {}
    panel.garage_values = {}
    height, width = 941., 941.*aspect
    unit = 2/height
    left, top, wide = width*.031, 114., min(462., width*.295)
    inset, inner = 24., wide-48.

    def point(x, y):
        return (x-width/2)*unit, 1-y*unit

    def box(x, y, w, h):
        a, b = point(x, y+h), point(x+w, y)
        return a[0], b[0], a[1], b[1]

    def fill(x, y, w, h, color, radius=4):
        node = rounded_panel(panel.content, 'garage-fill', box(x, y, w, h), color, radius*unit)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def label(text, x, y, size=18, color=theme.TEXT_LIGHT, bold=False, right=False, wrap=None):
        p = point(x, y)
        item = panel.label(text, *p, size*unit, color, font=panel.font if bold else panel.garage_font)
        if right:
            item.textNode.setAlign(TextNode.ARight)
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

    def button(text, x, y, w, h, command, value=None, *, role='plain', enabled=True, primary=False):
        px, pz = point(x+w/2, y+h/2)
        item = panel.button(text, px, pz, w*unit, h*unit, command, value,
                            enabled=enabled, primary=primary, radius=6*unit)
        item['text_font'] = panel.garage_font
        item['text_scale'] = (23 if role in ('primary', 'tab', 'tab-active') else 20)*unit
        if role in ('primary', 'tab-active'):
            item['text_font'] = panel.font
        item['text_pos'] = (0, -7*unit)
        item.setTransparency(TransparencyAttrib.MAlpha)
        panel.garage_roles[len(panel.buttons)-1] = role
        return item

    image('backgrounds/garage-coastal-v2.png', 0, 0, width, height)
    background = panel.frames[-1]
    texture = panel.garage_textures['backgrounds/garage-coastal-v2.png']
    ratio = aspect/(texture.getXSize()/texture.getYSize())
    background.setTexScale(TextureStage.getDefault(), ratio, 1)
    background.setTexOffset(TextureStage.getDefault(), (1-ratio)/2, 0)

    # 车模只在操作面板右侧取景，背景独立铺满画面。
    preview = vehicle if preview is None or tab != 'cars' else preview
    view_left, view_top = left+wide+18, 250.
    view_right, view_bottom = width-40, 824.
    panel.vehicle_view.show(panel.content, box(view_left, view_top, view_right-view_left, view_bottom-view_top),
                            preview, studio=True, skin_index=skin_index)
    panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
    panel.vehicle_view.highlight(None)

    # 顶栏与底栏统一 Dark Atelier 深海通栏。
    fill(0, 0, width, 74, theme.SLATE_BAR, 0)
    fill(0, 74, width, 1.5, theme.SLATE_BORDER, 0)
    fill(0, 860, width, 81, theme.SLATE_BAR, 0)
    fill(0, 859, width, 1.5, theme.SLATE_BORDER, 0)

    brand = label('COASTAL DRIVE', width*.031, 49, 32 if aspect > 1.5 else 26, theme.TEXT_LIGHT, True)
    brand['font'] = panel.garage_display_font
    if aspect > 1.6:
        fill(width*.031+254, 22, 2, 30, ORANGE, 1)
        label('海岸车库', width*.031+274, 48, 22, theme.TEXT_SUB)
    nav_width = 134 if aspect > 1.5 else 110
    for i, (key, title) in enumerate((('cars', '我的车辆'), ('upgrade', '挑战改装'), ('paint', '车身颜色'), ('setup', '专家参数'))):
        x = width*(.36+i*.098)-nav_width/2
        button(title, x, 12, nav_width, 50, 'garage-tab', key, role='tab-active' if key == tab else 'tab')
        if key == tab:
            fill(x+14, 62, nav_width-28, 3, ORANGE, 1.5)
    label(f'★  {progress.stars} / 18 星', width-left, 48, 22 if aspect > 1.5 else 18, theme.GOLD, True, right=True)

    # 左侧深海磨砂操作卡（不再贴刺眼白板）。
    fill(left-1, top-1, wide+2, 718, theme.SLATE_BORDER, 13)
    fill(left, top, wide, 716, theme.SLATE_GLASS, 12)
    fill(left+inset, top+26, 4, 34, ORANGE, 2)
    titles = {'cars': '我的车辆', 'paint': '车身颜色'}
    label(titles[tab], left+inset+16, top+54, 36, theme.TEXT_LIGHT, bold=True)

    # 右上角车辆参数暗玻璃铭牌（在明亮海天背景上清晰锐利）。
    car = next(item for item in cars if item.design_id == preview.design_id)
    config = preview.config
    power = max(rpm*torque/9549.3 for rpm, torque in config.torque_curve)
    if tab in ('cars', 'paint'):
        badge_w = 340
        bx = width-left-badge_w
        fill(bx-1, 113, badge_w+2, 82, theme.SLATE_BORDER, 11)
        fill(bx, 114, badge_w, 80, theme.SLATE_GLASS, 10)
        fill(bx+badge_w-4, 126, 4, 56, ORANGE, 2)
        label(car.name, width-left-18, 148, 25, theme.TEXT_LIGHT, True, right=True)
        tuning = '项目调校 · ' if preview.design_id in ('game-tuned', 'coastal-hatch', 'coastal-roadster', 'club-coupe', 'subaru-wrx-sti', 'porsche-930') else ''
        label(f'{tuning}{power:.0f} kW  /  {config.mass:.0f} kg', width-left-18, 180, 17, theme.TEXT_SUB, right=True)

    if tab == 'cars':
        count = sum(progress.stars >= item.unlock or item.design_id == vehicle.design_id for item in cars)
        label(f'已解锁 {count} / {len(cars)} 辆', left+inset, top+92, 18, theme.TEXT_SUB)
        selected = next(i for i, item in enumerate(cars) if item.design_id == preview.design_id)
        first = min(max(0, selected-2), max(0, len(cars)-4))
        for index, item in enumerate(cars[first:first+4]):
            x, y = left+inset, top+116+index*100
            active = item.design_id == preview.design_id
            fill(x-1, y-1, inner+2, 92, ORANGE if active else theme.SLATE_BORDER, 9)
            button('', x, y, inner, 90, 'garage-car', item.design_id, role='category-active' if active else 'category')
            if active:
                fill(x, y+10, 4, 70, ORANGE, 2)
            # 工程存档沿用其实际经典双门外观，不用虚构缩略图。
            thumbnail = item.design_id if item.design_id in ('game-tuned', 'coastal-hatch', 'coastal-roadster',
                'gr86-2022-premium-6mt', 'coastal-gt', 'club-coupe', 'subaru-wrx-sti', 'porsche-930') else 'game-tuned'
            thumbnail_width = min(132., inner*.34)
            thumbnail_height = thumbnail_width*9/16
            text_offset = thumbnail_width+18
            image('garage-v2/car-'+thumbnail+'.png', x+10, y+(90-thumbnail_height)/2,
                  thumbnail_width, thumbnail_height)
            label(item.name, x+text_offset, y+35, 21 if inner >= 360 else 19, theme.TEXT_LIGHT, bold=True)
            is_cur = item.design_id == vehicle.design_id
            is_open = progress.stars >= item.unlock
            tag = '当前驾驶' if is_cur else '已解锁' if is_open else f'需 {item.unlock} 星解锁'
            tag_color = ORANGE if is_cur else (theme.SEA if is_open else theme.TEXT_LOCKED)
            label(tag, x+text_offset, y+65, 16, tag_color)
        if len(cars) > 4:
            button('‹', left+inset, top+526, 46, 36, 'garage-car', cars[(selected-1) % len(cars)].design_id, role='secondary')
            label(f'{selected+1} / {len(cars)}', left+wide/2-20, top+551, 17, theme.TEXT_SUB)
            button('›', left+wide-inset-46, top+526, 46, 36, 'garage-car', cars[(selected+1) % len(cars)].design_id, role='secondary')
        current = preview.design_id == vehicle.design_id
        unlocked = current or progress.stars >= car.unlock
        button('当前驾驶' if current else '选择驾驶' if unlocked else f'获得 {car.unlock} 星解锁',
               left+inset, top+588, inner, 58, 'garage-select', role='primary', primary=True, enabled=unlocked and not current)
        label('预览不会更换当前驾驶车辆', left+inset, top+676, 16, theme.TEXT_SUB)
    else:
        label(car.name+' · 涂装预览', left+inset, top+92, 18, theme.TEXT_SUB)
        fill(left+inset-1, top+113, inner+2, 178, theme.SLATE_BORDER, 9)
        fill(left+inset, top+114, inner, 176, theme.SLATE_CARD, 8)
        image('garage-v2/paint-'+str(skin_index)+'.png', left+inset+12, top+120, 162, 162)
        label(SKINS[skin_index].name, left+inset+192, top+196, 26, theme.TEXT_LIGHT, bold=True)
        label('当前预览色漆', left+inset+192, top+228, 16, theme.TEXT_SUB)
        cell = inner/3
        for index, skin in enumerate(SKINS):
            x, y = left+inset+(index % 3)*cell, top+310+(index//3)*118
            active = index == skin_index
            fill(x-1, y-1, cell-6, 110, ORANGE if active else theme.SLATE_BORDER, 9)
            button('', x, y, cell-8, 108, 'garage-paint', index,
                   role='category-active' if active else 'category')
            image('garage-v2/paint-'+str(index)+'.png', x+(cell-8)/2-33, y+6, 66, 66)
            label(skin.name, x+(cell-8)/2-28, y+95, 17, ORANGE if active else theme.TEXT_LIGHT)
        button('应用车身颜色', left+inset, top+572, inner, 56, 'garage-paint-save', role='primary', primary=True)
        button('恢复当前车漆', left+inset, top+642, inner, 38, 'garage-tab', 'paint', role='secondary')

    # 通知只占面板与底栏之间的一条状态位，不覆盖车辆。
    message = notice or progress.notice
    if message:
        message_width = width-2*left if tab == 'setup' else wide
        fill(left, 834, message_width, 24, theme.SLATE_BAR, 4)
        line = panel.vehicle_view.base.fit_lines(message, (message_width-32)*unit, 15*unit, max_lines=1)
        label(line+('…' if line != message else ''), left+16, 850, 15, theme.GOLD)

    button('Enter  确认', width*.031, 880, 145, 42, 'garage-confirm', role='footer')
    button('Esc  返回', width*.13, 880, 130, 42, 'garage-back', role='footer')
    if tab in ('cars', 'paint'):
        button('←', width*.43, 880, 46, 42, 'garage-orbit', -25, role='secondary')
        button('→', width*.475, 880, 46, 42, 'garage-orbit', 25, role='secondary')
        label('旋转视角', width*.52, 910, 19, theme.TEXT_SUB)
    back_title = '返回首页' if panel.vehicle_view.base.career_garage_return == 'home' else '返回赛事'
    button(back_title, width-left-140, 880, 140, 42, 'garage-back', role='footer')
    panel.select(panel.primary)


def style(panel):
    for index, button in enumerate(panel.buttons):
        role = panel.garage_roles[index]
        disabled, focused = button['state'] == DGG.DISABLED, index == panel.selected
        transparent = role in ('tab', 'tab-active', 'footer', 'quiet', 'event-card')
        if role == 'primary':
            color = (.22, .27, .34, 1) if disabled else (theme.ORANGE_BRIGHT if focused else ORANGE)
        elif role == 'category-active':
            color = (.24, .18, .17, .96) if focused else (.18, .15, .16, .92)
        elif role in ('season-tab', 'setup-tab'):
            color = theme.SLATE_CARD if focused else (.07, .10, .14, .78)
        elif role == 'setup-step':
            color = theme.SLATE_CARD_HI if focused else (.11, .16, .22, .95)
        elif transparent:
            color = (1, 1, 1, .12) if focused else (0, 0, 0, 0)
        else:
            color = theme.SLATE_CARD_HI if focused else theme.SLATE_CARD
        button['geom_color'] = color
        if disabled:
            button['text_fg'] = theme.TEXT_LOCKED
        elif role in ('season-tab', 'setup-tab', 'tab') and not focused:
            button['text_fg'] = theme.TEXT_SUB
        elif role == 'tab-active':
            button['text_fg'] = theme.TEXT_LIGHT
        else:
            button['text_fg'] = theme.TEXT_LIGHT
