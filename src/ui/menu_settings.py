"""声音与驾驶辅助构图；复用已有设置动作，不持有设置副本。"""

from ui.main_menu import GRAY, ORANGE, WHITE
from ui.menu_layout import canvas, style


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
