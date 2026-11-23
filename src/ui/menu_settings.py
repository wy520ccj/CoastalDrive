"""声音与驾驶辅助构图；复用已有设置动作，统一 Dark Atelier 深海磨砂样式。"""

from ui import theme
from ui.main_menu import ORANGE
from ui.menu_layout import canvas, style


def audio(cards, app, station):
    margin, width, fill, text, button = canvas(cards, app, 'audio', '声音设置', '三个通道独立调节 · 立即保存', 7)
    left, right = margin+30, margin+width-30
    for index, (title, description, value) in enumerate((
            ('主音量', '整体播放音量', app.audio_settings.master_volume),
            ('效果音', '引擎 · 轮胎 · 环境', app.audio_settings.effects_volume),
            ('车载音乐', '电台与背景音乐', app.audio_settings.music_volume))):
        y = 286+index*146
        text(title, left, y, 26, theme.TEXT_LIGHT, bold=True)
        text(f'{value}%', right, y, 27, theme.GOLD if value else theme.TEXT_SUB, bold=True, right=True)
        text(description, left, y+32, 18, theme.TEXT_SUB)
        track_width = width-215
        fill(left, y+56, track_width, 12, (.18, .23, .30, 1), 6)
        if value:
            fill(left, y+56, track_width*value/100, 12, ORANGE, 6)
        for offset, label in enumerate(('−', '+')):
            button(index*2+offset, label, right-118+offset*66, y+32, 52, 50)
        fill(left, y+104, width-60, 1, theme.SLATE_BORDER, 0)
    text('当前电台', left, 740, 18, theme.TEXT_SUB)
    name, _, song = station.partition(' · ')
    text(name, left, 776, 26, theme.TEXT_LIGHT, bold=True)
    if song:
        text(song, left, 804, 15, theme.TEXT_SUB)
    button(6, '切换电台  ›', right-162, 744, 162, 48)
    if app.audio_settings.notice:
        text(app.fit_lines(app.audio_settings.notice, (width-60)*2/941, 16*2/941, 1), left, 850, 16, theme.GOLD)
    style(cards, app.panel_selection)


def assists(cards, app):
    margin, width, fill, text, button = canvas(cards, app, 'assists', '驾驶辅助', '下次起步时应用', 3)
    left, right = margin+30, margin+width-30
    for index, (abbreviation, title, description, enabled) in enumerate((
            ('ABS', '制动防抱死', '调节制动压力，保持转向能力', app.session.abs_enabled),
            ('TCS', '加速防打滑', '抑制驱动轮空转，稳定出弯加速', app.session.tcs_enabled),
            ('ESC', '车身稳定', '主动修正横摆偏转，防止失控', app.session.esc_enabled))):
        y = 330+index*160
        fill(left, y-50, width-60, 1, theme.SLATE_BORDER, 0)
        text(abbreviation, left, y+12, 34, ORANGE if enabled else theme.TEXT_SUB, bold=True)
        text(title, left+116, y+4, 24, theme.TEXT_LIGHT, bold=True)
        text(description, left+116, y+39, 18, theme.TEXT_SUB)
        button(index, '开启' if enabled else '关闭', right-132, y-16, 132, 52, toggle=enabled)
    fill(left, 768, width-60, 1, theme.SLATE_BORDER, 0)
    text('点击开关切换状态，Esc 返回。', left, 804, 18, theme.TEXT_SUB)
    if app.driving_mode_settings.notice:
        text(app.fit_lines(app.driving_mode_settings.notice, (width-60)*2/941, 16*2/941, 1), left, 850, 16, theme.GOLD)
    style(cards, app.panel_selection)
