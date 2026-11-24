"""预算挑战的参数改装与联合结算；沿用车库母版，不显示未经实测的预测。"""

import math
from dataclasses import replace

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectEntry, DirectSlider
from panda3d.core import LineSegs, TextNode, TransparencyAttrib

from career import EVENT_BY_ID, EVENTS
from career_garage import CAR_BY_DESIGN
from challenge_build import HARDWARE
from race import GameMode
from road_test_driver import TRIAL_POLICIES
from sprint_routes import VALLEY_BRAKING
from ui import atelier, theme
from ui.career_layout import ORANGE, WHITE
from ui.career_layout import canvas as career_canvas

SUCCESS = theme.PINE
from ui.lab_widgets import rounded_panel
from ui.race_feedback import energy_segment, energy_segment_delta
from ui.sprint_feedback import valley_braking_feedback
from vehicle_designs import vehicle_design
from vehicle_workspace import WorkspaceVehicle

GROUPS = (('动力与阻力', ('power', 'mass', 'drag', 'final_drive')),
          ('轮胎与底盘', ('front_tire', 'rear_tire', 'brakes', 'springs', 'dampers')),
          ('免费调校', ('brake_share', 'antiroll_share')))
HARDWARE_BY_KEY = {item.key: item for item in HARDWARE}
UNITS = {'power': ('%', 1, .5), 'mass': ('kg', 1, 1.), 'drag': ('m²', 4, .001),
         'front_tire': ('kN/rad', 1, .5), 'rear_tire': ('kN/rad', 1, .5),
         'brakes': ('N·m', 1, 10.), 'springs': ('kN/m', 1, .5),
         'dampers': ('%', 1, 1.), 'final_drive': ('', 3, .01),
         'brake_share': ('%', 1, 1.), 'antiroll_share': ('%', 1, 1.)}
FREE_NAMES = {'brake_share': '前制动份额', 'antiroll_share': '前防倾份额'}
RECORD_NAMES = {'fastest': '最快', 'economy': '最省油', 'cheapest': '最低费用', 'specialist': '专项最佳'}
CAREER_ROAD_SEGMENTS = {
    'coast-sprint': ('起步长弯', '紧凑组合弯', '回弯出弯', '末段弯道'),
    'ridge-run': ('连续上坡', '第一处回头弯', '下坡接第二弯', '出弯冲线'),
    'coastal-cup': ('沿海组合弯', '长弯上坡', '双回头弯', '末段组合弯'),
}
ENTRY_ACTIONS = ('challenge-commit', 'challenge-value', 'challenge-step', 'challenge-tab',
                 'challenge-save', 'challenge-start', 'challenge-auto', 'challenge-lab', 'reference-topic')


def field_values(spec, draft, key):
    base = spec.base_config
    scales = {'power': 100., 'mass': base.mass,
              'drag': base.drag_coefficient*base.frontal_area,
              'front_tire': base.lateral_stiffness/1000,
              'rear_tire': base.rear_lateral_stiffness/1000,
              'brakes': base.brake_torque, 'springs': sum(base.suspension_spring_rates)/4000,
              'dampers': 100., 'final_drive': base.final_drive}
    if key in scales:
        item, scale = HARDWARE_BY_KEY[key], scales[key]
        return item.title, scale, item.minimum*scale, item.maximum*scale, draft.value(key)*scale
    if key == 'brake_share':
        stock, low, high = base.front_brake_share*100, 40., 80.
    elif key == 'antiroll_share':
        stock, low, high = base.suspension_antiroll_rates[0]/sum(base.suspension_antiroll_rates)*100, 5., 95.
    else:
        raise ValueError('未知工程参数')
    value = draft.value(key)
    return FREE_NAMES[key], stock, low, high, stock if value is None else value*100


def formatted(key, value):
    digits = UNITS[key][1]
    return f'{value:.{digits}f}'.rstrip('0').rstrip('.') if digits else f'{value:g}'


def read_value(spec, draft, key, raw):
    title, stock, low, high, _ = field_values(spec, draft, key)
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(title+'须填写数字') from None
    if not math.isfinite(value):
        raise ValueError(title+'须为有限数')
    # 输入框显示舍入后的端点；精确输入该显示值时仍还原真实物理端点。
    if value == float(formatted(key, low)):
        value = low
    elif value == float(formatted(key, high)):
        value = high
    if not low <= value <= high:
        raise ValueError(f'{title}范围 {formatted(key, low)}—{formatted(key, high)} {UNITS[key][0]}')
    return round(value/(stock if key in HARDWARE_BY_KEY else 100.), 10)


def step_value(spec, draft, key, direction):
    _, _, low, high, value = field_values(spec, draft, key)
    return read_value(spec, draft, key, min(high, max(low, value+UNITS[key][2]*direction)))


def read_build(panel, input_value=None):
    """先读完当前页再更新方案，避免同步第一行时覆盖其它尚未提交的输入。"""
    spec, draft, _, _ = panel.challenge_data
    values = {}
    for key, entry in panel.challenge_entries.items():
        raw = input_value[1] if input_value is not None and input_value[0] == key else entry.get()
        current = field_values(spec, draft, key)[-1]
        number = read_value(spec, draft, key, raw)
        # 显示精度的舍入不应改变实际参数，免费原车设定仍保留None。
        if float(raw) != float(formatted(key, current)):
            values[key] = number
    changed = replace(draft, **values)
    spec.configuration(changed)
    return changed


def _vehicle_box(width, left, wide, bottom=670.):
    unit = 2/941
    return ((left+wide+18-width/2)*unit, (width/2-left)*unit, 1-bottom*unit, 1-230.*unit)


def _result_width(width):
    return min(680., width*.43)


def result_vehicle_box(aspect):
    """结算预热与显示共用精确视口。"""
    width = 941*aspect
    return _vehicle_box(width, width*.031, _result_width(width))


