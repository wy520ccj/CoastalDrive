"""首页的声音与驾驶辅助构图；复用已有设置动作，不持有设置副本。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from career_garage import garage_cars
from session import Phase
from ui import theme
from ui.lab_widgets import rounded_panel
from ui.main_menu import DARK, GRAY, INK, ORANGE, WHITE


def canvas(cards, app, page, title, subtitle, back):
    cards.active, cards.settings_page, cards.settings_app = True, page, app
    cards.dark = False
    aspect = cards.settings_aspect = app.getAspectRatio()
    width, unit = 941*aspect, 2/941
    margin, panel_width = width*.031, min(620, width*.46)
    cards.root.show()
    app.panel.setScale(1)
    app.panel['frameSize'] = (-aspect, aspect, -1, 1)
    app.panel['frameTexture'], app.panel['frameColor'] = None, (0, 0, 0, 0)
    app.panel_title.hide()
    app.panel_note.hide()
    app.panel_detail.hide()
    app.panel_accent.hide()
    cards.settings_edges, cards.settings_toggles, cards.settings_primary = {}, {}, back

    def point(x, y):
        return (x-width/2)*unit, 1-y*unit

    def box(x, y, w, h):
        a, b = point(x, y+h), point(x+w, y)
        return a[0], b[0], a[1], b[1]

    def fill(x, y, w, h, color, radius=4, parent=None):
        return rounded_panel(cards.content if parent is None else parent, 'settings-fill',
                             box(x, y, w, h), color, radius*unit)

    def text(value, x, y, size=22, color=INK, *, bold=False, right=False):
        label = cards.text(value, *point(x, y), size*unit, color)
        label['font'] = app.ui_font if bold else app.main_menu.regular
        label.textNode.setAlign(TextNode.ARight if right else TextNode.ALeft)
        return label

    def button(index, title, x, y, w, h, *, toggle=None):
        edge = fill(x-2, y-2, w+4, h+4, ORANGE, h/2 if toggle is not None else 4)
        cards.settings_edges[index] = edge
        item = cards.buttons[index]
        item.reparentTo(cards.content)
        item.setScale(1)
        px, pz = point(x+w/2, y+h/2)
        item.setPos(px, 0, pz)
        item['frameSize'], item['frameTexture'] = (-w*unit/2, w*unit/2, -h*unit/2, h*unit/2), None
        item['frameColor'], item['text'] = (0, 0, 0, 0), title
        item['text_font'], item['text_scale'] = app.main_menu.regular, (22 if h < 60 else 24)*unit
        item['text_align'], item['text_pos'] = TextNode.ACenter, (0, -7*unit)
        geom = rounded_panel(cards.content, 'settings-control', item['frameSize'], WHITE,
                             (h/2 if toggle is not None else 4)*unit)
        geom.detachNode()
        item['geom'] = geom
        item.setTransparency(TransparencyAttrib.MAlpha)
        if toggle is not None:
            cards.settings_toggles[index] = toggle
            item['text_pos'] = ((-20 if toggle else 20)*unit, -7*unit)
            center = (w/2-h/2-3) if toggle else (-w/2+h/2+3)
            cards.settings_knobs.append(rounded_panel(item, 'settings-toggle-knob',
                ((center-h/2+5)*unit, (center+h/2-5)*unit, (-h/2+5)*unit, (h/2-5)*unit), WHITE, h/2*unit))
        return item

    bg = DirectFrame(parent=cards.content, frameSize=(-aspect, aspect, -1, 1), frameColor=WHITE,
        frameTexture=app.loader.loadTexture(theme.asset_filename('backgrounds/garage-coastal-v2.png')),
        sortOrder=-10, state=DGG.DISABLED)
    cards.frames.append(bg)
    texture = bg['frameTexture']
    ratio = aspect/(texture.getXSize()/texture.getYSize())
    bg.setTexScale(TextureStage.getDefault(), min(1, ratio), min(1, 1/ratio))
    bg.setTexOffset(TextureStage.getDefault(), max(0, (1-ratio)/2), max(0, (1-1/ratio)/2))
    app.workshop_vehicle.show(cards.content,
        box(margin+panel_width+18, 220, width-2*margin-panel_width-18, 620), app.workspace_vehicle, studio=True)
    app.workshop_vehicle.frame.setTransparency(TransparencyAttrib.MAlpha)
    app.workshop_vehicle.highlight(None)
    fill(0, 0, width, 74, DARK, 0)
    fill(0, 860, width, 81, DARK, 0)
    fill(margin, 122, panel_width, 706, (.98, .98, .99, .96))
    brand = text('COASTAL DRIVE', margin+10, 50, 34, WHITE, bold=True)
    brand['font'] = app.display_font
    if aspect > 1.5:
        text('/  '+title, margin+267, 49, 21, WHITE)
    text(f'★  {app.career_progress.stars} / 18 星', width-350, 49, 23, (1, .75, .31, 1))
    text(f'{app.career_progress.credits} 积分', width-55, 49, 23, WHITE, right=True)
    car = next(item for item in garage_cars(app.workspace_vehicle) if item.design_id == app.workspace_vehicle.design_id)
    text('当前车辆', width-margin-180, 148, 20, WHITE)
    text(car.name, width-margin, 191, 28, WHITE, bold=True, right=True)
    text(title, margin+30, 194, 44, bold=True)
    text(subtitle, margin+30, 234, 21, GRAY)
    text('↑ ↓ 选择    ← → 调整    Enter 确认' if page == 'audio' else '↑ ↓ 选择    Enter 切换',
         margin, 911, 20, WHITE)
    button(back, 'Esc   返回首页' if app.session.phase == Phase.MENU else 'Esc   返回暂停',
           width-220, 881, 181, 44)
    return margin, panel_width, fill, text, button


def audio(cards, app, station):
    margin, width, fill, text, button = canvas(cards, app, 'audio', '声音设置', '三个通道独立调节 · 立即保存', 7)
    left, right = margin+30, margin+width-30
    for index, (title, description, value) in enumerate((
            ('主音量', '整体播放音量', app.audio_settings.master_volume),
            ('效果音', '引擎 · 轮胎 · 环境', app.audio_settings.effects_volume),
            ('车载音乐', '电台与背景音乐', app.audio_settings.music_volume))):
        y = 296+index*146
        text(title, left, y, 28, bold=True)
        text(f'{value}%', right, y, 29, bold=True, right=True)
        text(description, left, y+34, 20, GRAY)
        track_width = width-215
        fill(left, y+58, track_width, 14, (.80, .82, .86, 1), 7)
        if value:
            fill(left, y+58, track_width*value/100, 14, ORANGE, 7)
        for offset, label in enumerate(('−', '+')):
            button(index*2+offset, label, right-118+offset*66, y+33, 52, 52)
        fill(left, y+105, width-60, 1, (.78, .80, .84, 1), 0)
    text('当前电台', left, 750, 20, GRAY)
    name, _, song = station.partition(' · ')
    text(name, left, 786, 28, bold=True)
    if song:
        text(song, left, 810, 15, GRAY)
    button(6, '切换电台  ›', right-160, 752, 160, 48)
    if app.audio_settings.notice:
        text(app.fit_lines(app.audio_settings.notice, (width-60)*2/941, 16*2/941, 1), left, 850, 16, WHITE)
    style(cards, app.panel_selection)


def assists(cards, app):
    margin, width, fill, text, button = canvas(cards, app, 'assists', '驾驶辅助', '下次起步时应用', 3)
    left, right = margin+30, margin+width-30
    for index, (abbreviation, title, description, enabled) in enumerate((
            ('ABS', '制动防抱死', '调节制动压力', app.session.abs_enabled),
            ('TCS', '加速防打滑', '抑制驱动轮空转', app.session.tcs_enabled),
            ('ESC', '车身稳定', '修正车身偏转', app.session.esc_enabled))):
        y = 338+index*163
        fill(left, y-53, width-60, 1, (.78, .80, .84, 1), 0)
        text(abbreviation, left, y+12, 36, bold=True)
        text(title, left+116, y+4, 26, bold=True)
        text(description, left+116, y+41, 20, GRAY)
        button(index, '开启' if enabled else '关闭', right-132, y-18, 132, 54, toggle=enabled)
    fill(left, 777, width-60, 1, (.78, .80, .84, 1), 0)
    text('点击开关切换，Esc 返回。', left, 810, 19, GRAY)
    if app.driving_mode_settings.notice:
        text(app.fit_lines(app.driving_mode_settings.notice, (width-60)*2/941, 16*2/941, 1), left, 850, 16, WHITE)
    style(cards, app.panel_selection)


def style(cards, selected):
    for index, edge in cards.settings_edges.items():
        edge.show() if selected == index else edge.hide()
        button = cards.buttons[index]
        primary = index == cards.settings_primary
        if index in cards.settings_toggles:
            enabled = cards.settings_toggles[index]
            button['geom_color'] = ORANGE if enabled else (.43, .46, .51, 1)
            button['text_fg'] = WHITE
        else:
            button['geom_color'] = ORANGE if primary else (1, .88, .82, 1) if index == selected else (.90, .91, .94, 1)
            button['text_fg'] = WHITE if primary else INK
