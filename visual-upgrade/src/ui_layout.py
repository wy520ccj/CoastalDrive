"""页面构图：按设计图把面板、按钮、图标与文字摆到参考像素位置。

布局只描述静态构图与文字装填；操作回调仍由 application 提供。
"""

from direct.gui.DirectGui import DirectFrame
from panda3d.core import TextNode

import ui_theme as theme
from race import GameMode
from ui_components import OptionButton, PageRoot, ValueRow, pixel_text

LOGO = "coastal-drive-logo.png"


def text(parent, canvas, value, x, y, size, *, color=theme.INK, align=TextNode.ALeft):
    return pixel_text(parent, canvas, value, x, y, size, color=color, align=align)


def icon(parent, canvas, skin, name, x, y, size, *, alpha=1.0):
    """图标按参考像素定位，(x, y) 为图标左上角。"""
    node = skin.picture(f"icon-{name}", parent, canvas, x, y, size, size)
    if alpha < 1:
        node.setColorScale(1, 1, 1, alpha)
    return node


def panel(page, canvas, skin, rect, style="panel"):
    """在页面内开一层子面板；坐标相对页面左上角。"""
    x, y = page.rect[0], page.rect[1]
    return PageRoot(page.node, canvas, skin, (x + rect[0], y + rect[1], rect[2], rect[3]), style)


def divider(parent, canvas, x, y, width, *, color=theme.INK_SOFT):
    return DirectFrame(
        parent=parent, frameColor=color, frameSize=(0, canvas.ux(width), 0, canvas.uy(2)),
        pos=(canvas.x(x), 0, canvas.y(y)),
    )


def label(parent, canvas, value, x, y, size, **kwargs):
    return text(parent, canvas, value, x, y, size, **kwargs)


class MainMenuPage:
    """主菜单：左侧奶白入口面板，右侧留给真实海岸场景。

    几何按设计图量取：面板宽约 700、主入口行高约 78，每行是「图标 + 标签 + 箭头」。
    入口与操作成对写在数据块里，顺序即显示顺序；前三项为主入口，其余为次要入口。
    """

    PANEL = (34, 40, 700, 812)
    ENTRY_HEIGHT = 78
    ENTRY_GAP = 14
    SUB_HEIGHT = 62
    SUB_GAP = 12
    ENTRIES = (
        ("计时挑战", "clock", "primary", "main",
         lambda app: app.start_game(mode=GameMode.TIME_TRIAL)),
        ("滨海自由驾驶", "palm", "", "main",
         lambda app: app.start_game(mode=GameMode.FREE_DRIVE)),
        ("无限高速", "road", "", "main", lambda app: app.choose_highway()),
        ("车库", "home", "", "other", lambda app: app.choose_garage()),
        ("声音设置", "volume", "", "other", lambda app: app.choose_audio_settings()),
        ("退出", "arrow", "", "other", lambda app: app.userExit()),
    )

    def __init__(self, parent, canvas, skin, app, notice=""):
        self.canvas = canvas
        self.skin = skin
        self.app = app
        self.page = PageRoot(parent, canvas, skin, self.PANEL)
        x, y, width, _ = self.PANEL
        self._logo(y)
        self.notice = None
        self.notice_node = None
        self.buttons = []
        main_top = y + 168
        other_top = main_top + 3 * (self.ENTRY_HEIGHT + self.ENTRY_GAP) + 34
        for name, icon, style, group, action in self.ENTRIES:
            if group == "main":
                top = main_top + len(self.buttons) * (self.ENTRY_HEIGHT + self.ENTRY_GAP)
                rect = (x + 34, top, width - 68, self.ENTRY_HEIGHT)
                font, size = theme.FONT_HEADING, "main"
            else:
                index = len(self.buttons) - 3
                top = other_top + index * (self.SUB_HEIGHT + self.SUB_GAP)
                rect = (x + 78, top, width - 156, self.SUB_HEIGHT)
                font, size = theme.FONT_BODY, "sub"
            self.buttons.append(self._entry(name, icon, style, action, rect, font, size))
        divider(self.page.node, canvas, x + 34, other_top - 20, width - 68)
        self.set_notice(notice)

    def _entry(self, name, icon, style, action, rect, font_scale, size):
        def command():
            action(self.app)

        button = OptionButton(
            self.page.node, self.canvas, self.skin, rect, name, command,
            primary=style == "primary", icon=icon, font_scale=font_scale, size=size,
        )
        return self.page.add(button)

    def _logo(self, page_y):
        width, height = 900, 190
        logo_width = 520
        self.skin.picture(LOGO, self.page.node, self.canvas,
                          self.PANEL[0] + 46, page_y + 42,
                          logo_width, logo_width * height / width)

    def set_notice(self, notice):
        """保存失败等提示显示在面板底部；为空时不占位。"""
        if notice == self.notice:
            return
        self.notice = notice
        if self.notice_node is None:
            self.notice_node = text(
                self.page.node, self.canvas, notice,
                self.PANEL[0] + self.PANEL[2] / 2, self.PANEL[1] + self.PANEL[3] - 52,
                theme.FONT_LABEL, color=theme.RED, align=TextNode.ACenter,
            )
            return
        self.notice_node.setText(notice)
        self.notice_node.show() if notice else self.notice_node.hide()

    def destroy(self):
        # 按钮已挂进 page.children，由 page.destroy 统一回收
        if self.notice_node is not None:
            self.notice_node.destroy()
        self.page.destroy()