def _vehicle(panel, spec, draft, width, left, wide, label, fill=None, image=None):
    margin, bottom = width*.031, 670.
    if panel.page == 'challenge' and panel.vehicle_view.base.challenge_presets(spec):
        # 宽屏车辆随展示区变大，收起视口下缘为参考方案留出间距。
        bottom = max(600., bottom-max(0., width-margin-left-wide-18-500.)*.30)
    if image is not None:
        stage_x = left+wide+18
        stage_span = width-margin-stage_x
        image('atelier/floor-warm-bounce.png', stage_x-24, bottom-215, stage_span+48, 245,
              tint=(1, 0.90, 0.74, 0.80))
    box = _vehicle_box(width, left, wide, bottom)
    config = spec.configuration(draft)
    panel.vehicle_view.show(panel.content, box, WorkspaceVehicle(spec.design_id, config), studio=True,
                            skin_index=0 if spec.assessment == 'reference' else None)
    panel.vehicle_view.frame.setTransparency(TransparencyAttrib.MAlpha)
    panel.vehicle_view.highlight(None)
    if fill is not None:
        letter, score, _pi_color, _power_kw, _ = theme.vehicle_pi(config)
        bx = width-margin-384
        if image is not None:
            image('atelier/card-idle.png', bx-8, 114, 400, 100)
            fill(bx+8, 139, 3.5, 48, theme.AMBER, 2)
        else:
            fill(bx-1, 121, 386, 86, theme.CARBON_EDGE, 8)
            fill(bx, 122, 384, 84, theme.CARBON_GLASS, 7)
        panel.challenge_readouts['pi-bg'] = fill(bx+22, 150, 86, 28, theme.STEEL_BG, 5)
        lbl_pi = label(f'{letter} {score}', bx+65, 170, 16, theme.STEEL_TEXT, bold=True)
        lbl_pi['font'] = panel.garage_display_font
        lbl_pi.textNode.setAlign(TextNode.ACenter)
        panel.challenge_readouts['pi-combined'] = lbl_pi
    tx = width-margin-16 if fill is not None else width-margin
    label(vehicle_design(spec.design_id).name, tx, 152, 22, WHITE, right=True, bold=True)
    power = max(rpm*torque/9549.3 for rpm, torque in config.torque_curve)
    panel.challenge_readouts['vehicle'] = label(f'{config.mass:.0f} kg  |  {power:.0f} kW',
                                               tx, 184, 16, theme.DARK_SUB, right=True)


def _reference_setups(panel, spec, width, x, fill, label, button, image=None):
    choices = panel.vehicle_view.base.challenge_presets(spec)
    if not choices:
        return
    span = width*.969-x
    if image is not None:
        image('atelier/panel-obsidian.png', x-9, 574, span+18, 108)
    else:
        fill(x-1, 581, span+2, 94, theme.SLATE_BORDER, 11)
        fill(x, 582, span, 92, theme.SLATE_GLASS, 10)
    fill(x+9, 592, 3.5, 22, theme.AMBER, 2)
    panel.challenge_readouts['preset-title'] = label('参考方案', x+22, 609, 20, theme.TEXT_LIGHT, bold=True)
    gap = 12
    w = (span-gap*(len(choices)+1))/len(choices)
    measure = TextNode('reference-label-width')
    measure.setFont(panel.garage_font)
    titles = [f'{setup.title} · {setup.build.cost}' for setup in choices]
    size = min(20., (w-16)/max(measure.calcWidth(title) for title in titles))
    for index, title in enumerate(titles):
        left = x+gap+index*(w+gap)
        panel.challenge_readouts[f'preset:{index}'] = fill(left-1, 617, w+2, 45, theme.SLATE_BORDER, 7)
        item = button(title, left, 618, w, 43, 'challenge-preset', index, role='setup-preset')
        item['text_scale'] = size*2/941


def _targets(panel, spec, width, left, fill, label, image=None):
    span = width-left-width*.031
    if spec.assessment == 'reference':
        x, y = width-width*.031-span, 640.
        if image is not None:
            image('atelier/panel-obsidian.png', x-9, y-8, span+18, 204)
        else:
            fill(x-1, y-1, span+2, 190, theme.SLATE_BORDER, 11)
            fill(x, y, span, 188, theme.SLATE_GLASS, 10)
        fill(x+9, y+12, 3.5, 22, theme.AMBER, 2)
        label('固定参考 A/B', x+22, y+30, 20, theme.TEXT_LIGHT, bold=True)
        label(spec.conditions, x+18, y+61, 16, theme.TEXT_SUB, wrap=span-36)
        for index, requirement in enumerate(spec.requirements):
            yy = y+108+index*30
            label(('铜', '银', '金')[index], x+18, yy, 19, (theme.BRONZE, theme.SILVER, theme.GOLD)[index], bold=True)
            label(requirement, x+span-18, yy, 19, theme.TEXT_LIGHT, right=True)
        return
    x, y = width-width*.031-span, 686.
    if image is not None:
        image('atelier/panel-obsidian.png', x-9, y-8, span+18, 158)
    else:
        fill(x-1, y-1, span+2, 144, theme.SLATE_BORDER, 11)
        fill(x, y, span, 142, theme.SLATE_GLASS, 10)
    fill(x+9, y+12, 3.5, 22, theme.AMBER, 2)
    distance = spec.id == GameMode.DISTANCE_CHALLENGE.value
    label('车道内完赛' if distance else '完赛目标 · 试行' if spec.provisional else '完赛目标',
          x+22, y+30, 20, theme.TEXT_LIGHT, bold=True)
    if spec.assessment != 'road':
        label(spec.metric_label+' / '+spec.metric_unit, x+span-18, y+29, 17, theme.TEXT_SUB, right=True)
        values = ([f'≤ {limit:g}' for limit in spec.metric_limits] if spec.assessment == 'lower' else
                  ['至少 3 门', '全部 5 门', f'全 5 门且 ≤ {spec.metric_limits[0]:g}s'])
        for index, value in enumerate(values):
            yy = y+62+index*30
            label(('铜', '银', '金')[index], x+18, yy, 19, (theme.BRONZE, theme.SILVER, theme.GOLD)[index], bold=True)
            label(value, x+span-18, yy, 19, theme.TEXT_LIGHT, right=True)
        return
    if distance and not spec.targets:
        label('无碰撞驶满 5 公里', x+18, y+72, 21, theme.TEXT_LIGHT)
        label('倒车可调姿，复位结束本次', x+18, y+111, 18, theme.TEXT_SUB)
        return
    if not spec.targets:
        label('用时与赛段油耗同次达标', x+18, y+72, 21, theme.TEXT_LIGHT)
        label('目标标定中 · 当前可试跑', x+18, y+111, 18, theme.TEXT_SUB)
        return
    label('用时 / s', x+span*.55, y+29, 17, theme.TEXT_SUB, right=True)
    label('L/100km', x+span-18, y+29, 17, theme.TEXT_SUB, right=True)
    for index, target in enumerate(spec.targets):
        yy = y+62+index*30
        label(target.medal, x+18, yy, 19, (theme.BRONZE, theme.SILVER, theme.GOLD)[min(index, 2)], bold=True)
        label(f'≤ {target.seconds:.1f}', x+span*.55, yy, 19, theme.TEXT_LIGHT, right=True)
        label(f'≤ {target.consumption:.1f}', x+span-18, yy, 19, theme.TEXT_LIGHT, right=True)


def _slide(panel, key):
    if not panel.challenge_updating:
        spec, draft, _, _ = panel.challenge_data
        _, _, low, high, current = field_values(spec, draft, key)
        raw = min(high, max(low, panel.challenge_sliders[key]['value']))
        # Panda滑杆返回float32；程序同步控件不能把原车变成收费的微小改装。
        if math.isclose(raw, current, rel_tol=1e-6, abs_tol=1e-8):
            return
        panel.action('challenge-value', (key, formatted(key, raw)))


