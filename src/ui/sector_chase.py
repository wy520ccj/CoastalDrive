"""落日黑曜石与琥珀金风格追时赛选关与按段遥测结算。"""

from race import GameMode
from sector_chase import CHASE_COURSES
from ui import atelier, theme
from ui.career_layout import WHITE, canvas
from ui.lab_widgets import gradient_panel

PHOTOS = {GameMode.TIME_TRIAL: 'career/chase-coastal.png', GameMode.VALLEY_PACE: 'career/chase-valley.png'}


def selection(panel, progress, mode, compatible):
    width, left, fill, label, image, button = canvas(panel, progress, '俱乐部挑战', season=True)
    unit = 2/941
    course = CHASE_COURSES[mode]
    menu_width = width*.29
    right = left+menu_width+28
    available = width-left-right

    label('俱乐部挑战  /  赛段追时', left, 108, 14, theme.DARK_SUB)
    fill(left, 124, 4, 34, theme.AMBER, 2)
    label('赛段追时', left+16, 154, 38, WHITE, bold=True)
    for index, (option, item) in enumerate(CHASE_COURSES.items()):
        y = 204+index*92
        active = option == mode
        button(item.name, left, y, menu_width, 80, 'chase-menu', option,
               role='category-active' if active else 'secondary')

    image('atelier/panel-obsidian.png', left-10, 412, menu_width+20, 422)
    fill(left+10, 434, 3.5, 34, theme.AMBER, 2)
    label('全程实跑参考', left+24, 450, 14, theme.DARK_SUB)
    label(f'{course.reference[-1][1]:.3f} s', left+24, 488, 30, theme.AMBER, bold=True, display=True)
    fill(left+18, 508, menu_width-36, 1.2, (0.24, 0.29, 0.38, 0.85), 0)
    image('atelier/card-idle.png', left+12, 524, menu_width-24, 86)
    image('garage-v2/car-game-tuned.png', left+22, 540, 96, 52)
    label('指定车辆', left+128, 558, 13, theme.DARK_SUB)
    label('Subaru BRZ', left+128, 586, 19, WHITE, bold=True)
    label('有效完赛并保持预算内，计入追时个人最佳。', left+20, 646, 16.5, theme.DARK_SUB, wrap=menu_width-40)
    if not compatible:
        label('追时使用游戏驾驶与默认 ABS / TCS / ESC。', left+20, 738, 17, theme.AMBER, wrap=menu_width-40)

    image('atelier/panel-obsidian.png', right-10, 86, available+20, 750)
    image(PHOTOS[mode], right+4, 100, available-8, 376, crop=True)
    gradient_panel(panel.content, 'chase-scrim',
                   ((right+4-width/2)*unit, (right+available-4-width/2)*unit, 1-476*unit, 1-350*unit),
                   (0.055, 0.068, 0.094, 0.96), (0.055, 0.068, 0.094, 0.0))
    fill(right+14, 486, available-28, 36, (0.055, 0.070, 0.098, 0.85), 6)
    label('赛段', right+26, 511, 16, theme.DARK_SUB)
    label('门位', right+available*.54, 511, 16, theme.DARK_SUB, right=True)
    label('参考累计', width-left-26, 511, 16, theme.DARK_SUB, right=True)
    for index, (name, (distance, seconds, _)) in enumerate(zip(course.labels, course.reference, strict=True)):
        y = 532+index*56
        fill(right+16, y, available-32, 1, (0.22, 0.27, 0.35, 0.80), 0)
        label(name, right+26, y+40, 20, WHITE)
        label(f'{distance:.0f} m', right+available*.54, y+40, 18, theme.DARK_SUB, right=True)
        label(f'{seconds:.3f} s', width-left-26, y+40, 19, theme.STEEL_TEXT, bold=True, right=True, display=True)
    button('返回赛事', left, 866, 160, 56, 'board', role='footer')
    prep_btn = button('准备车辆', width-left-228, 866, 228, 56, 'chase-prepare', mode,
                      role='primary', primary=True, enabled=compatible)
    prep_btn['text_pos'] = (16*unit, -7*unit)
    p_ic = atelier.picture(prep_btn, panel.loader, 'atelier/icon-steering.png',
                           (-72*unit, -46*unit, -13*unit, 13*unit),
                           color=theme.INK if compatible else theme.DARK_LOCKED)
    panel.frames.append(p_ic)
    panel.select(panel.primary if compatible else 0)


def segment_times(status, index):
    if index >= len(status.splits):
        return None, None
    previous = status.splits[index-1].seconds if index else 0.
    reference_start = status.reference_splits[index-1].seconds if index else 0.
    elapsed = status.splits[index].seconds-previous
    reference = status.reference_splits[index].seconds-reference_start
    return elapsed, elapsed-reference


