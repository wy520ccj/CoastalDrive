"""车库场景菜单的坐标与原生控件；统一 Dark Atelier 深海磨砂玻璃母版。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from career_garage import garage_cars
from session import Phase
from ui import theme
from ui.lab_widgets import rounded_panel
from ui.main_menu import ORANGE, WHITE


def canvas(cards, app, page, title, subtitle, back, *, panel_limit=620, footer=True, car_y=220, car_height=620):
    cards.active, cards.garage_page, cards.garage_app = True, page, app
    cards.dark = True
    aspect = cards.garage_aspect = app.getAspectRatio()
    width, unit = 941*aspect, 2/941
    margin, panel_width = width*.031, min(panel_limit, width*(.355 if panel_limit == 462 else .46))
    cards.root.show()
    app.panel.setScale(1)
    app.panel['frameSize'] = (-aspect, aspect, -1, 1)
    app.panel['frameTexture'], app.panel['frameColor'] = None, (0, 0, 0, 0)
    app.panel_title.hide()
    app.panel_note.hide()
    app.panel_detail.hide()
    app.panel_accent.hide()
    cards.garage_edges, cards.garage_toggles, cards.garage_primary = {}, {}, back
    cards.garage_quiet = set()

    def point(x, y):
        return (x-width/2)*unit, 1-y*unit

    def box(x, y, w, h):
        a, b = point(x, y+h), point(x+w, y)
        return a[0], b[0], a[1], b[1]

    def fill(x, y, w, h, color, radius=4, parent=None):
        node = rounded_panel(cards.content if parent is None else parent, 'menu-fill',
                             box(x, y, w, h), color, radius*unit)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def text(value, x, y, size=22, color=theme.TEXT_LIGHT, *, bold=False, right=False):
        label = cards.text(value, *point(x, y), size*unit, color)
        label['font'] = app.ui_font if bold else app.main_menu.regular
        label.textNode.setAlign(TextNode.ARight if right else TextNode.ALeft)
        return label

    def button(index, title, x, y, w, h, *, toggle=None):
        edge = fill(x-2, y-2, w+4, h+4, ORANGE, h/2 if toggle is not None else 7)
        cards.garage_edges[index] = edge
        item = cards.buttons[index]
        item.reparentTo(cards.content)
        item.setScale(1)
        px, pz = point(x+w/2, y+h/2)
        item.setPos(px, 0, pz)
        item['frameSize'], item['frameTexture'] = (-w*unit/2, w*unit/2, -h*unit/2, h*unit/2), None
        item['frameColor'], item['text'] = (0, 0, 0, 0), title
        item['text_font'], item['text_scale'] = app.main_menu.regular, (21 if h < 60 else 23)*unit
        item['text_align'], item['text_pos'] = TextNode.ACenter, (0, -7*unit)
        geom = rounded_panel(cards.content, 'menu-control', item['frameSize'], WHITE,
                             (h/2 if toggle is not None else 6)*unit)
        geom.detachNode()
        item['geom'] = geom
        item.setTransparency(TransparencyAttrib.MAlpha)
        if toggle is not None:
            cards.garage_toggles[index] = toggle
            item['text_pos'] = ((-20 if toggle else 20)*unit, -7*unit)
            center = (w/2-h/2-3) if toggle else (-w/2+h/2+3)
            cards.garage_knobs.append(rounded_panel(item, 'settings-toggle-knob',
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
        box(margin+panel_width+18, car_y, width-2*margin-panel_width-18, car_height), app.workspace_vehicle, studio=True)
    app.workshop_vehicle.frame.setTransparency(TransparencyAttrib.MAlpha)
    app.workshop_vehicle.highlight(None)

    fill(0, 0, width, 74, theme.SLATE_BAR, 0)
    fill(0, 72, width*.34, 3, ORANGE, 0)
    fill(width*.34, 72, width*.33, 3, theme.AMBER, 0)
    fill(width*.67, 72, width*.33, 3, theme.SEA, 0)
    fill(0, 860, width, 81, theme.SLATE_BAR, 0)
    fill(0, 859, width, 1.5, theme.HAIRLINE, 0)

    # 左侧 Dark Atelier 磨砂主卡。
    fill(margin-1, 113, panel_width+2, 718, theme.SLATE_BORDER, 13)
    fill(margin, 114, panel_width, 716, theme.SLATE_GLASS, 12)
    fill(margin+28, 144, 4, 38, ORANGE, 2)

    brand = text('COASTAL DRIVE', margin, 49, 32, theme.TEXT_LIGHT, bold=True)
    brand['font'] = app.display_font
    if aspect > 1.5:
        fill(margin+254, 22, 2, 30, ORANGE, 1)
        text(title, margin+274, 48, 22, theme.TEXT_SUB)
    text(f'★  {app.career_progress.stars} / 18 星', width-margin, 48, 22, theme.GOLD, bold=True, right=True)

    # 右上角车辆暗玻璃铭牌。
    car = next(item for item in garage_cars(app.workspace_vehicle) if item.design_id == app.workspace_vehicle.design_id)
    badge_w = 300
    bx = width-margin-badge_w
    fill(bx-1, 113, badge_w+2, 82, theme.SLATE_BORDER, 11)
    fill(bx, 114, badge_w, 80, theme.SLATE_GLASS, 10)
    fill(bx+badge_w-4, 126, 4, 56, ORANGE, 2)
    text('当前车辆', width-margin-18, 144, 16, theme.TEXT_SUB, right=True)
    text(car.name, width-margin-18, 180, 25, theme.TEXT_LIGHT, bold=True, right=True)

    text(title, margin+46, 178, 40, theme.TEXT_LIGHT, bold=True)
    text(subtitle, margin+30, 220, 19, theme.TEXT_SUB)
    if footer:
        text('↑ ↓ 选择    ← → 调整    Enter 确认' if page == 'audio' else '↑ ↓ 选择    Enter 切换',
             margin, 910, 19, theme.TEXT_SUB)
        button(back, 'Esc  返回首页' if app.session.phase == Phase.MENU else 'Esc  返回暂停',
               width-margin-184, 880, 184, 44)
    return margin, panel_width, fill, text, button


def style(cards, selected):
    for index, edge in cards.garage_edges.items():
        edge.show() if selected == index else edge.hide()
        button = cards.buttons[index]
        primary = index == cards.garage_primary
        if index in cards.garage_toggles:
            enabled = cards.garage_toggles[index]
            button['geom_color'] = ORANGE if enabled else (.76, .78, .82, 1)
            button['text_fg'] = WHITE
        elif index in cards.garage_quiet:
            button['geom_color'] = theme.CHARCOAL if index == selected else theme.MIST
            button['text_fg'] = WHITE if index == selected else theme.INK
        else:
            button['geom_color'] = (theme.ORANGE_BRIGHT if index == selected else ORANGE) if primary else (
                theme.CHARCOAL if index == selected else theme.MIST)
            button['text_fg'] = WHITE if (primary or index == selected) else theme.INK