def canvas(panel, progress, title, *, budget):
    width, left, fill, label, image, button = career_canvas(panel, progress, '', budget=budget, chrome=False)
    panel.challenge_readouts['budget'].hide()
    image('atelier/bar-top.png', 0, 0, width, 108)
    image('atelier/footer-surface.png', 0, 846, width, 95)
    heading, _, subtitle = title.partition(' · ')
    fill(left, 26, 4.5, 56, theme.AMBER, 2)
    label(heading, left+18, 56, 33, WHITE, bold=True)
    label(subtitle, left+18, 88, 18, theme.DARK_SUB)
    x = width-left-374
    for index, (key, name) in enumerate((('limit', '预算'), ('used', '已用'), ('remaining', '剩余'))):
        xx = x+index*132
        label(name, xx, 35, 15, theme.DARK_SUB)
        lbl = label(str(budget) if key in ('limit', 'remaining') else '0', xx, 70, 26, WHITE, bold=True)
        lbl['font'] = panel.garage_display_font
        panel.challenge_readouts[key] = lbl
    fill(x, 85, 374, 6, (0.14, 0.17, 0.23, 0.96), 3)
    panel.challenge_readouts['budget-bar'] = fill(x, 85, 374, 6, theme.AMBER, 3)
    panel.challenge_readouts['budget-left'] = (x-width/2)*2/941
    return width, left, fill, label, image, button


def _focus_row(panel, key, focused):
    panel.challenge_readouts['row:'+key].setColor(theme.AMBER_WASH if focused else (0, 0, 0, 0))
    panel.challenge_readouts['row-edge:'+key].setColor(theme.AMBER if focused else (0, 0, 0, 0))
    panel.challenge_readouts['entry-edge:'+key].setColor(theme.AMBER if focused else theme.CARBON_EDGE)


def _blur_entry(panel, key):
    if panel.challenge_updating or panel.root.isHidden() or panel.page != 'challenge':
        return
    _focus_row(panel, key, False)
    panel.action('challenge-commit')


def _reset_icon(button, unit):
    line = LineSegs()
    line.setColor(*theme.TEXT_SUB)
    line.setThickness(1.6)
    for index in range(25):
        angle = math.radians(135+index*300/24)
        point = (9*math.cos(angle)*unit, 0, 9*math.sin(angle)*unit)
        line.moveTo(*point) if index == 0 else line.drawTo(*point)
    line.moveTo(-10*unit, 0, 10*unit)
    line.drawTo(-10*unit, 0, 3*unit)
    line.drawTo(-3*unit, 0, 3*unit)
    button.attachNewNode(line.create())


def build_page(panel, spec, draft, tab, notice):
    panel.challenge_updating = True
    app = panel.vehicle_view.base
    practice = spec.assessment == 'road' and app.budget_origin == 'tour-practice'
    subtitle = (' · '.join(app.highway_conditions()) if spec.id == GameMode.DISTANCE_CHALLENGE.value else
                '单站练习' if practice else '车辆方案')
    if spec.version == VALLEY_BRAKING.version:
        subtitle = VALLEY_BRAKING.description.splitlines()[-1]
    width, left, fill, label, image, button = canvas(panel, None, spec.name+' · '+subtitle, budget=spec.budget)
    unit, wide = 2/941, min(790., width*.53)
    keys = tuple(key for key in GROUPS[tab][1] if key in spec.allowed)
    image('atelier/panel-obsidian.png', left-12, 116, wide+24, 714)
    tab_width = (wide-40)/3
    for index, (title, _) in enumerate(GROUPS):
        x = left+20+index*tab_width
        button(title, x, 146, tab_width-6, 52, 'challenge-tab', index,
               role='setup-active' if index == tab else 'setup-tab',
               enabled=any(key in spec.allowed for key in GROUPS[index][1]))
    control = left+wide*.47
    control_width = wide*.37
    stock_x = left+wide*.36
    fill(left+16, 218, wide-32, 36, (0.055, 0.070, 0.098, 0.78), 6)
    label('参数', left+30, 243, 17, theme.TEXT_SUB, bold=True)
    label('原车', stock_x, 243, 17, theme.TEXT_SUB, right=True)
    label('调节', control, 243, 17, theme.TEXT_SUB)
    label('费用', left+wide-24, 243, 17, theme.TEXT_SUB, bold=True, right=True)
    for index, key in enumerate(keys):
        y = 266+index*98
        title, stock, low, high, value = field_values(spec, draft, key)
        panel.challenge_readouts['row:'+key] = fill(left+12, y-2, wide-24, 91, (0, 0, 0, 0), 8)
        panel.challenge_readouts['row-edge:'+key] = fill(left+8, y-2, 4, 91, (0, 0, 0, 0), 2)
        label(title, left+30, y+32, 20 if wide >= 740 else 18, theme.TEXT_LIGHT, bold=True)
        label(UNITS[key][0], left+30, y+62, 16, theme.TEXT_SUB)
        reset = button('', left+wide*.23, y+(47 if wide < 740 else 15), 32, 34,
                       'challenge-reset', key, role='quiet')
        _reset_icon(reset, unit)
        label(formatted(key, stock), stock_x, y+33, 20, theme.TEXT_SUB, right=True)
        number_x, number_w = control+52, control_width-104
        panel.challenge_readouts['entry-edge:'+key] = fill(number_x-1, y+6, number_w+2, 36, theme.CARBON_EDGE, 6)
        fill(number_x, y+7, number_w, 34, theme.CARBON_SOLID, 5)
        button('−', control, y+7, 40, 34, 'challenge-step', (key, -1), role='setup-step')
        button('+', control+control_width-40, y+7, 40, 34, 'challenge-step', (key, 1), role='setup-step')
        entry = DirectEntry(parent=panel.content, initialText=formatted(key, value),
            pos=((number_x+number_w/2-width/2)*unit, 0, 1-(y+32)*unit), scale=20*unit,
            text_font=panel.garage_font, text_fg=WHITE, text_align=2,
            frameColor=(0, 0, 0, 0), frameSize=(-number_w/44, number_w/44, -.35, 1.1),
            relief=DGG.FLAT, width=number_w/22, numLines=1,
            focusInCommand=lambda k=key: _focus_row(panel, k, True),
            focusOutCommand=lambda k=key: _blur_entry(panel, k),
            command=lambda raw, k=key: panel.action('challenge-value', (k, raw)))
        track_y = y+57
        slider = DirectSlider(parent=panel.content, range=(low, high), value=value,
            pos=((control+control_width/2-width/2)*unit, 0, 1-track_y*unit),
            frameSize=(-control_width*unit/2, control_width*unit/2, -2*unit, 2*unit),
            frameColor=(0.18, 0.22, 0.29, 1), relief=DGG.FLAT,
            thumb_frameSize=(-6*unit, 6*unit, -8*unit, 8*unit), thumb_frameColor=theme.AMBER,
            thumb_relief=DGG.FLAT, pageSize=UNITS[key][2], scrollSize=UNITS[key][2],
            command=lambda k=key: _slide(panel, k))
        thumb = rounded_panel(panel.content, 'slider-thumb', (-7.5*unit, 7.5*unit, -7.5*unit, 7.5*unit), theme.AMBER, 7.5*unit)
        rounded_panel(thumb, 'slider-thumb-core', (-3.5*unit, 3.5*unit, -3.5*unit, 3.5*unit), theme.CARBON_SOLID, 3.5*unit)
        thumb.detachNode()
        slider.thumb['geom'] = thumb
        slider.thumb['frameColor'] = (0, 0, 0, 0)
        panel.challenge_readouts['track:'+key] = fill(control, track_y-2, control_width, 4, theme.AMBER, 0)
        for tick in range(5):
            fill(control+control_width*tick/4, track_y+7, 1, 5, theme.SLATE_BORDER, 0)
        fill(control+control_width*(stock-low)/(high-low), track_y-5, 2, 12, theme.TEXT_LIGHT, 0)
        label(formatted(key, low), control, y+83, 14, theme.TEXT_SUB)
        label(formatted(key, high), control+control_width, y+83, 14, theme.TEXT_SUB, right=True)
        panel.challenge_widgets.extend((entry, slider))
        panel.challenge_entries[key], panel.challenge_sliders[key] = entry, slider
        panel.challenge_readouts['cost:'+key] = label('', left+wide-24, y+33, 21, theme.GOLD, bold=True, right=True)
        fill(left+20, y+91, wide-40, 1, theme.SLATE_BORDER, radius=0)
    panel.challenge_readouts['other'] = label('', left+30, 797, 18, theme.TEXT_SUB)
    button('恢复原车', left+wide-170, 766, 150, 40, 'challenge-reset', None, role='secondary')
    _vehicle(panel, spec, draft, width, left, wide, label, fill=fill, image=image)
    _reference_setups(panel, spec, width, left+wide+18, fill, label, button, image=image)
    _targets(panel, spec, width, left+wide+18, fill, label, image=image)
    reference = spec.assessment == 'reference'
    if reference:
        button('切换：'+('弯道改装' if 'braking' in spec.id else '制动改装'), width*.49, 23, 158, 42,
               'reference-topic', 1 if 'braking' in spec.id else 0, role='secondary')
    button('‹  返回巡回' if practice else '‹  返回', left, 862, 190, 58, 'challenge-back', role='footer')
    button('保存方案', left+230, 862, 190, 58, 'challenge-save', role='secondary')
    button('查看曲线' if reference else '参考试验', left+436, 862, 190, 58, 'challenge-lab', role='secondary')
    if app.budget_origin == 'cup':
        button('带入单项方案', left+642, 862, 190, 58, 'challenge-import', role='secondary')
    elif spec.id in TRIAL_POLICIES and app.budget_origin != 'chase':
        button('自动试车', left+642, 862, 190, 58, 'challenge-auto', role='secondary')
    panel.challenge_readouts['notice'] = label('', left+24, 841, 17, ORANGE, wrap=width-2*left)
    start_btn = button('开始挑战', width-left-284, 862, 284, 58,
                       'challenge-start', role='primary', primary=True)
    start_btn['text_pos'] = (16*unit, -7*unit)
    s_ic = atelier.picture(start_btn, panel.loader, 'atelier/icon-steering.png',
                           (-86*unit, -60*unit, -13*unit, 13*unit), color=theme.INK)
    panel.frames.append(s_ic)
    panel.challenge_readouts['start'] = start_btn
    update_build(panel, spec, draft, notice)
    panel.challenge_updating = False
    panel.select(panel.primary)


