"""追时赛选关和按段结算；统一 Dark Atelier 深海赛事板语言。"""

from race import GameMode
from sector_chase import CHASE_COURSES
from ui import theme
from ui.career_layout import ORANGE, canvas

PHOTOS = {GameMode.TIME_TRIAL: 'career/chase-coastal.png', GameMode.VALLEY_PACE: 'career/chase-valley.png'}


def selection(panel, progress, mode, compatible):
    width, left, fill, label, image, button = canvas(panel, progress, '俱乐部挑战', season=True)
    course = CHASE_COURSES[mode]
    menu_width = width*.27
    right = left+menu_width+28
    available = width-left-right
    fill(left, 130, 4, 38, ORANGE, 2)
    label('赛段追时', left+16, 162, 42, theme.TEXT_LIGHT, bold=True)
    for index, (option, item) in enumerate(CHASE_COURSES.items()):
        y = 216+index*94
        active = option == mode
        fill(left-1, y-1, menu_width+2, 84, ORANGE if active else theme.SLATE_BORDER, 9)
        button(item.name, left, y, menu_width, 82, 'chase-menu', option,
               role='category-active' if active else 'plain')
        if active:
            fill(left, y+10, 5, 62, ORANGE, 2)
    fill(left, 424, menu_width, 1, theme.SLATE_BORDER, 0)
    label(f'全程实跑参考 {course.reference[-1][1]:.3f} s', left, 464, 21, theme.GOLD, bold=True)
    label('指定车辆 · Subaru BRZ', left, 508, 21, theme.TEXT_LIGHT)
    label('有效完赛并保持预算内，计入追时个人最佳。', left, 558, 19, theme.TEXT_SUB, wrap=menu_width)
    if not compatible:
        label('追时使用游戏驾驶与默认 ABS / TCS / ESC。', left, 718, 20, ORANGE, wrap=menu_width)

    fill(right-1, 107, available+2, 378, theme.SLATE_BORDER, 11)
    image(PHOTOS[mode], right, 108, available, 376, crop=True)
    label('赛段', right+18, 520, 19, theme.TEXT_SUB)
    label('门位', right+available*.54, 520, 19, theme.TEXT_SUB, right=True)
    label('参考累计', width-left-18, 520, 19, theme.TEXT_SUB, right=True)
    for index, (name, (distance, seconds, _)) in enumerate(zip(course.labels, course.reference, strict=True)):
        y = 536+index*58
        fill(right, y, available, 1, theme.SLATE_BORDER, 0)
        label(name, right+18, y+42, 23, theme.TEXT_LIGHT)
        label(f'{distance:.0f} m', right+available*.54, y+42, 21, theme.TEXT_SUB, right=True)
        label(f'{seconds:.3f} s', width-left-18, y+42, 21, theme.TEXT_LIGHT, right=True)
    button('返回赛事', left, 864, 160, 60, 'board', role='footer')
    button('准备车辆', width-left-228, 864, 228, 60, 'chase-prepare', mode,
           role='primary', primary=True, enabled=compatible)
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
    run = status.result
    course, practice = status.chase, status.practice_sector
    data_width = (width-2*left)*.56
    right = left+data_width+28
    fill(right-1, 107, width-left-right+2, 692, theme.SLATE_BORDER, 11)
    image(PHOTOS[mode], right, 108, width-left-right, 690, crop=True)
    fill(left, 128, 4, 34, ORANGE, 2)
    label(course.name+(' · 单段练习' if practice is not None else ''), left+16, 158, 38, theme.TEXT_LIGHT, bold=True)
    if practice is None:
        label(f'{run.seconds:.3f} s', left, 256, 62, theme.TEXT_LIGHT, bold=True)
        difference = run.seconds-status.reference_splits[-1].seconds
        summary = (f'较参考 {difference:+.3f} s' if run.valid else run.notice)
        if run.valid and status.chase_best is not None:
            summary += f'  ·  个人最佳 {status.chase_best:.3f} s'
    else:
        elapsed, delta = segment_times(status, practice)
        label('—' if elapsed is None else f'{elapsed:.3f} s', left, 256, 62, theme.TEXT_LIGHT, bold=True)
        summary = '练习成绩不计入正式纪录' if elapsed is not None else run.notice
        if delta is not None:
            summary += f'  ·  较参考 {delta:+.3f} s'
    label(summary, left, 320, 21, theme.TEXT_SUB, wrap=data_width)
    if run.valid and not run.official and practice is None:
        label(run.notice, left, 362, 19, ORANGE, wrap=data_width)
    if status.save_notice:
        label(status.save_notice, left, 779, 18, ORANGE, wrap=data_width)
    label('赛段', left+18, 418, 19, theme.TEXT_SUB)
    label('本次用时', left+data_width*.67, 418, 19, theme.TEXT_SUB, right=True)
    label('与参考', left+data_width-18, 418, 19, theme.TEXT_SUB, right=True)
    indexes = range(len(course.labels)) if practice is None else (practice,)
    recommendation = min(len(status.splits), len(course.labels)-1)
    if run.valid and practice is None and len(status.splits) == len(course.labels):
        recommendation = max(indexes, key=lambda i: segment_times(status, i)[1])
    for offset, index in enumerate(indexes):
        y = 440+offset*58
        fill(left, y, data_width, 1, theme.SLATE_BORDER, 0)
        if index == recommendation and practice is None:
            fill(left, y+2, data_width, 54, (.22, .15, .14, .95), 6)
            fill(left, y+2, 5, 54, ORANGE, 2)
        button('', left, y+2, data_width, 54, 'chase-practice', index, role='event-card')
        panel.card_edges[len(panel.buttons)-1] = fill(left, y+2, 5, 54, (0, 0, 0, 0), 0)
        elapsed, delta = segment_times(status, index)
        label(course.labels[index], left+18, y+38, 24, theme.TEXT_LIGHT)
        label('—' if elapsed is None else f'{elapsed:.3f} s', left+data_width*.67, y+38, 22, theme.TEXT_LIGHT, right=True)
        delta_color = (.32, .86, .54, 1) if delta is not None and delta < 0 else (
            ORANGE if delta is not None and delta > 0 else theme.TEXT_SUB)
        label('—' if delta is None else f'{delta:+.3f} s', left+data_width-18, y+38, 22, delta_color, right=True)
    button('返回赛事', left, 864, 160, 60, 'challenge-back', role='footer')
    if status.score_pending:
        button('重试保存', width-left-681, 864, 190, 60, 'challenge-save-score', role='secondary')
    button('练习此段' if practice is None else '再练此段', width-left-444, 864, 190, 60,
           'chase-practice', recommendation if practice is None else practice, role='secondary')
    button('再跑全程', width-left-228, 864, 228, 60, 'chase-full', role='primary', primary=True)
    panel.select(panel.primary)