class MessagePage:
    """居中窄面板：暂停、设置与结算共用。

    构图对应设计图：大标题、绿色状态行（可选）、数值行、底部整行操作按钮。
    """

    WIDTH = 640

    def __init__(self, parent, canvas, skin, title, notes, rows, buttons, *,
                 tint=theme.INK, status=None):
        self.canvas = canvas
        self.skin = skin
        self.status = None
        self.notes = []
        self.rows = []
        self.buttons = []
        self.nodes = []
        note_top = 164
        rows_top = note_top + (len(notes) * 46 if notes else 0) + 34
        button_top = rows_top + len(rows) * 72 + (28 if rows else 0)
        height = button_top + len(buttons) * 74 + 44
        x = (1920 - self.WIDTH) / 2
        y = (1080 - height) / 2 - 20
        self.rect = (x, y, self.WIDTH, height)
        self.page = PageRoot(parent, canvas, skin, self.rect)
        center_x = x + self.WIDTH / 2
        self.title = text(self.page.node, canvas, title, center_x, y + 96,
                          theme.FONT_TITLE, color=tint, align=TextNode.ACenter)
        if status:
            # 说明行跟随标题语义：失败红、成功绿、普通局面用弱化色
            status_color = theme.INK_SOFT if tint == theme.INK else tint
            self.status = text(self.page.node, canvas, status, center_x, y + 156,
                               theme.FONT_BODY, color=status_color, align=TextNode.ACenter)
        for index, line in enumerate(notes):
            self.notes.append(text(self.page.node, canvas, line, center_x,
                                   y + note_top + index * 46,
                                   theme.FONT_SUBHEAD, color=theme.INK_SOFT,
                                   align=TextNode.ACenter))
        for index, (icon, name, value) in enumerate(rows):
            self.rows.append(ValueRow(self.page.node, canvas, skin,
                                      (x + 26, y + rows_top + index * 72,
                                       self.WIDTH - 52, 62),
                                      icon, name, value))
        for index, (label, action, primary, icon) in enumerate(buttons):
            self.buttons.append(OptionButton(
                self.page.node, canvas, skin,
                (x + 26, y + button_top + index * 74, self.WIDTH - 52, 62),
                label, action, primary=primary, icon=icon, size="word",
                font_scale=theme.FONT_SUBHEAD,
            ))

    def destroy(self):
        self.title.destroy()
        for node in self.nodes + self.notes:
            node.destroy()
        if self.status is not None:
            self.status.destroy()
        for row in self.rows:
            row.destroy()
        for button in self.buttons:
            button.destroy()
        self.page.destroy()