def _record_feedback(status, provisional):
    medal = status.result.medal
    graded = [RECORD_NAMES[name] for grade, name in status.record_updates if grade == medal]
    if graded:
        prefix = '试行' if provisional else ''
        return '新'+prefix+medal+'牌纪录 · '+' / '.join(graded)
    overall = [RECORD_NAMES[name] for grade, name in status.record_updates if grade == '完赛']
    return '新个人纪录 · '+' / '.join(overall) if overall else ''


def _result_segments(spec, status, left, wide, fill, label, *, automatic=False, valley_labels=()):
    road = spec.assessment == 'road'
    circuit = spec.id == GameMode.TIME_TRIAL.value
    valley = spec.id == GameMode.VALLEY_PACE.value
    braking = spec.id == GameMode.SHORT_BRAKING.value
    reference = status.reference_splits if road and status.result.valid else ()
    career_sections = CAREER_ROAD_SEGMENTS.get(spec.id)
    fill(left+24, 598, wide-48, 38, (0.055, 0.070, 0.098, 0.85), 6)
    heading = '检查点' if circuit else '路段' if road else '里程点' if braking else '道路门'
    if reference and status.splits:
        heading += ' · 括号较对照' if automatic or status.reference_label else ' · 括号较最快'
    label(heading, left+36, 624, 17, theme.TEXT_SUB)
    label('本段用时 / s' if road else '累计用时 / s', left+wide*.57, 624, 17, theme.TEXT_SUB, right=True)
    label('本段 L/100km' if road else '累计 L/100km', left+wide-30, 624, 17, theme.TEXT_SUB, right=True)
    for index, split in enumerate(status.splits):
        y = 660+index*(29 if len(status.splits) > 4 else 36)
        name = '终点' if split.distance_m == spec.distance_m else str(index+1)
        if road:
            segment = energy_segment(status.splits, index)
            start, end, seconds, consumption = segment
            if valley:
                name = (valley_labels or ('测速门前', '减速区', '限速带', '出带冲线'))[index]
            elif career_sections:
                name = career_sections[index]
            elif not circuit:
                name = f'{start:g}–{end:g}m'
            delta = energy_segment_delta(segment, reference, index)
        else:
            seconds, consumption, delta = split.seconds, split.litres*100_000/split.distance_m, None
            if braking:
                name = f'{split.distance_m:g}m'
        values = (f'{seconds:.1f}', f'{consumption:.1f}')
        if delta is not None:
            values = tuple(f'{value} ({change:+.1f})' if abs(change) >= .05 else f'{value} (0.0)'
                           for value, change in zip(values, delta, strict=True))
        label(name, left+36, y, 17 if valley_labels else 19, theme.TEXT_LIGHT)
        label(values[0], left+wide*.57, y, 19, theme.TEXT_LIGHT, right=True)
        label(values[1], left+wide-30, y, 19, theme.TEXT_LIGHT, right=True)


