"""普通驾驶的暂停与结算；只排布现有动作和权威比赛快照。"""

from panda3d.core import TextNode

from coastal_medals import result_goal, result_medal
from race import GameMode
from ui.main_menu import DARK, GRAY, INK, ORANGE, WHITE
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
    x, inner, width = left+24, wide-48, app.getAspectRatio()*941
    text('当前进度已保留', x, 292, 25, bold=True)
    text('按 Esc 继续驾驶，返回当前游戏。', x, 330, 20, GRAY)
    for index, title, y in ((0, '继续驾驶', 373), (2, '声音设置', 471),
                             (3, '重新开始', 569), (4, '结束驾驶', 667)):
        item = button(index, title, x, y, inner, 78)
        item['text_font'], item['text_scale'] = app.ui_font, 30*2/941
        item['text_align'], item['text_pos'] = TextNode.ALeft, ((-inner/2+24)*2/941, -10*2/941)
        text('›', x+inner-36, y+52, 34, WHITE if index == 0 else INK)
    text('重新开始将从起点发车。', x, 789, 20, GRAY)
    button(1, '专家试验台', width-left-350, 882, 180, 44)
    button(5, '返回首页', width-left-150, 882, 150, 44)
    text('↑ ↓ 选择    Enter 确认    Esc 继续', left, 911, 20, WHITE)
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
    fill(x, 258, inner, 49, (1, .91, .85, 1))
    values['outcome'] = text(outcome, x+15, 292, 27, ORANGE, bold=True)
    values['title'] = title
    if timed:
        text('本圈用时' if race.last_lap is not None else '本次驾驶用时', x, 349, 21, GRAY)
        seconds = race.last_lap if race.last_lap is not None else race.elapsed
        values['hero'] = text(f'{seconds:.3f}', x, 423, 76, bold=True)
        text('秒', x+inner-28, 420, 25, GRAY)
        fill(x, 451, inner, 1, (.76, .79, .83, 1), 0)
        text('本配置最佳', x, 494, 23)
        values['best'] = text(f'{race.best_lap:.3f} 秒' if race.best_lap is not None else '暂无有效成绩',
                              x+inner, 494, 27, bold=True, right=True)
        goal = result_goal(race) if track == 'coastal' else '同配置下再次挑战，对照个人最佳。'
        values['goal'] = text(app.fit_lines(goal, inner*2/941, 20*2/941), x, 540, 20, GRAY)
        # 保存与无效原因占固定信息区；不把未保存的圈速标为已入库最佳。
        lines = []
        if race.invalidated:
            lines.append('圈速无效：'+race.invalid_reason)
        elif race.last_lap is None:
            lines.append('挑战提前结束，本次不记录圈速。')
        elif race.new_best:
            lines.append('本圈更快 · 尚未保存' if race.save_error else
                         '新个人最佳' if race.reference_lap is not None else '首个有效圈 · 已建立最佳参考')
        if app.workspace_vehicle.workshop_result is not None:
            # 原应用保留工程道路验证/保存逻辑；此处完整呈现其消息，不再发奖或写文件。
            lines = [note]
        else:
            lines.extend(message for message in (race.save_error, race.score_notice if not race.save_error else '',
                                                race.ghost_notice) if message)
        message = '\n'.join(lines) or '成绩已记录，可重新挑战。'
    else:
        if track == 'endless':
            text('本次行驶距离', x, 349, 21, GRAY)
            values['hero'] = text(f'{highway.distance/1000:.2f}', x, 423, 76, bold=True)
            text('公里', x+inner-56, 420, 25, GRAY)
            fill(x, 451, inner, 1, (.76, .79, .83, 1), 0)
            text('驾驶用时', x, 494, 23)
            text(f'{highway.elapsed:.2f} 秒', x+inner, 494, 27, bold=True, right=True)
            text('碰撞次数', x, 540, 23)
            text(f'{highway.collisions} 次', x+inner, 540, 27, bold=True, right=True)
        else:
            values['hero'] = text('下次再出发', x, 400, 47, bold=True)
            text('滨海环路 · 自由驾驶', x, 461, 24, GRAY)
        message = highway.reason if mode == GameMode.DISTANCE_CHALLENGE else '自由驾驶不记录圈速。\n可以重新出发，或返回首页换一辆车。'
    fill(x, 586, inner, 138, (.91, .93, .96, 1))
    values['notice'] = text(app.fit_lines(message, (inner-28)*2/941, 18*2/941), x+14, 617, 18, INK)
    item = button(0, '重新出发' if mode == GameMode.FREE_DRIVE else '重新挑战', x, 748, inner, 55)
    item['text_font'], item['text_scale'] = app.ui_font, 30*2/941
    item['text_pos'] = (0, -10*2/941)
    # 第二动作可能为原工程回程；保留原动作与标签，不把它改成另一条路径。
    second = app.buttons[1]['text']
    button(1, '返回首页' if second == '返回主菜单' else second, width-left-310, 882, 160, 44)
    button(2, '退出游戏', width-left-130, 882, 130, 44)
    text('↑ ↓ 选择    Enter 确认', left, 911, 20, WHITE)
    right = left+wide+18
    available = width-left-right
    fill(right, 660, available, 168, DARK)
    values['sectors'] = ()
    if timed and race.splits:
        text('分段用时', right+20, 697, 23, WHITE, bold=True)
        text('本段 / 秒 · 比出发时最佳（负值更快）', right+20, 725, 17, WHITE)
        columns = result_columns(race)
        rows = tuple(zip(*(column.splitlines()[1:] for column in columns)))
        cell = (available-40)/len(rows)
        sector_labels = []
        for index, row in enumerate(rows):
            center = right+20+cell*(index+.5)
            for value, y, size, color in ((row[0], 753, 17, WHITE), (row[1], 782, 23, WHITE),
                                          (row[2], 811, 18, (.51, .94, .71, 1) if row[2].startswith('-') else WHITE)):
                label = text(value, center, y, size, color)
                label.textNode.setAlign(TextNode.ACenter)
                sector_labels.append(label)
        values['sectors'] = tuple(sector_labels)
    else:
        text('自由驾驶 · 不计圈速' if mode == GameMode.FREE_DRIVE else '暂无有效分段记录',
             right+20, 710, 25, WHITE, bold=True)
        text('继续体验当前车辆，或回车库选择下一辆。' if mode == GameMode.FREE_DRIVE else '重新挑战，从起点再次出发。',
             right+20, 756, 18, WHITE)
    cards.garage_quiet = {1, 2}
    style(cards, app.panel_selection)
