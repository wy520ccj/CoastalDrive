"""落日黑曜石与琥珀金风格车库场景菜单母版：哑光黑曜石细描边 + 琥珀金焦点 + 冷静钢蓝 PI 徽标。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from career_garage import garage_cars
from session import Phase
from ui import atelier, theme
from ui.lab_widgets import gradient_panel, rounded_panel
from ui.main_menu import WHITE


def canvas(cards, app, page, title, subtitle, back, *, panel_limit=620, footer=True, car_y=210, car_height=620):
    cards.active, cards.garage_page, cards.garage_app = True, page, app
    cards.dark = True
    aspect = cards.garage_aspect = app.getAspectRatio()
    width, unit = 941*aspect, 2/941
    margin, panel_width = width*.028, min(panel_limit, width*(.355 if panel_limit == 462 else .46))
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

    def fill(x, y, w, h, color, radius=6, parent=None):
        node = rounded_panel(cards.content if parent is None else parent, 'menu-fill',
                             box(x, y, w, h), color, radius*unit)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def text(value, x, y, size=22, color=theme.TEXT_LIGHT, *, bold=False, right=False, display=False):
        label = cards.text(value, *point(x, y), size*unit, color)
        label['font'] = app.display_font if display else app.ui_font if bold else app.main_menu.regular
        label.textNode.setAlign(TextNode.ARight if right else TextNode.ALeft)
        return label

    def button(index, title, x, y, w, h, *, toggle=None):
        rad = h/2 if toggle is not None else 6
        if toggle is not None:
            fill(x-1, y-1, w+2, h+2, theme.CARBON_EDGE, rad+1)
            edge = fill(x-1.8, y-1.8, w+3.6, h+3.6, theme.AMBER, rad+1.5)
        else:
            edge = fill(x, y, 0.1, 0.1, (0, 0, 0, 0), 0)
        cards.garage_edges[index] = edge
        item = cards.buttons[index]
        item.reparentTo(cards.content)
        item.setScale(1)
        px, pz = point(x+w/2, y+h/2)
        item.setPos(px, 0, pz)
        item['frameSize'], item['frameTexture'] = (-w*unit/2, w*unit/2, -h*unit/2, h*unit/2), None
        item['frameColor'], item['text'] = (0, 0, 0, 0), title
        item['text_font'], item['text_scale'] = app.main_menu.regular, (19 if h < 60 else 21)*unit
        item['text_align'], item['text_pos'] = TextNode.ACenter, (0, -7*unit)
        if toggle is not None:
            geom = rounded_panel(cards.content, 'menu-control', item['frameSize'], WHITE, rad*unit)
            geom.detachNode()
            item['geom'] = geom
            cards.garage_toggles[index] = toggle
            item['text_pos'] = ((-20 if toggle else 20)*unit, -7*unit)
            center = (w/2-h/2-3) if toggle else (-w/2+h/2+3)
            knob_col = theme.INK if toggle else WHITE
            cards.garage_knobs.append(rounded_panel(item, 'settings-toggle-knob',
                ((center-h/2+5)*unit, (center+h/2-5)*unit, (-h/2+5)*unit, (h/2-5)*unit), knob_col, h/2*unit))
        else:
            item['geom'] = None
        item.setTransparency(TransparencyAttrib.MAlpha)
        return item

    bg = DirectFrame(parent=cards.content, frameSize=(-aspect, aspect, -1, 1), frameColor=WHITE,
        frameTexture=atelier.tex(app.loader, atelier.SUNSET_GARAGE_BG),
        sortOrder=-10, state=DGG.DISABLED)
    cards.frames.append(bg)
    texture = bg['frameTexture']
    ratio = aspect/(texture.getXSize()/texture.getYSize())
    bg.setTexScale(TextureStage.getDefault(), min(1, ratio), min(1, 1/ratio))
    bg.setTexOffset(TextureStage.getDefault(), max(0, (1-ratio)/2), max(0, (1-1/ratio)/2))
    gradient_panel(cards.content, 'menu-scrim', box(0, 0, width*0.56, 941),
                   (0.040, 0.050, 0.072, 0.78), (0.040, 0.050, 0.072, 0.0), horizontal=True)
    gradient_panel(cards.content, 'menu-top-scrim', box(0, 0, width, 118),
                   (0.03, 0.04, 0.06, 0.0), (0.03, 0.04, 0.06, 0.72))
    gradient_panel(cards.content, 'menu-bot-scrim', box(0, 740, width, 201),
                   (0.03, 0.04, 0.06, 0.76), (0.03, 0.04, 0.06, 0.0))

    # 3D 展车底部暖金落日地面反光（位于展车视口下方，消除悬浮感）。
    stage_x = margin+panel_width+18
    stage_w = width-2*margin-panel_width-18
    bounce_h = min(260., car_height*0.48)
    cards.frames.append(atelier.picture(
        cards.content, app.loader, 'atelier/floor-warm-bounce.png',
        box(stage_x-24, car_y+car_height-bounce_h+34, stage_w+48, bounce_h),
        color=(1, 0.90, 0.74, 0.80), sort_order=-2))
    app.workshop_vehicle.show(cards.content,
        box(stage_x, car_y, stage_w, car_height), app.workspace_vehicle, studio=True)
    app.workshop_vehicle.frame.setTransparency(TransparencyAttrib.MAlpha)
    app.workshop_vehicle.highlight(None)

    # 顶底拉丝黑曜石通栏（与生涯/调校界面完全统一）。
    cards.frames.append(atelier.picture(cards.content, app.loader, 'atelier/bar-top.png', box(0, 0, width, 72)))
    cards.frames.append(atelier.picture(cards.content, app.loader, 'atelier/footer-surface.png', box(0, 858, width, 83)))

    # 左侧微颗粒黑曜石悬浮主卡。
    cards.frames.append(atelier.picture(cards.content, app.loader, 'atelier/panel-obsidian.png',
                                        box(margin-10, 86, panel_width+20, 756)))
    fill(margin+10, 114, 4, 42, theme.AMBER, 2)

    cards.frames.append(atelier.wordmark(cards.content, app.loader, box(margin, 15, 212, 40)))
    if aspect > 1.5:
        fill(margin+228, 21, 1.5, 28, (0.34, 0.40, 0.50, 0.85), 0)
        text(title, margin+246, 44, 20, WHITE, bold=True)
        fill(margin+246, 67, 76, 3, theme.AMBER, 1.5)
    star_w = 152
    cards.frames.append(atelier.picture(cards.content, app.loader, 'atelier/btn-ghost.png',
                                        box(width-margin-star_w, 15, star_w, 42)))
    star_lbl = text(f'★  {app.career_progress.stars} / 18 星', width-margin-star_w/2, 42, 17, theme.AMBER, bold=True)
    star_lbl.textNode.setAlign(TextNode.ACenter)

    # 右上角黑曜石微光卡片 + 钢蓝 PI 性能铭牌。
    car = next(item for item in garage_cars(app.workspace_vehicle) if item.design_id == app.workspace_vehicle.design_id)
    letter, score, _pi_color, power_kw, _ = theme.vehicle_pi(app.workspace_vehicle.config)
    badge_w = 344
    bx = width-margin-badge_w
    cards.frames.append(atelier.picture(cards.content, app.loader, 'atelier/card-idle.png',
                                        box(bx-8, 88, badge_w+16, 102)))
    fill(bx+8, 115, 3.5, 48, theme.AMBER, 2)
    fill(bx+22, 125, 84, 28, theme.STEEL_BG, 5)
    lbl_pi = text(f'{letter} {score}', bx+64, 145, 16, theme.STEEL_TEXT, bold=True, display=True)
    lbl_pi.textNode.setAlign(TextNode.ACenter)
    text(car.name, width-margin-18, 135, 22, WHITE, bold=True, right=True)
    text(f'{power_kw:.0f} kW  |  {app.workspace_vehicle.config.mass:.0f} kg',
         width-margin-18, 165, 15, theme.DARK_SUB, right=True)

    text(title, margin+28, 158, 36, WHITE, bold=True)
    text(subtitle, margin+28, 198, 17, theme.DARK_SUB)
    if footer:
        text('↑ ↓ 选择    ← → 调整    Enter 确认' if page == 'audio' else '↑ ↓ 选择    Enter 切换',
             margin, 908, 17, theme.DARK_SUB)
        button(back, 'Esc  返回首页' if app.session.phase == Phase.MENU else 'Esc  返回暂停',
               width-margin-184, 878, 184, 44)
    return margin, panel_width, fill, text, button


def style(cards, selected):
    loader = cards.garage_app.loader
    for index, edge in cards.garage_edges.items():
        edge.show() if selected == index else edge.hide()
        button = cards.buttons[index]
        primary = index == cards.garage_primary
        focused = index == selected
        if index in cards.garage_toggles:
            enabled = cards.garage_toggles[index]
            button['geom_color'] = (theme.AMBER_BRIGHT if focused else theme.AMBER) if enabled else (
                theme.CHARCOAL_SOFT if focused else (0.17, 0.20, 0.26, 1))
            button['text_fg'] = theme.INK if enabled else WHITE
        elif index in cards.garage_quiet:
            button['frameTexture'] = atelier.tex(loader, 'atelier/btn-ghost-hover.png' if focused else 'atelier/btn-ghost.png')
            button['frameColor'] = (1, 1, 1, 1)
            button['text_fg'] = theme.AMBER if focused else WHITE
        elif primary:
            button['frameTexture'] = atelier.tex(loader, 'atelier/btn-primary-hover.png' if focused else 'atelier/btn-primary.png')
            button['frameColor'] = (1, 1, 1, 1)
            button['text_fg'] = theme.INK
        else:
            button['frameTexture'] = atelier.tex(loader, 'atelier/card-active.png' if focused else 'atelier/btn-ghost.png')
            button['frameColor'] = (1, 1, 1, 1)
            button['text_fg'] = theme.AMBER if focused else WHITE