def _career_slalom_segments(event, run, left, wide, fill, label):
    fill(left+24, 598, wide-48, 38, (0.055, 0.070, 0.098, 0.85), 6)
    label('道路门', left+36, 624, 17, theme.TEXT_SUB)
    label('距起点 / m', left+wide*.57, 624, 17, theme.TEXT_SUB, right=True)
    label('本次通过', left+wide-30, 624, 17, theme.TEXT_SUB, right=True)
    for index, (distance, _) in enumerate(event.gates):
        y = 651+index*29
        state = '未到达'
        if index < len(run.passed):
            state = '通过' if run.passed[index] else '漏门'
        label(f'第{index+1}门', left+36, y, 19, theme.TEXT_LIGHT)
        label(f'{distance:g}', left+wide*.57, y, 19, theme.TEXT_SUB, right=True)
        label(state, left+wide-30, y, 19, ORANGE if state == '漏门' else SUCCESS if state == '通过' else theme.TEXT_SUB, right=True)


def _slalom_trial_segments(run, reference, left, wide, fill, label):
    previous = () if reference is None or not run.succeeded else reference.clearances
    fill(left+24, 598, wide-48, 38, (0.055, 0.070, 0.098, 0.85), 6)
    label('门位' if not previous else '门位 · 括号较对照', left+36, 624, 17, theme.TEXT_SUB)
    label('累计用时 / s', left+wide*.57, 624, 17, theme.TEXT_SUB, right=True)
    label('车身余量 / m', left+wide-30, 624, 17, theme.TEXT_SUB, right=True)
    for index, (seconds, clearance) in enumerate(zip(run.gate_times, run.clearances, strict=True)):
        y = 651+index*28
        value = f'{clearance:.2f}'
        if previous:
            difference = clearance-previous[index]
            value += f' ({difference:+.2f})' if abs(difference) >= .005 else ' (0.00)'
        label(f'第{index+1}门', left+36, y, 19, theme.TEXT_LIGHT)
        label(f'{seconds:.2f}', left+wide*.57, y, 19, theme.TEXT_LIGHT, right=True)
        label(value, left+wide-30, y, 19, theme.TEXT_LIGHT, right=True)


def _result_build_or_unlocks(result, award, left, right, fill, label, button, image=None):
    span = right-left
    if award is None or not award['saved'] or not award['unlocked']:
        costs = result.build.costs()
        changed = [f'{item.title} {costs[item.key]}' for item in HARDWARE if costs[item.key]]
        if image is not None:
            image('atelier/panel-obsidian.png', left-9, 702, span+18, 134)
        else:
            fill(left-1, 709, span+2, 120, theme.SLATE_BORDER, 11)
            fill(left, 710, span, 118, theme.SLATE_GLASS, 10)
        fill(left+10, 728, 3.5, 82, theme.AMBER, 2)
        label('本次方案', left+26, 742, 14, theme.AMBER, bold=True)
        label(' · '.join(changed) if changed else '原车硬件',
              left+26, 774, 19, theme.TEXT_LIGHT, wrap=span-48)
        return

    events = [event for event in EVENTS if event.name in award['unlocked']]
    cars = [CAR_BY_DESIGN[design_id] for design_id in award['vehicles']]
    if image is not None:
        image('atelier/panel-obsidian.png', left-9, 645, span+18, 191)
    else:
        fill(left-1, 652, span+2, 177, theme.SLATE_BORDER, 11)
        fill(left, 653, span, 175, theme.SLATE_GLASS, 10)
    fill(left+10, 666, 4, 148, ORANGE, 2)
    label('新解锁', left+26, 693, 24, theme.GOLD, bold=True)
    y = 736
    if events:
        label('赛事 · '+' / '.join(event.name for event in events), left+26, y, 19, theme.TEXT_LIGHT, wrap=span-192)
        button('查看赛事', right-148, y-25, 128, 33, 'brief', events[0].id, role='secondary')
        y += 49
    if cars:
        label('车辆 · '+' / '.join(car.name for car in cars), left+26, y, 19, theme.TEXT_LIGHT, wrap=span-192)
        button('查看新车', right-148, y-25, 128, 33, 'garage-new', cars[-1].design_id, role='secondary')