def result(panel, progress, mode, status):
    width, left, fill, label, image, button = canvas(panel, progress, '追时结算', season=True)
    unit = 2/941
    run = status.result
    course, practice = status.chase, status.practice_sector
    data_width = (width-2*left)*.56
    right = left+data_width+26
    photo_w = width-left-right
    image('atelier/panel-obsidian.png', right-10, 86, photo_w+20, 750)
    image(PHOTOS[mode], right+4, 100, photo_w-8, 722, crop=True)
    gradient_panel(panel.content, 'chase-res-scrim',
                   ((right+4-width/2)*unit, (right+photo_w-4-width/2)*unit, 1-822*unit, 1-650*unit),
                   (0.050, 0.062, 0.088, 0.88), (0.050, 0.062, 0.088, 0.0))
    label('赛段追时  /  单段练习' if practice is not None else '赛段追时  /  完赛结算', left, 108, 14, theme.DARK_SUB)
    fill(left, 124, 4, 34, theme.AMBER, 2)
    label(course.name+(' · 单段练习' if practice is not None else ''), left+16, 154, 34, WHITE, bold=True)
    if practice is None:
        label(f'{run.seconds:.3f} s', left, 246, 58, WHITE, bold=True, display=True)
        difference = run.seconds-status.reference_splits[-1].seconds
        summary = (f'较参考 {difference:+.3f} s' if run.valid else run.notice)
        if run.valid and status.chase_best is not None:
            summary += f'  ·  个人最佳 {status.chase_best:.3f} s'
    else:
        elapsed, delta = segment_times(status, practice)
        label('—' if elapsed is None else f'{elapsed:.3f} s', left, 246, 58, WHITE, bold=True, display=True)
        summary = '练习成绩不计入正式纪录' if elapsed is not None else run.notice
        if delta is not None:
            summary += f'  ·  较参考 {delta:+.3f} s'
    label(summary, left, 306, 19, theme.DARK_SUB, wrap=data_width)
    if run.valid and not run.official and practice is None:
        label(run.notice, left, 350, 17, theme.AMBER, wrap=data_width)
    if status.save_notice:
        label(status.save_notice, left, 782, 17, theme.AMBER, wrap=data_width)
    fill(left, 382, data_width, 36, (0.055, 0.070, 0.098, 0.85), 6)
    label('赛段', left+18, 407, 16, theme.DARK_SUB)
    label('本次用时', left+data_width*.67, 407, 16, theme.DARK_SUB, right=True)
    label('与参考', left+data_width-18, 407, 16, theme.DARK_SUB, right=True)
    indexes = range(len(course.labels)) if practice is None else (practice,)
    recommendation = min(len(status.splits), len(course.labels)-1)
    if run.valid and practice is None and len(status.splits) == len(course.labels):
        recommendation = max(indexes, key=lambda i: segment_times(status, i)[1])
    for offset, index in enumerate(indexes):
        y = 432+offset*58
        rec = index == recommendation and practice is None
        image('atelier/card-active.png' if rec else 'atelier/card-idle.png', left-6, y-4, data_width+12, 62)
        if rec:
            fill(left+6, y+11, 3.5, 32, theme.AMBER, 2)
        button('', left, y, data_width, 54, 'chase-practice', index, role='event-card')
        panel.card_edges[len(panel.buttons)-1] = fill(left+6, y+11, 3.5, 32, (0, 0, 0, 0), 2)
        elapsed, delta = segment_times(status, index)
        label(course.labels[index], left+20, y+36, 21, WHITE)
        label('—' if elapsed is None else f'{elapsed:.3f} s', left+data_width*.67, y+36, 20, WHITE,
              right=True, display=elapsed is not None)
        delta_color = theme.PINE if delta is not None and delta < 0 else (
            theme.AMBER if delta is not None and delta > 0 else theme.DARK_SUB)
        label('—' if delta is None else f'{delta:+.3f} s', left+data_width-18, y+36, 20, delta_color,
              bold=delta is not None, right=True, display=delta is not None)
    button('返回赛事', left, 866, 160, 56, 'challenge-back', role='footer')
    if status.score_pending:
        button('重试保存', width-left-681, 866, 190, 56, 'challenge-save-score', role='secondary')
    button('练习此段' if practice is None else '再练此段', width-left-444, 866, 190, 56,
           'chase-practice', recommendation if practice is None else practice, role='secondary')
    full_btn = button('再跑全程', width-left-228, 866, 228, 56, 'chase-full', role='primary', primary=True)
    full_btn['text_pos'] = (16*unit, -7*unit)
    f_ic = atelier.picture(full_btn, panel.loader, 'atelier/icon-steering.png',
                           (-72*unit, -46*unit, -13*unit, 13*unit), color=theme.INK)
    panel.frames.append(f_ic)
    panel.select(panel.primary)
