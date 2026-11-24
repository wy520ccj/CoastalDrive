"""落日海岸工坊车库：1:1 复刻参考图右侧通高黑曜石面板 + 左侧全高落日车库 3D 展台 + 底部序号进度栏。"""

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode, TextureStage, TransparencyAttrib

from skins import SKINS
from ui import atelier, theme
from ui.lab_widgets import gradient_panel, rounded_panel
from vehicle_designs import vehicle_design

INK = theme.INK
GRAY = theme.DARK_SUB
WHITE = theme.WHITE
ORANGE = theme.AMBER
LINE = theme.CARBON_EDGE


def show(panel, progress, vehicle, notice, tab, preview, skin_index, cars):
    aspect = panel.vehicle_view.base.getAspectRatio()
    panel.garage_aspect = aspect
    panel.garage_roles = {}
    panel.garage_values = {}
    panel.atelier_btn_tex = {}
    panel.atelier_radios = {}
    height, width = 941., 941.*aspect
    unit = 2/height
    dock_w = min(492., max(390., width * 0.295))
    stage_w = width - dock_w
    foot_y = 858.

    def point(x, y):
        return (x-width/2)*unit, 1-y*unit

    def box(x, y, w, h):
        a, b = point(x, y+h), point(x+w, y)
        return a[0], b[0], a[1], b[1]

    def fill(x, y, w, h, color, radius=6):
        node = rounded_panel(panel.content, 'garage-fill', box(x, y, w, h), color, radius*unit)
        node.setTransparency(TransparencyAttrib.MAlpha)
        return node

    def label(text, x, y, size=18, color=WHITE, bold=False, right=False, center=False, wrap=None, display=False):
        p = point(x, y)
        font = panel.garage_display_font if display else panel.font if bold else panel.garage_font
        item = panel.label(text, *p, size*unit, color, font=font)
        if right:
            item.textNode.setAlign(TextNode.ARight)
        elif center:
            item.textNode.setAlign(TextNode.ACenter)
        if wrap is not None:
            item.textNode.setWordwrap(wrap/size)
        return item

    def image(name, x, y, w, h, color=WHITE, crop=False, sort_order=0):
        frame = atelier.picture(panel.content, panel.loader, name, box(x, y, w, h),
                                color=color, crop=crop, sort_order=sort_order)
        panel.frames.append(frame)
        return frame

    def button(text, x, y, w, h, command, value=None, *, role='plain', enabled=True, primary=False,
               radius=6, tex_idle=None, tex_focus=None, text_pos=(0, -6)):
        px, pz = point(x+w/2, y+h/2)
        item = panel.button(text, px, pz, w*unit, h*unit, command, value,
                            enabled=enabled, primary=primary, radius=radius*unit)
        item['text_font'] = panel.font if role in ('primary', 'tab-active') else panel.garage_font
        item['text_scale'] = (19 if role == 'primary' else 17)*unit
        item['text_pos'] = (text_pos[0]*unit, text_pos[1]*unit)
        item.setTransparency(TransparencyAttrib.MAlpha)
        idx = len(panel.buttons)-1
        panel.garage_roles[idx] = role
        if tex_idle is not None:
            item['geom'] = None
            item['frameTexture'] = atelier.tex(panel.loader, tex_idle)
            item['frameColor'] = (1, 1, 1, 1) if enabled else (0.55, 0.58, 0.64, 0.72)
            panel.atelier_btn_tex[idx] = (tex_idle, tex_focus or tex_idle)
        return item

    # 全屏落日海岸工坊实景图（无车空展台，3D 车模自然落于反光水泥地）。
    bg = DirectFrame(parent=panel.content, frameSize=box(0, 0, width, height),
                     frameTexture=atelier.tex(panel.loader, atelier.SUNSET_GARAGE_BG),
                     frameColor=(1, 1, 1, 1), state=DGG.DISABLED)
    texture = bg['frameTexture']
    ratio = aspect/(texture.getXSize()/texture.getYSize())
    bg.setTexScale(TextureStage.getDefault(), min(1, ratio), min(1, 1/ratio))
    bg.setTexOffset(TextureStage.getDefault(), max(0, (1-ratio)/2), max(0, (1-1/ratio)/2))
    panel.frames.append(bg)

    gradient_panel(panel.content, 'g-top-scrim', box(0, 0, stage_w, 120),
                   (0.03, 0.04, 0.06, 0.0), (0.03, 0.04, 0.06, 0.78))
    gradient_panel(panel.content, 'g-bot-scrim', box(0, 680, stage_w, foot_y-680),
                   (0.03, 0.04, 0.06, 0.86), (0.03, 0.04, 0.06, 0.0))

    # 车底暖金落日地面反光与环境接地暗晕（与首页完全一致，位于 3D 展车下方）。
    image('atelier/floor-warm-bounce.png', 135, 498, stage_w - 175, 230, sort_order=-2)

    # 3D 展车与首页保持同一落地透视高度，且与顶部页签、左缘旋转键、右栏面板、底部进度条严格零重叠。
    preview = vehicle if preview is None or tab != 'cars' else preview
    panel.vehicle_view.show(panel.content, box(178., 158., stage_w-196., 560.),
                            preview, studio=True, skin_index=skin_index)
    panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
    panel.vehicle_view.highlight(None)

    # ── 左上角：真实手刷 COASTAL DRIVE 透明标识图 + 副标题 ──
    image(atelier.WORDMARK_BRUSH, 34, 18, 246, 46, color=(0.96, 0.97, 0.99, 1))
    label('海岸车库', 38, 82, 16, (0.80, 0.84, 0.90, 0.92))

    # ── 顶部中部磨砂深色玻璃导览条 + 平铺无框分页（与首页完全统一）──
    tabs = (('cars', '我的车辆'), ('upgrade', '挑战改装'), ('paint', '车身颜色'), ('setup', '专家参数'))
    nav_w = 114 if aspect > 1.5 else 88
    nav_gap = 12 if aspect > 1.5 else 6
    nav_x = 326. if aspect > 1.5 else 292.
    nav_span = len(tabs) * nav_w + (len(tabs) - 1) * nav_gap
    image('atelier/top-nav-glass.png', nav_x - 42, 0, nav_span + 84, 74)
    for i, (key, title) in enumerate(tabs):
        tx = nav_x+i*(nav_w+nav_gap)
        active = key == tab
        button(title, tx, 18, nav_w, 46, 'garage-tab', key,
               role='tab-active' if active else 'tab', radius=4)
        if active:
            fill(tx+14, 70, nav_w-28, 3, theme.AMBER, 1.5)

    # ── 左缘悬浮磨砂玻璃视角旋转键（与首页左缘页签同尺寸同材质）──
    button('←  左转视角', 0, 148, 166, 66, 'garage-orbit', -25, role='secondary',
           tex_idle='atelier/left-tab-idle.png', tex_focus='atelier/left-tab-active.png')
    button('→  右转视角', 0, 226, 166, 66, 'garage-orbit', 25, role='secondary',
           tex_idle='atelier/left-tab-idle.png', tex_focus='atelier/left-tab-active.png')

    # ── 左下角磨砂深色当前预览车辆信息卡 + 真实 Cycles 车模微缩图（与首页左下角 1:1 统一）──
    car = next(item for item in cars if item.design_id == preview.design_id)
    letter, score, _, power_kw, _ = theme.vehicle_pi(preview.config)
    strip_x = max(42., width * 0.028)
    card_x = strip_x - 18.
    card_w = min(544., stage_w - card_x - 24)
    image('atelier/car-strip-glass.png', card_x, 738, card_w, 110)
    label('当前预览车辆', strip_x, 766, 13.5, GRAY)
    fill(strip_x+98, 750, 64, 21, theme.STEEL_BG, 4)
    label(f'{letter} {score}', strip_x+130, 765, 13.5, theme.STEEL_TEXT, bold=True, center=True, display=True)
    label(car.name, strip_x, 804, 26, WHITE, bold=True)
    tuning = '项目调校  |  ' if preview.design_id in (
        'game-tuned', 'coastal-hatch', 'coastal-roadster', 'club-coupe', 'subaru-wrx-sti', 'porsche-930') else ''
    label(f'{tuning}{power_kw:.0f} kW  |  {preview.config.mass:.0f} kg  |  {car.category}',
          strip_x, 833, 14.5, GRAY)
    preview_thumb = preview.design_id if preview.design_id in (
        'game-tuned', 'coastal-hatch', 'coastal-roadster', 'gr86-2022-premium-6mt',
        'coastal-gt', 'club-coupe', 'subaru-wrx-sti', 'porsche-930') else 'game-tuned'
    image('garage-v2/car-'+preview_thumb+'.png', card_x + card_w - 186, 744, 168, 92,
          color=(0.94, 0.90, 0.84, 0.96))

    # ── 右侧 29.5% 通高拉丝哑光黑曜石面板（自带向左投射柔和环境阴影，与首页 1:1 统一）──
    image('atelier/dock-surface.png', stage_w - 34, 0, dock_w + 34, foot_y)
    fill(stage_w, 74, dock_w, 1.2, (0.20, 0.24, 0.31, 0.85), 0)

    right_pad = max(28., width * 0.028)
    back_title = '返回首页  ›' if panel.vehicle_view.base.career_garage_return == 'home' else '返回赛事  ›'
    button(back_title, width-right_pad-164, 15, 164, 44, 'garage-back', role='footer',
           tex_idle='atelier/btn-ghost.png', tex_focus='atelier/btn-ghost-hover.png')

    rx = stage_w + 28.
    rw = dock_w - 28. - right_pad

    if tab == 'cars':
        count = sum(progress.stars >= item.unlock or item.design_id == vehicle.design_id for item in cars)
        label('海岸车库  /  我的车辆', rx, 112, 13.5, GRAY)
        label(f'★ {progress.stars} / 18', rx + rw, 112, 13.5, theme.AMBER, bold=True, right=True)
        label('选择车辆', rx, 152, 30, WHITE, bold=True)
        label(f'已解锁 {count} / {len(cars)} 辆，点击预览实车效果。', rx, 182, 14.5, GRAY)

        selected = next(i for i, item in enumerate(cars) if item.design_id == preview.design_id)
        first = min(max(0, selected-1), max(0, len(cars)-4))
        card_h, card_gap = 88., 11.
        for index, item in enumerate(cars[first:first+4]):
            cy = 204. + index * (card_h + card_gap)
            active = item.design_id == preview.design_id
            is_cur = item.design_id == vehicle.design_id
            is_open = progress.stars >= item.unlock
            button('', rx, cy, rw, card_h, 'garage-car', item.design_id,
                   role='category-active' if active else 'category',
                   tex_idle='atelier/card-active.png' if active else 'atelier/card-idle.png',
                   tex_focus='atelier/card-active.png')
            thumbnail = item.design_id if item.design_id in ('game-tuned', 'coastal-hatch', 'coastal-roadster',
                'gr86-2022-premium-6mt', 'coastal-gt', 'club-coupe', 'subaru-wrx-sti', 'porsche-930') else 'game-tuned'
            image('garage-v2/car-'+thumbnail+'.png', rx+12, cy+15, 102, 57,
                  color=(1.0, 0.97, 0.92, 1.0) if active else (0.86, 0.88, 0.92, 0.94))
            label(item.name, rx+122, cy+41, 18 if aspect > 1.5 else 15.5, theme.AMBER if active else WHITE, bold=True)
            c_let, c_scr, _, _, _ = theme.vehicle_pi(vehicle_design(item.design_id).config)
            tag = '当前驾驶' if is_cur else '已解锁' if is_open else f'需 {item.unlock} 星'
            if is_cur:
                fill(rx+122, cy+52, 68, 21, theme.STEEL_BG, 4)
                label(tag, rx+156, cy+67, 11.5, theme.STEEL_TEXT, bold=True, center=True)
                label(f'{c_let} {c_scr}', rx+200, cy+68, 12.5, GRAY, display=True)
            else:
                label(f'{c_let} {c_scr}  ·  {tag}', rx+122, cy+68, 13,
                      theme.STEEL_TEXT if is_open else theme.DARK_LOCKED)
            r_tex = 'atelier/radio-active.png' if active else 'atelier/radio-installed.png' if is_cur else 'atelier/radio-idle.png'
            image(r_tex, rx+rw-38, cy+(card_h-23)/2, 23, 23)

        if len(cars) > 4:
            nav_y = 602.
            hw = (rw - 12) / 2
            button('‹  上一辆', rx, nav_y, hw, 38, 'garage-car',
                   cars[(selected-1) % len(cars)].design_id, role='secondary',
                   tex_idle='atelier/btn-ghost.png', tex_focus='atelier/btn-ghost-hover.png')
            button('下一辆  ›', rx+hw+12, nav_y, hw, 38, 'garage-car',
                   cars[(selected+1) % len(cars)].design_id, role='secondary',
                   tex_idle='atelier/btn-ghost.png', tex_focus='atelier/btn-ghost-hover.png')

        # 复刻参考图「已安装 → 待安装」对比区。
        cur_car = next(item for item in cars if item.design_id == vehicle.design_id)
        sum_y = 656.
        fill(rx, sum_y, rw, 1, (0.20, 0.24, 0.31, 0.85), 0)
        label('当前驾驶', rx, sum_y+26, 13, GRAY)
        label(cur_car.name, rx, sum_y+56, 17 if aspect > 1.5 else 15.5, WHITE, bold=True)
        label('→', rx+rw*0.50, sum_y+56, 20, GRAY, center=True)
        label('当前预览', rx+rw, sum_y+26, 13, GRAY, right=True)
        label(car.name, rx+rw, sum_y+56, 17 if aspect > 1.5 else 15.5, theme.AMBER, bold=True, right=True)

        current = preview.design_id == vehicle.design_id
        unlocked = current or progress.stars >= car.unlock
        cta_y, cta_h = 746., 66.
        btn_txt = '当前驾驶中' if current else '选择并驾驶' if unlocked else f'需 {car.unlock} 星解锁'
        go_btn = button(btn_txt, rx, cta_y, rw, cta_h, 'garage-select',
                        role='primary', primary=True, enabled=unlocked and not current,
                        tex_idle='atelier/btn-primary.png' if (unlocked and not current) else 'atelier/btn-ghost.png',
                        tex_focus='atelier/btn-primary-hover.png' if (unlocked and not current) else 'atelier/btn-ghost.png',
                        text_pos=(18 if (unlocked and not current) else 0, -7))
        if unlocked and not current:
            ic = atelier.picture(go_btn, panel.loader, 'atelier/icon-steering.png',
                                 (-78*unit, -50*unit, -14*unit, 14*unit), color=INK)
            panel.frames.append(ic)
    else:
        paint_notes = ('暖金清漆金属质感', '深海镜面金属漆', '经典赛道竞速红', '暗松林深邃金属漆', '纯净高光珠光白')
        label('海岸车库  /  车身颜色', rx, 112, 13.5, GRAY)
        label(f'★ {progress.stars} / 18', rx + rw, 112, 13.5, theme.AMBER, bold=True, right=True)
        label('车身涂装', rx, 152, 30, WHITE, bold=True)
        label(f'{car.name}  ·  实时预览落日车漆反光。', rx, 182, 14.5, GRAY)

        card_h, card_gap = 82., 10.
        for index, skin in enumerate(SKINS):
            cy = 204. + index * (card_h + card_gap)
            active = index == skin_index
            is_saved = index == panel.vehicle_view.base.skin_index
            button('', rx, cy, rw, card_h, 'garage-paint', index,
                   role='category-active' if active else 'category',
                   tex_idle='atelier/card-active.png' if active else 'atelier/card-idle.png',
                   tex_focus='atelier/card-active.png')
            image('garage-v2/paint-'+str(index)+'.png', rx+20, cy+13, 56, 56)
            label(skin.name, rx+92, cy+38, 19, theme.AMBER if active else WHITE, bold=True)
            label(paint_notes[index] if index < len(paint_notes) else '金属清漆涂装',
                  rx+92, cy+64, 13, GRAY)
            if active:
                fill(rx+rw-122, cy+20, 62, 21, theme.STEEL_BG, 4)
                label('当前预览', rx+rw-91, cy+35, 11.5, theme.STEEL_TEXT, bold=True, center=True)
            elif is_saved:
                fill(rx+rw-112, cy+20, 52, 21, theme.STEEL_BG, 4)
                label('已应用', rx+rw-86, cy+35, 11.5, theme.STEEL_TEXT, bold=True, center=True)
            r_tex = 'atelier/radio-active.png' if active else 'atelier/radio-installed.png' if is_saved else 'atelier/radio-idle.png'
            image(r_tex, rx+rw-38, cy+(card_h-23)/2, 23, 23)

        cta_y, cta_h = 746., 66.
        reset_w = 128.
        save_w = rw - reset_w - 12.
        save_btn = button('应用车身颜色', rx, cta_y, save_w, cta_h, 'garage-paint-save',
                          role='primary', primary=True,
                          tex_idle='atelier/btn-primary.png', tex_focus='atelier/btn-primary-hover.png',
                          text_pos=(16, -7))
        p_ic = atelier.picture(save_btn, panel.loader, 'atelier/icon-paint.png',
                               (-84*unit, -60*unit, -12*unit, 12*unit), color=INK)
        panel.frames.append(p_ic)
        button('恢复原漆', rx+save_w+12, cta_y, reset_w, cta_h, 'garage-tab', 'paint',
               role='footer',
               tex_idle='atelier/btn-ghost.png', tex_focus='atelier/btn-ghost-hover.png')

    # ── 底部通宽拉丝黑曜石序号进度条 + 右下角斜切角标（与首页 1:1 统一）──
    image('atelier/footer-surface.png', 0, foot_y, width, 941-foot_y)
    image('atelier/footer-corner-tag.png', width - 178, foot_y + 38, 178, 45)
    label('海岸车库 · S1', width - 24, foot_y + 68, 13.5, GRAY, right=True)
    step_active = 0 if tab == 'cars' else 1
    steps = (('1', '选择车辆'), ('2', '车身涂装'), ('3', '海岸试驾'))
    step_span = 260. if aspect > 1.5 else 200.
    start_sx = width/2 - step_span - 60
    sy = foot_y + 42
    for si, (num, s_label) in enumerate(steps):
        cx = start_sx + si * step_span
        is_on = si == step_active
        image('atelier/step-active.png' if is_on else 'atelier/step-idle.png', cx-16, sy-16, 32, 32)
        label(num, cx, sy+7, 15, INK if is_on else GRAY, bold=True, center=True)
        label(s_label, cx+26, sy+7, 16, theme.AMBER if is_on else GRAY, bold=is_on)
        if si < 2:
            fill(cx+112, sy-0.5, step_span-144, 1.2, (0.24, 0.28, 0.36, 0.9), 0)

    message = notice or progress.notice
    if message:
        line = panel.vehicle_view.base.fit_lines(message, (width*0.32)*unit, 14*unit, max_lines=1)
        label(line+('…' if line != message else ''), 34, sy+7, 14, theme.AMBER, bold=True)
    else:
        label('← → 换车或调视角   Enter 确认   Esc 返回', 34, sy+7, 14, GRAY)
    panel.select(panel.primary)