def result_page(panel, spec, status):
    result = status.result
    app = panel.vehicle_view.base
    road = app.session.highway.snapshot
    career_run = road.career if road.career is not None and road.career.event_id == spec.id else None
    subtitle = (' · '.join(app.highway_conditions()) if spec.id == GameMode.DISTANCE_CHALLENGE.value else
                '自动试车' if app.budget_auto else '单站练习结算' if app.budget_origin == 'tour-practice' else '挑战结算')
    if app.budget_auto and spec.id == GameMode.DISTANCE_CHALLENGE.value:
        subtitle += ' · 自动试车'
    width, left, fill, label, image, button = canvas(panel, None, spec.name+' · '+subtitle, budget=spec.budget)
    unit = 2/941
    _budget(panel, spec, result.cost)
    wide = _result_width(width)
    image('atelier/panel-obsidian.png', left-12, 112, wide+24, 726)
    fill(left+24, 162, 5, 46, ORANGE, 2)
    title = (result.medal+'牌完成' if result.medal else '有效完赛' if result.official and spec.targets else
             '试跑完成' if result.valid else '挑战未完成')
    label(title, left+40, 204, 44, theme.GOLD if result.medal == '金' else theme.TEXT_LIGHT, bold=True)
    target = result.next_target or (spec.targets[-1] if result.medal == '金' and spec.targets else None)
    target_name = (target.medal+'牌目标' if target is not None else '专项要求' if spec.assessment != 'road'
                   else '目标待标定' if not spec.targets else '本场要求')
    automatic_specialist = app.budget_auto and spec.assessment == 'lower'
    automatic_brake = automatic_specialist and spec.id == GameMode.SHORT_BRAKING.value
    automatic_slalom = automatic_specialist and spec.id == GameMode.FAST_SLALOM.value
    slalom = app.session.highway.snapshot.slalom if automatic_slalom else None
    valley = app.session.highway.snapshot.sprint if spec.version == VALLEY_BRAKING.version else None
    trial = app.auto_trial_reference if app.budget_auto else None
    valley_labels, retry_hint = (valley_braking_feedback(valley, None if trial is None else trial.valley)
                                if valley is not None else ((), ''))
    if app.budget_auto and result.valid and (spec.targets or automatic_specialist):
        target, target_name = (spec.targets[-1] if spec.targets else None), '金牌参考'
    reference = status.reference_result if spec.assessment in ('road', 'lower') else None
    specialist_reference = spec.assessment == 'lower' and reference is not None
    oil_precision = 2 if app.budget_auto else 1
    if automatic_brake:
        entry = app.session.highway.snapshot.braking.entry_kph
        if entry is not None:
            detail = f'入门 {entry:.1f} km/h'
            if reference is not None and result.valid:
                detail += f' · 较对照 {result.metric_value-reference.metric_value:+.2f} m'
            label(detail, left+24, 244, 19, theme.TEXT_SUB)
    if slalom is not None and slalom.clearances:
        label(f'通过 {slalom.gates}/6 门 · 最小余量 {min(slalom.clearances):.2f} m', left+24, 244, 19, theme.TEXT_SUB)
    if retry_hint:
        label(retry_hint, left+24, 244, 19, theme.TEXT_SUB)
    if result.valid and road.overtake is not None and reference is None and not app.budget_auto:
        label(f'安全超越 {road.overtake.passes} 辆', left+24, 244, 19, theme.TEXT_SUB)
    if reference is not None:
        if app.budget_auto:
            target_name = next((setup.title for setup in app.challenge_presets(spec) if setup.build == reference.build),
                               '对照试车')
        elif specialist_reference:
            target_name = '个人最佳'
            if result.valid and result.metric_value is not None:
                difference = result.metric_value-reference.metric_value
                label(f'较个人最佳 {difference:+.2f} {spec.metric_unit}', left+24, 244, 19, theme.TEXT_SUB)
        elif status.reference_label:
            target_name = status.reference_label
        elif not spec.targets:
            target_name = '最快完赛'
        if spec.assessment == 'road' and ((result.official and spec.targets) or (app.budget_auto and result.valid)):
            time_delta = result.seconds-reference.seconds
            oil_delta = round(result.consumption-reference.consumption, oil_precision)
            time_text = f'{time_delta:+.1f}' if abs(time_delta) >= .05 else '0.0'
            oil_text = f'{oil_delta:+.{oil_precision}f}' if oil_delta else f'{0:.{oil_precision}f}'
            name = '较对照' if app.budget_auto else '较'+(status.reference_label or '最快完赛')
            label(f'{name}  {time_text} s · {oil_text} L/100km', left+24, 244, 19, theme.TEXT_SUB)
        elif spec.targets and not app.budget_auto and reference.build != result.build and not retry_hint:
            label(f'最快完赛对照  {reference.seconds:.1f} s · {reference.consumption:.1f} L/100km',
                  left+24, 244, 19, theme.TEXT_SUB)
    if spec.provisional:
        target_name += ' · 试行'
    fill(left+24, 264, wide-48, 42, (0.055, 0.070, 0.098, 0.85), 6)
    label('本次', left+wide*.60, 293, 20, theme.TEXT_SUB, right=True)
    label(target_name, left+wide-24, 293, 20, theme.TEXT_SUB, right=True)
    oil = result.consumption if result.valid else None
    rows = (('用时 / s', f'{result.seconds:.1f}', f'≤ {target.seconds:.1f}' if target else '—',
             target is not None and result.seconds <= target.seconds),
            ('赛段油耗 / L/100km', '—' if oil is None else f'{oil:.1f}',
             f'≤ {target.consumption:.1f}' if target else '—',
             target is not None and oil is not None and result.litres <= target.consumption*spec.distance_m/100_000),
            ('改装费', str(result.cost), f'≤ {spec.budget}', result.cost <= spec.budget))
    if reference is not None and (app.budget_auto or not spec.targets or status.reference_label):
        # 对照三项来自出发时冻结的同一次完赛。
        rows = (('用时 / s', f'{result.seconds:.1f}', f'{reference.seconds:.1f}',
                 result.valid and result.seconds <= reference.seconds),
                ('赛段油耗 / L/100km', '—' if oil is None else f'{oil:.{oil_precision}f}',
                 f'{reference.consumption:.{oil_precision}f}', oil is not None and oil <= reference.consumption),
                ('改装费', str(result.cost), str(reference.cost), result.cost <= reference.cost))
    if automatic_specialist or specialist_reference:
        actual = result.metric_value if result.valid else None
        limit = reference.metric_value if reference is not None else spec.metric_limits[-1]
        distance = f'{limit:.2f}' if reference is not None else f'≤ {limit:g}'
        rows = (('完赛用时 / s', f'{result.seconds:.1f}', '有效完成' if reference is None else f'{reference.seconds:.1f}',
                 result.valid and (reference is None or result.seconds <= reference.seconds)),
                (f'{spec.metric_label} / {spec.metric_unit}', '—' if actual is None else f'{actual:.2f}', distance,
                 actual is not None and actual <= limit), rows[-1])
    elif spec.assessment != 'road':
        index = min(2, ('', '铜', '银', '金').index(result.medal))
        required = (f'≤ {spec.metric_limits[index]:g}' if spec.assessment == 'lower' else
                    f'5门 / ≤{spec.metric_limits[0]:g}s' if index == 2 else '全部5门' if index == 1 else '至少3门')
        actual = '—' if result.metric_value is None else f'{result.metric_value:g}'
        if spec.assessment == 'lower':
            met = result.valid and result.metric_value is not None and result.metric_value <= spec.metric_limits[index]
        else:
            gates = 3 if index == 0 else 5
            met = (result.valid and result.metric_value is not None and result.metric_value >= gates
                   and (index < 2 or result.seconds <= spec.metric_limits[0]))
        rows = (('完赛用时 / s', f'{result.seconds:.1f}', '有效完成', result.valid),
                (spec.metric_label+' / '+spec.metric_unit, actual, required, met), rows[-1])
    for index, (name, current, required, met) in enumerate(rows):
        y = 353+index*68
        label(name, left+24, y, 20, theme.TEXT_LIGHT)
        label(current, left+wide*.60, y, 26, SUCCESS if met else ORANGE, bold=True, right=True)
        label(required, left+wide-24, y, 22, theme.TEXT_SUB, right=True)
        fill(left+24, y+20, wide-48, 1, theme.SLATE_BORDER, radius=0)
    record_feedback = _record_feedback(status, spec.provisional)
    feedback = result.notice if result.notice != title else ''
    if app.budget_auto and result.valid:
        traffic = road.overtake
        if traffic is not None:
            feedback = f'安全超越{traffic.passes}辆 · 自动试车不计成绩'
    if result.gaps is not None:
        time_gap, oil_gap = result.gaps
        parts = []
        if time_gap:
            parts.append(f'用时需缩短{time_gap:.1f}秒' if time_gap >= .1 else '用时还差不到0.1秒')
        if oil_gap:
            parts.append(f'油耗需降低{oil_gap:.1f} L/100km' if oil_gap >= .1 else '油耗还差不到0.1 L/100km')
        if time_gap == 0 and oil_gap:
            parts.insert(0, '用时已达标')
        elif oil_gap == 0 and time_gap:
            parts.insert(0, '油耗已达标')
        feedback = '，'.join(parts)
    elif career_run is not None and result.valid and result.metric_value is not None:
        if spec.id == 'parking' and result.metric_value > spec.metric_limits[-1]:
            beyond = career_run.position > spec.distance_m
            side = '停过' if beyond else '停早'
            change = '提前' if beyond else '推迟'
            feedback = f'{side} {result.metric_value:.1f} 米 · 同速可稍{change}制动'
        elif spec.assessment == 'career-slalom' and result.metric_value < len(career_run.passed):
            first = career_run.passed.index(False)+1
            feedback = f'第 {first} 门先松油，车身摆正后再通过'
    if record_feedback and not feedback:
        feedback, record_feedback = record_feedback, ''
    label(feedback, left+24, 557, 21, ORANGE, bold=True, wrap=wide-48)
    if spec.assessment == 'career-slalom' and career_run is not None:
        _career_slalom_segments(EVENT_BY_ID[spec.id], career_run, left, wide, fill, label)
    elif spec.id == 'parking' and career_run is not None and result.valid:
        fill(left+24, 598, wide-48, 38, (0.055, 0.070, 0.098, 0.85), 6)
        label('停车位置', left+36, 624, 17, theme.TEXT_SUB)
        label('距起点 / m', left+wide-30, 624, 17, theme.TEXT_SUB, right=True)
        label('停车区中心', left+36, 660, 19, theme.TEXT_LIGHT)
        label(f'{spec.distance_m:.1f}', left+wide-30, 660, 19, theme.TEXT_SUB, right=True)
        label('本次停稳', left+36, 696, 19, theme.TEXT_LIGHT)
        label(f'{career_run.position:.1f}', left+wide-30, 696, 19, theme.TEXT_LIGHT, right=True)
    elif spec.id != 'parking' and slalom is None:
        _result_segments(spec, status, left, wide, fill, label, automatic=app.budget_auto,
                         valley_labels=valley_labels)
    elif slalom is not None:
        _slalom_trial_segments(slalom, app.auto_trial_reference, left, wide, fill, label)
    _vehicle(panel, spec, result.build, width, left, wide, label, fill=fill, image=image)
    award = app.career_award
    _result_build_or_unlocks(result, award, left+wide+18, width-left, fill, label, button, image=image)
    tour = app.tour_active
    store = app.active_series if tour else None
    advanced = tour and len(store.current) > app.tour_round
    failed_progress = (award is not None and not award['saved']) or (tour and store.unsaved)
    needs_save = status.score_pending or failed_progress
    notice = '成绩未保存，原纪录保留' if status.score_pending else status.save_notice or record_feedback
    label(notice, left+24, 815, 17, ORANGE, wrap=wide-230 if needs_save else wide-48)
    if needs_save:
        action = 'challenge-save-score' if status.score_pending else 'tour-save' if tour else 'save'
        button('重试保存进度' if failed_progress else '重试保存成绩', left+wide-184, 790, 160, 38,
               action, role='secondary')
    panel.challenge_readouts['budget'].setText(f'本场预算 {spec.budget}')
    button('Esc 返回综合杯' if app.budget_origin == 'cup' else
           'Esc 返回巡回' if app.budget_origin in ('tour', 'tour-practice') else
           'Esc 返回进阶' if app.budget_origin == 'journey' else 'Esc 返回赛事',
           left, 880, 190, 42, 'challenge-back', role='footer')
    retry_x = width*.48
    if reference is not None and reference.build != result.build and not (advanced or needs_save):
        apply_width = min(240., retry_x-left-230)
        apply_x = min(left+270, retry_x-apply_width-20)
        title = '套用对照方案'
        button(title, apply_x, 877, apply_width, 48, 'challenge-apply-reference', reference.build,
               role='secondary')
    series = '综合杯' if app.budget_origin == 'cup' else '巡回'
    button(series+'总览' if advanced else '重试本场', retry_x, 877, 210, 48,
           'challenge-back' if advanced else 'challenge-retry', role='secondary')
    primary = ('完成'+series if len(store.current) == 3 else '配置下一站') if advanced else '调整方案'
    action = 'tour-next' if advanced else 'challenge-adjust'
    if app.budget_mode == 'coastal-cup' and not needs_save and result.official and result.medal:
        name, continuation, _ = app.season_continuation()
        if continuation in ('cup-menu', 'cup-season-result'):
            primary, action = name, continuation
    primary_enabled = not (advanced and store.cup and store.unsaved)
    res_btn = button(primary, width-left-260, 874, 260, 56, action,
                     role='primary', primary=True, enabled=primary_enabled)
    res_btn['text_pos'] = (16*unit, -7*unit)
    r_ic = atelier.picture(res_btn, panel.loader,
                           'atelier/icon-sliders.png' if action == 'challenge-adjust' else 'atelier/icon-steering.png',
                           (-78*unit, -52*unit, -13*unit, 13*unit),
                           color=theme.INK if primary_enabled else theme.DARK_LOCKED)
    panel.frames.append(r_ic)
    panel.select(panel.primary)


