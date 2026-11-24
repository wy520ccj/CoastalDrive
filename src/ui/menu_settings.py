"""落日黑曜石与琥珀金风格声音与驾驶辅助设置面板。"""

from ui import atelier, theme
from ui.main_menu import WHITE
from ui.menu_layout import canvas, style


def _box(app, x, y, w, h):
    width, unit = 941*app.getAspectRatio(), 2/941
    return (x-width/2)*unit, (x+w-width/2)*unit, 1-(y+h)*unit, 1-y*unit


def audio(cards, app, station):
    margin, width, fill, text, button = canvas(cards, app, 'audio', '声音设置', '三个通道独立调节 · 立即保存', 7)
    left, right = margin+30, margin+width-30
    cards.frames.append(atelier.picture(
        cards.content, app.loader, 'atelier/icon-speaker.png',
        _box(app, right-34, 124, 34, 34), color=theme.AMBER))
    for index, (title, description, value) in enumerate((
            ('主音量', '整体播放音量', app.audio_settings.master_volume),
            ('效果音', '引擎 · 轮胎 · 环境', app.audio_settings.effects_volume),
            ('车载音乐', '电台与背景音乐', app.audio_settings.music_volume))):
        y = 276+index*142
        cards.frames.append(atelier.picture(
            cards.content, app.loader, 'atelier/card-idle.png',
            _box(app, left-14, y-40, width-32, 134)))
        text(title, left+6, y, 23, WHITE, bold=True)
        text(f'{value}%', right-6, y, 25, theme.AMBER if value else theme.DARK_SUB, bold=True, right=True, display=True)
        text(description, left+6, y+30, 15.5, theme.DARK_SUB)
        track_width = width-232
        fill(left+6, y+56, track_width, 7, (0.14, 0.17, 0.23, 0.96), 3.5)
        if value:
            fill(left+6, y+56, track_width*value/100, 7, theme.AMBER, 3.5)
        for offset, label in enumerate(('−', '+')):
            button(index*2+offset, label, right-122+offset*64, y+30, 52, 46)
    cards.frames.append(atelier.picture(
        cards.content, app.loader, 'atelier/card-idle.png',
        _box(app, left-14, 678, width-32, 136)))
    fill(left+2, 706, 3.5, 78, theme.AMBER, 2)
    text('当前电台', left+18, 724, 15, theme.AMBER, bold=True)
    name, _, song = station.partition(' · ')
    text(name, left+18, 760, 24, WHITE, bold=True)
    if song:
        text(song, left+18, 788, 15, theme.DARK_SUB)
    button(6, '切换电台  ›', right-166, 722, 158, 48)
    if app.audio_settings.notice:
        text(app.fit_lines(app.audio_settings.notice, (width-60)*2/941, 16*2/941, 1), left, 846, 16, theme.AMBER)
    style(cards, app.panel_selection)


def assists(cards, app):
    margin, width, fill, text, button = canvas(cards, app, 'assists', '驾驶辅助', '下次起步时应用', 3)
    left, right = margin+30, margin+width-30
    cards.frames.append(atelier.picture(
        cards.content, app.loader, 'atelier/icon-shield.png',
        _box(app, right-34, 124, 34, 34), color=theme.AMBER))
    for index, (abbreviation, title, description, enabled) in enumerate((
            ('ABS', '制动防抱死', '调节制动压力，保持转向能力', app.session.abs_enabled),
            ('TCS', '加速防打滑', '抑制驱动轮空转，稳定出弯加速', app.session.tcs_enabled),
            ('ESC', '车身稳定', '主动修正横摆偏转，防止失控', app.session.esc_enabled))):
        y = 314+index*156
        cards.frames.append(atelier.picture(
            cards.content, app.loader, 'atelier/card-active.png' if enabled else 'atelier/card-idle.png',
            _box(app, left-14, y-58, width-32, 146)))
        text(abbreviation, left+8, y+14, 31, theme.AMBER if enabled else theme.DARK_SUB, bold=True, display=True)
        text(title, left+118, y+4, 22, WHITE, bold=True)
        text(description, left+118, y+38, 15.5, theme.DARK_SUB)
        button(index, '开启' if enabled else '关闭', right-138, y-14, 130, 50, toggle=enabled)
    fill(left, 754, width-60, 1.2, (0.24, 0.29, 0.38, 0.85), 0)
    text('点击开关切换状态，Esc 返回。', left, 796, 16, theme.DARK_SUB)
    if app.driving_mode_settings.notice:
        text(app.fit_lines(app.driving_mode_settings.notice, (width-60)*2/941, 16*2/941, 1), left, 846, 16, theme.AMBER)
    style(cards, app.panel_selection)