def style(panel):
    """全站 CareerPanel 统一落日黑曜石与琥珀金控件高亮：兼容高分微光贴图按钮与几何按钮。"""
    btn_tex = getattr(panel, 'atelier_btn_tex', {})
    for index, button in enumerate(panel.buttons):
        role = panel.garage_roles[index]
        disabled, focused = button['state'] == DGG.DISABLED, index == panel.selected
        if index in btn_tex:
            idle_name, focus_name = btn_tex[index]
            button['frameTexture'] = atelier.tex(panel.loader, focus_name if (focused and not disabled) else idle_name)
            button['frameColor'] = (0.55, 0.58, 0.64, 0.72) if disabled else (1, 1, 1, 1)
            if disabled:
                button['text_fg'] = theme.DARK_LOCKED
            elif role == 'primary':
                button['text_fg'] = INK
            elif focused:
                button['text_fg'] = theme.AMBER
            else:
                button['text_fg'] = WHITE
            continue
        transparent = role in ('event-card', 'quiet')
        if role == 'primary':
            color = (0.18, 0.21, 0.27, 1) if disabled else (theme.AMBER_BRIGHT if focused else theme.AMBER)
        elif role in ('tab-active', 'tab'):
            color = (0.14, 0.17, 0.22, 0.45) if focused else (0, 0, 0, 0)
        elif role == 'category-active':
            color = (0.24, 0.195, 0.115, 0.96) if focused else theme.AMBER_WASH
        elif role == 'category':
            color = (0.145, 0.172, 0.225, 0.96) if focused else theme.CARBON_CARD
        elif role in ('season-tab-active', 'setup-active'):
            color = theme.AMBER_WASH if focused else (0.155, 0.135, 0.100, 0.92)
        elif role in ('season-tab', 'setup-tab'):
            color = theme.CHARCOAL_SOFT if focused else theme.CARBON_SOLID
        elif role in ('setup-preset', 'setup-step'):
            color = theme.AMBER_WASH if focused else theme.CARBON_CARD
        elif role in ('footer', 'secondary'):
            color = theme.AMBER_WASH if focused else theme.CARBON_SOLID
        elif transparent:
            color = (0.949, 0.690, 0.255, 0.10) if focused else (0, 0, 0, 0)
        else:
            color = theme.AMBER_WASH if focused else theme.CARBON_CARD
        button['geom_color'] = color
        if disabled:
            button['text_fg'] = theme.DARK_LOCKED
        elif role == 'primary':
            button['text_fg'] = theme.INK
        elif role in ('tab-active', 'season-tab-active', 'setup-active'):
            button['text_fg'] = theme.AMBER if role != 'tab-active' else WHITE
        elif role in ('tab', 'season-tab', 'setup-tab'):
            button['text_fg'] = WHITE if focused else theme.DARK_SUB
        elif role == 'category-active' or (focused and role in ('secondary', 'footer', 'setup-preset', 'setup-step')):
            button['text_fg'] = theme.AMBER
        else:
            button['text_fg'] = WHITE