def pause_page(panel, spec, draft, status):
    width, left, fill, label, image, button = canvas(panel, None, spec.name+' · 已暂停', budget=spec.budget)
    unit = 2/941
    _budget(panel, spec, draft.cost)
    wide = min(462., width*.32)
    image('atelier/panel-obsidian.png', left-12, 112, wide+24, 726)
    x, inner = left+28, wide-56
    fill(x, 152, 4.5, 38, ORANGE, 2)
    label('已暂停', x+16, 184, 42, theme.TEXT_LIGHT, bold=True)
    seconds = 0. if status is None else status.seconds
    progress = 0. if status is None else status.progress_m
    label(f'{seconds:.1f} s · {progress:.0f} / {spec.distance_m:.0f} m', x, 252, 20, theme.TEXT_SUB)
    label(f'本场改装 {draft.cost} / {spec.budget}', x, 294, 20, theme.TEXT_LIGHT)
    origin = panel.vehicle_view.base.budget_origin
    back = '返回综合杯' if origin == 'cup' else '返回巡回' if origin in ('tour', 'tour-practice') else '返回挑战'
    for title, y, action in (('继续驾驶', 348, 'challenge-resume'),
                             ('从起点重试', 456, 'challenge-retry'),
                             ('调整方案', 564, 'challenge-adjust'),
                             (back, 672, 'challenge-back')):
        item = button(title, x, y, inner, 72, action, role='primary' if y == 348 else 'secondary', primary=y == 348)
        if y == 348:
            item['text_pos'] = (16*unit, -7*unit)
            ic = atelier.picture(item, panel.loader, 'atelier/icon-steering.png',
                                 (-74*unit, -46*unit, -14*unit, 14*unit), color=theme.INK)
            panel.frames.append(ic)
    label('Esc 继续驾驶', left, 910, 19, theme.TEXT_SUB)
    panel.challenge_readouts['budget'].setText(f'本场预算 {spec.budget}')
    _vehicle(panel, spec, draft, width, left, wide, label, fill=fill, image=image)
    panel.select(panel.primary)


