"""普通驾驶的暂停与结算；统一 Dark Atelier 样式，只排布现有动作和权威比赛快照。"""

from panda3d.core import TextNode

from coastal_medals import result_goal, result_medal
from race import GameMode
from ui import theme
from ui.main_menu import ORANGE, WHITE
from ui.menu_layout import canvas, style
from ui.race_feedback import result_columns


def location(app):
    mode = app.session.mode
    name = {GameMode.TIME_TRIAL: '计时挑战', GameMode.FREE_DRIVE: '自由驾驶',
            GameMode.DISTANCE_CHALLENGE: '五公里无碰撞'}[mode]
    return ('滨海环路' if app.session.simulation.track == 'coastal' else '无限高速'
            if app.session.simulation.track == 'endless' else '测试场')+' · '+name


def pause(cards, app):
    left, wide, _fill, text, button = canvas(cards, app, 'pause', '已暂停', location(app), 0,
                                             panel_limit=462, footer=False)
    cards.summary_values = {}
    x, inner, width = left+28, wide-56, app.getAspectRatio()*941
    text('当前进度已保留', x, 286, 23, theme.TEXT_LIGHT, bold=True)
    text('按 Esc 继续驾驶，返回当前画面。', x, 322, 18, theme.TEXT_SUB)
    for index, title, y in ((0, '继续驾驶', 368), (2, '声音设置', 466),
                             (3, '重新开始', 564), (4, '结束驾驶', 662)):
        item = button(index, title, x, y, inner, 76)
        item['text_font'], item['text_scale'] = app.ui_font, 27*2/941
        item['text_align'], item['text_pos'] = TextNode.ALeft, ((-inner/2+24)*2/941, -9*2/941)
        text('›', x+inner-34, y+50, 32, WHITE if index == 0 else theme.TEXT_SUB)
    text('重新开始将从起点发车。', x, 784, 18, theme.TEXT_SUB)
    button(1, '专家试验台', width-left-350, 880, 180, 44)
    button(5, '返回首页', width-left-150, 880, 150, 44)
    text('↑ ↓ 选择    Enter 确认    Esc 继续', left, 910, 19, theme.TEXT_SUB)
    cards.summary_order = (0, 2, 3, 4, 1, 5)
    cards.garage_quiet = {1, 5}
    style(cards, app.panel_selection)