def reference_result_page(panel, spec, draft, data, notice=''):
    """沿用02的原车、实测主表和底栏，参考A/B直接并列原始指标。"""
    width, left, fill, label, image, button = canvas(panel, None, spec.name+' · 试验结果', budget=spec.budget)
    unit = 2/941
    _budget(panel, spec, draft.cost)
    wide = min(680., width*.43)
    image('atelier/panel-obsidian.png', left-12, 112, wide+24, 726)
    fill(left+24, 162, 5, 46, ORANGE, 2)
    label(data['medal']+'牌完成' if data['passed'] else '试验完成', left+40, 204, 44,
          theme.GOLD if data['passed'] and data['medal'] == '金' else theme.TEXT_LIGHT, bold=True)
    fill(left+24, 264, wide-48, 42, (0.055, 0.070, 0.098, 0.85), 6)
    label('指标', left+32, 293, 20, theme.TEXT_SUB)
    label('原车 A', left+wide*.66, 293, 20, theme.TEXT_SUB, right=True)
    label('方案 B', left+wide-24, 293, 20, theme.TEXT_SUB, right=True)
    for index, (name, a, b, unit_label) in enumerate((data['primary'], *data['rows'])):
        yy = 350+index*54
        label(name+' / '+unit_label, left+24, yy, 19, theme.TEXT_LIGHT)
        label('—' if a is None else f'{a:.3f}', left+wide*.66, yy, 22, theme.TEXT_SUB, right=True)
        label('—' if b is None else f'{b:.3f}', left+wide-24, yy, 22, theme.TEXT_LIGHT, bold=True, right=True)
        fill(left+24, yy+16, wide-48, 1, theme.SLATE_BORDER, radius=0)
    label(f"改善 {data['improvement_pct']:.2f}%", left+24, 652, 28, SUCCESS if data['passed'] else ORANGE, bold=True)
    label('全部专项约束达标' if data['passed'] else ' · '.join(data['unmet']),
          left+24, 700, 19, SUCCESS if data['passed'] else ORANGE, wrap=wide-48)
    label(f'本场改装 {draft.cost} / {spec.budget}', left+24, 774, 24, theme.TEXT_LIGHT)
    label(notice, left+24, 814, 17, ORANGE, wrap=wide-48)
    _vehicle(panel, spec, draft, width, left, wide, label, fill=fill, image=image)
    _targets(panel, spec, width, left+wide+18, fill, label, image=image)
    button('Esc 返回参数', left, 880, 190, 42, 'challenge-adjust', role='footer')
    button('导出报告', left+210, 877, 150, 48, 'reference-export', role='secondary')
    button('查看曲线', left+380, 877, 155, 48, 'challenge-lab', role='secondary')
    drive_btn = button('保存并试驾', width-left-260, 874, 260, 56, 'reference-drive', role='primary',
                       enabled=data['passed'], primary=True)
    drive_btn['text_pos'] = (16*unit, -7*unit)
    d_ic = atelier.picture(drive_btn, panel.loader, 'atelier/icon-steering.png',
                           (-80*unit, -54*unit, -13*unit, 13*unit),
                           color=theme.INK if data['passed'] else theme.DARK_LOCKED)
    panel.frames.append(d_ic)
    panel.challenge_readouts['budget'].setText(f'本场预算 {spec.budget}')
    panel.select(panel.primary)


def _budget(panel, spec, cost):
    over = cost > spec.budget
    panel.challenge_readouts['used'].setText(str(cost))
    panel.challenge_readouts['remaining'].setText(str(spec.budget-cost))
    panel.challenge_readouts['remaining'].setFg(theme.MAGENTA_BRIGHT if over else WHITE)
    panel.challenge_readouts['budget-bar'].setSx(min(1., cost/spec.budget))
    panel.challenge_readouts['budget-bar'].setX(panel.challenge_readouts['budget-left']*(1-min(1., cost/spec.budget)))


def update_build(panel, spec, draft, notice=''):
    panel.challenge_updating = True
    cost, costs = draft.cost, draft.costs()
    over = cost > spec.budget
    header = panel.challenge_readouts['budget']
    allowance = f'超出 {cost-spec.budget}' if over else f'剩余 {spec.budget-cost}'
    header.setText(f'本场预算 {spec.budget}    已用 {cost}    {allowance}'
                   if panel.layout_aspect > 1.5 else
                   f'预算 {spec.budget} · 已用 {cost}\n'+allowance)
    header.setFg(theme.MAGENTA_BRIGHT if over else WHITE)
    _budget(panel, spec, cost)
    setups = panel.vehicle_view.base.challenge_presets(spec)
    measured = None
    for index, setup in enumerate(setups):
        edge = panel.challenge_readouts[f'preset:{index}']
        selected = draft == setup.build
        edge.setColor(ORANGE if selected else theme.SLATE_BORDER)
        if selected:
            measured = setup.measured
    if setups:
        title = '参考方案'
        if measured is not None:
            seconds, consumption = measured
            title += f' · 实跑 {seconds:.1f} s / {consumption:.2f} L/100km'
        panel.challenge_readouts['preset-title'].setText(title)
    for key, entry in panel.challenge_entries.items():
        value = field_values(spec, draft, key)[-1]
        entry.enterText(formatted(key, value))
        panel.challenge_sliders[key]['value'] = value
        _, _, low, high, _ = field_values(spec, draft, key)
        # 填充围绕滑杆左端缩放，保留原车独立刻度。
        track = panel.challenge_readouts['track:'+key]
        fraction = (value-low)/(high-low)
        bounds = track.getTightBounds()
        if 'track-left:'+key not in panel.challenge_readouts:
            panel.challenge_readouts['track-left:'+key] = bounds[0].x
        left_x = panel.challenge_readouts['track-left:'+key]
        track.setSx(max(.00001, fraction))
        track.setX(left_x*(1-max(.00001, fraction)))
        panel.challenge_readouts['cost:'+key].setText(str(costs[key]) if key in costs else '免费')
    others = [item for item in HARDWARE if item.key not in panel.challenge_entries and costs[item.key]]
    summary = f'其他改造  {sum(costs[item.key] for item in others)}'
    panel.challenge_readouts['other'].setText(summary)
    config = spec.configuration(draft)
    letter, score, _pi_color, power, _ = theme.vehicle_pi(config)
    panel.challenge_readouts['vehicle'].setText(f'{config.mass:.0f} kg  |  {power:.0f} kW')
    if 'pi-combined' in panel.challenge_readouts:
        panel.challenge_readouts['pi-combined'].setText(f'{letter} {score}')
    panel.challenge_readouts['start']['text'] = ('开始A/B试验' if spec.assessment == 'reference' else
        '试验驾驶' if over or spec.assessment == 'road' and not spec.targets else '开始挑战')
    panel.challenge_readouts['notice'].setText(notice or ('超出预算，本次只作试验' if over else ''))
    panel.challenge_updating = False