def result(cards, app, note):
    race, highway = app.session.race.snapshot, app.session.highway.snapshot
    mode, track = app.session.mode, app.session.simulation.track
    timed = mode == GameMode.TIME_TRIAL
    valid = timed and race.finished and race.last_lap is not None and not race.invalidated
    title = ('计时完成' if valid else '圈速无效' if race.invalidated else '计时结束') if timed else (
        '挑战完成' if highway.succeeded else '挑战未完成') if mode == GameMode.DISTANCE_CHALLENGE else '驾驶结束'
    left, wide, fill, text, button = canvas(cards, app, 'result', title, location(app), 0,
                                            footer=False, car_y=220, car_height=428)
    width, x, inner = app.getAspectRatio()*941, left+30, wide-60
    values = cards.summary_values = {}
    cards.summary_order = (0, 1, 2)
    medal = result_medal(race, track)
    outcome = ('滨海'+medal+'牌' if medal else '有效完成 · 尚未达到铜牌' if track == 'coastal'
               else '有效完成') if valid else '本次不记录圈速' if timed else '自由驾驶' if mode == GameMode.FREE_DRIVE else (
                   '完成 5 公里无碰撞挑战' if highway.succeeded else '下次再试')
    fill(x, 254, inner, 48, theme.ORANGE_TINT, 8)
    fill(x, 254, 4, 48, ORANGE, 2)
    values['outcome'] = text(outcome, x+18, 288, 25, ORANGE, bold=True)
    values['title'] = title
    if timed:
        text('本圈用时' if race.last_lap is not None else '本次驾驶用时', x, 344, 19, theme.TEXT_SUB)
        seconds = race.last_lap if race.last_lap is not None else race.elapsed
        values['hero'] = text(f'{seconds:.3f}', x, 418, 72, theme.TEXT_LIGHT, bold=True)
        text('秒', x+inner-28, 415, 24, theme.TEXT_SUB)
        fill(x, 446, inner, 1, theme.SLATE_BORDER, 0)
        text('本配置最佳', x, 490, 21, theme.TEXT_SUB)
        values['best'] = text(f'{race.best_lap:.3f} 秒' if race.best_lap is not None else '暂无有效成绩',
                              x+inner, 490, 26, theme.GOLD if race.best_lap is not None else theme.TEXT_SUB,
                              bold=True, right=True)
        goal = result_goal(race) if track == 'coastal' else '同配置下再次挑战，对照个人最佳。'
        values['goal'] = text(app.fit_lines(goal, inner*2/941, 19*2/941), x, 536, 19, theme.TEXT_SUB)
        lines = []
        if race.invalidated:
            lines.append('圈速无效：'+race.invalid_reason)
        elif race.last_lap is None:
            lines.append('挑战提前结束，本次不记录圈速。')
        elif race.new_best:
            lines.append('本圈更快 · 尚未保存' if race.save_error else
                         '新个人最佳' if race.reference_lap is not None else '首个有效圈 · 已建立最佳参考')
        if app.workspace_vehicle.workshop_result is not None:
            lines = [note]
        else:
            lines.extend(message for message in (race.save_error, race.score_notice if not race.save_error else '',
                                                race.ghost_notice) if message)
        message = '\n'.join(lines) or '成绩已记录，可重新挑战。'
    else:
        if track == 'endless':
            text('本次行驶距离', x, 344, 19, theme.TEXT_SUB)
            values['hero'] = text(f'{highway.distance/1000:.2f}', x, 418, 72, theme.TEXT_LIGHT, bold=True)
            text('公里', x+inner-56, 415, 24, theme.TEXT_SUB)
            fill(x, 446, inner, 1, theme.SLATE_BORDER, 0)
            text('驾驶用时', x, 490, 21, theme.TEXT_SUB)
            text(f'{highway.elapsed:.2f} 秒', x+inner, 490, 26, theme.TEXT_LIGHT, bold=True, right=True)
            text('碰撞次数', x, 536, 21, theme.TEXT_SUB)
            text(f'{highway.collisions} 次', x+inner, 536, 26, theme.TEXT_LIGHT, bold=True, right=True)
        else:
            values['hero'] = text('下次再出发', x, 396, 44, theme.TEXT_LIGHT, bold=True)
            text('滨海环路 · 自由驾驶', x, 456, 22, theme.TEXT_SUB)
        message = highway.reason if mode == GameMode.DISTANCE_CHALLENGE else '自由驾驶不记录圈速。\n可以重新出发，或返回首页换一辆车。'
    fill(x, 582, inner, 138, theme.SLATE_CARD, 8)
    values['notice'] = text(app.fit_lines(message, (inner-28)*2/941, 18*2/941), x+14, 614, 18, theme.TEXT_LIGHT)
    item = button(0, '重新出发' if mode == GameMode.FREE_DRIVE else '重新挑战', x, 744, inner, 58)
    item['text_font'], item['text_scale'] = app.ui_font, 28*2/941
    item['text_pos'] = (0, -9*2/941)
    second = app.buttons[1]['text']
    button(1, '返回首页' if second == '返回主菜单' else second, width-left-310, 880, 160, 44)
    button(2, '退出游戏', width-left-130, 880, 130, 44)
    text('↑ ↓ 选择    Enter 确认', left, 910, 19, theme.TEXT_SUB)
    right = left+wide+18
    available = width-left-right
    fill(right-1, 659, available+2, 170, theme.SLATE_BORDER, 11)
    fill(right, 660, available, 168, theme.SLATE_GLASS, 10)
    values['sectors'] = ()
    if timed and race.splits:
        text('分段用时', right+22, 696, 22, theme.TEXT_LIGHT, bold=True)
        text('本段 / 秒 · 比出发时最佳（负值更快）', right+22, 724, 16, theme.TEXT_SUB)
        columns = result_columns(race)
        rows = tuple(zip(*(column.splitlines()[1:] for column in columns)))
        values['sectors'] = rows
        step = (available-44)/len(rows)
        for index, (sector, split, delta) in enumerate(rows):
            cx = right+22+index*step
            text(sector, cx, 757, 16, theme.TEXT_SUB)
            text(split, cx, 787, 23, theme.TEXT_LIGHT, bold=True)
            color = theme.SUCCESS if delta.startswith('-') else ORANGE if delta.startswith('+') else theme.TEXT_SUB
            text(delta, cx, 813, 16, color)
    else:
        text('驾驶概要', right+22, 696, 22, theme.TEXT_LIGHT, bold=True)
        summary = '无碰撞目标 5.00 公里 · 倒车可调姿' if mode == GameMode.DISTANCE_CHALLENGE else '随时按 Esc 可切换电台或进入专家试验台'
        text(summary, right+22, 740, 19, theme.TEXT_SUB)
    cards.garage_quiet = {1, 2}
    style(cards, app.panel_selection)
